import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page

import matcher.messages as messages
from meetups.settings import DEBUG, ADMIN_SLACK_USER_ID
from .models import Person, Match, Pool, PoolMembership, Round
from .tasks import  send_msg, ask_if_met
from .utils import (get_person_from_match, get_other_person_from_match,
                    get_mention, remove_mention, determine_yes_no_answer)
from .constants import QUESTIONS


logger = logging.getLogger(__name__)


def handle_slack_message(request):
    """validate that an incoming Slack message is well-formed enough to
    continue processing, and if so send to its appropriate handler function
    """
    if request.method != "POST":
        return JsonResponse(status=405,
            data={"error": f"\"{request.method}\" method not supported"})
    try:
        event = json.loads(request.body)
    except ValueError:
        return JsonResponse(status=400,
            data={"error": "request body is not valid JSON"})
    # To verify our app's URL, Slack sends a POST JSON payload with a
    # "challenge" parameter with which the app must respond to verify it.
    # Only allow this in debug mode.
    if DEBUG and event.get("challenge"):
        return JsonResponse(event)
    event_type = event.get("type")
    if event_type != "message":
        return JsonResponse(status=400,
            data={"error": f"invalid event type \"{event_type}\""})
    # Ignore messages from bots so the bot doesn't get stuck in an infinite
    # conversation loop with itself.
    bot_id = event.get("bot_id")
    if bot_id:
        return HttpResponse(204)
    # If the message sent was from the admin and they're @-mentioning someone,
    # send a message to that Slack user from the bot.
    message_sender = event.get("user")
    message_text = event.get("text")
    if message_sender == ADMIN_SLACK_USER_ID and get_mention(message_text):
        return send_message_as_bot(message_text)
    # Currently the only free-text (as opposed to action blocks) message we
    # expect from the user is their intro. If we wanted to support more text
    # messages in the future, we'd have to store the last sent message type on
    # the Person object, probably as a CHOICES enum
    user_id = event.get("user")
    try:
        person = Person.objects.get(user_id=user_id)
    except Person.DoesNotExist:
        # user is not registered with the bot
        return handle_unknown_message(user_id, message_text)
    message_map = {
        QUESTIONS["intro"]: update_intro,
        QUESTIONS["met"]: update_met,
        QUESTIONS["availability"]: update_availability
    }
    message = event.get("text")
    if not person.last_query:
        # the bot didn't ask the user anything, it's not expecting any 
        # particular message from them
        return handle_unknown_message(user_id, message_text)
    try:
        handler_func = message_map[person.last_query]
    except KeyError:
        logger.error(f"Unknown last query for {person}: {person.last_query}")
        return JsonResponse(status=500,
            data={"error": f"unknown last query \"{person.last_query}\""})
    return handler_func(event, person)

@cache_page(60 * 30) # cache response for 30 minutes
def get_pool_stats(request, channel_name):
    """validate that an incoming Slack message is well-formed enough to
    continue processing, and if so send to its appropriate handler function
    """
    if request.method != "GET":
        return JsonResponse(status=405,
            data={"error": f"\"{request.method}\" method not supported"})
    try:
        pool = Pool.objects.get(channel_name=channel_name)
    except Pool.DoesNotExist:
        return JsonResponse(status=404,
            data={"error": f"pool with channel name {channel_name} does not "
                            "exist"})
    most_recent_round = Round.objects.filter(pool=pool).latest("end_date")
    # exclude the most recent round because we won't have info yet on who met
    # up from it, so including it would skew the statistics
    matches = Match.objects.filter(round__pool=pool)\
        .exclude(round=most_recent_round)
    match_people = set([match.person_1.pk for match in matches] +
                        [match.person_2.pk for match in matches])
    return JsonResponse({
        "name": pool.name,
        "member_count": PoolMembership.objects.filter(pool=pool).count(),
        "people": list(Person.objects.filter(pk__in=match_people)\
            .values("id", "full_name")),
        "round_count": Round.objects.filter(pool=pool)\
            .exclude(pk=most_recent_round.pk).count(),
        "matches": list(matches.values("id", "person_1", "person_2",
            "met"))
    })


def update_intro(event, person):
    """update a Person's intro with the message text they send, or if the
    person already has an intro, send a default message
    """
    user_id = event.get("user")
    message_text = event.get("text", "")
    person.intro = message_text
    person.last_query = None
    person.last_query_pool = None
    person.save()
    # automatically set the Person to available for their first time
    # if people have an issue with this, they can contact
    # `ADMIN_SLACK_USER_ID`. Might revisit if this causes issues.
    PoolMembership.objects.filter(person=person).update(available=True)
    logger.info(f"Onboarded {person} with intro!")
    message = messages.INTRO_RECEIVED.format(person=person)
    if ADMIN_SLACK_USER_ID:
        message += (" " + messages.INTRO_RECEIVED_QUESTIONS\
            .format(ADMIN_SLACK_USER_ID=ADMIN_SLACK_USER_ID))
    send_msg.delay(user_id, text=message)
    return HttpResponse(204)


def update_availability(event, person):
    """update a Person's availability based on their yes/no answer, and follow
    up asking if they met with their last Match, if any, and we don't know yet
    """
    message_text = event.get("text", "")
    try:
        available = determine_yes_no_answer(message_text)
    except ValueError:
        logger.info(f"Unsure yes/no query from {person}: \"{message_text}\".")
        send_msg.delay(person.user_id, text=messages.UNSURE_YES_NO_ANSWER)
        return HttpResponse(204)
    pool = person.last_query_pool
    try:
        pool_membership = PoolMembership.objects.get(pool=pool, person=person)
    except PoolMembership.DoesNotExist:
        return JsonResponse(status=400,
            data={"error": f"pool membership does not exist with pool: "\
                f"{pool} and person: {person}"})
    pool_membership.available = available
    pool_membership.save()
    person.last_query = None
    person.last_query_pool = None
    person.save()
    logger.info(f"Set the availability of {person} in {pool} to {available}.")
    if available:
        message = messages.UPDATED_AVAILABLE
    else:
        message = messages.UPDATED_UNAVAILABLE
    # perform tasks in sequence to avoid a race condition between the messages
    # https://docs.celeryproject.org/en/4.4.2/userguide/canvas.html#chains
    (send_msg.s(person.user_id, text=message) |
     ask_if_met.s(person.user_id, pool.pk)).delay()
    return HttpResponse(204)


def update_met(event, person):
    """update a Match's `met` status with the provided yes/no answer
    """
    message_text = event.get("text", "")
    try:
        met = determine_yes_no_answer(message_text)
    except ValueError:
        logger.info(f"Unsure yes/no query from {person}: \"{message_text}\".")
        send_msg.delay(person.user_id, text=messages.UNSURE_YES_NO_ANSWER)
        return HttpResponse(204)
    pool = person.last_query_pool
    # a Person can be either `person_1` or `person_2` on a Match; it's random
    user_matches = (
        Match.objects.filter(round__pool=pool, person_1=person) |
        Match.objects.filter(round__pool=pool, person_2=person)
    )
    if not user_matches:
        return JsonResponse(status=404,
            data={"error": f"user \"{person.user_id}\" does not have any "
                "matches"})
    # assuming that the user is reporting on their latest match
    match = user_matches.latest("round__end_date")
    if match.met is not None and match.met != met:
        logger.warning(f"Conflicting \"met\" info for match \"{match}\". "
            f"Original value was {match.met}, new value from {person} is "
            f"{met}.")
    match.met = met
    match.save()
    person.last_query = None
    person.last_query_pool = None
    person.save()
    logger.info(f"Updated match \"{match}\" \"met\" value to {match.met}.")
    if met:
        other_person = get_other_person_from_match(person.user_id, match)
        message = messages.MET.format(other_person=other_person)
    else:
        message = messages.DID_NOT_MEET
    send_msg.delay(person.user_id, text=message)
    return HttpResponse(204)


def handle_unknown_message(user_id, message):
    """If the bot receives a message it doesn't know how to deal with, send it
    a direct message to the admin, if defined, otherwise respond with a
    generic "Sorry I don't know how to help you" type of message
    """
    logger.info(f"Received unknown query from {user_id}: \"{message}\".")
    if ADMIN_SLACK_USER_ID:
        send_msg.delay(ADMIN_SLACK_USER_ID,
            text=messages.UNKNOWN_MESSAGE_ADMIN.format(user_id=user_id,
            message=message))
    else:
        send_msg.delay(user_id, text=messages.UNKNOWN_MESSAGE_NO_ADMIN)
    return HttpResponse(204)


def send_message_as_bot(message):
    """Send a message to the first user @-mentioned in message as the bot
    """
    channel_id = get_mention(message)
    message = remove_mention(message)
    if message: # don't try to send an empty message
        send_msg.delay(channel_id, text=message)
        logger.info(f"Sent message to {channel_id} as bot: \"{message}\".")
    return HttpResponse(204)