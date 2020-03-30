import json
import logging

from django.http import HttpResponse, JsonResponse

import matcher.messages as messages
from meetups.settings import DEBUG, ADMIN_SLACK_USER_ID
from .models import Person, Match, Pool, PoolMembership
from .slack import  send_dm
from .utils import get_other_person_from_match, determine_yes_no_answer
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
    # Currently the only free-text (as opposed to action blocks) message we
    # expect from the user is their intro. If we wanted to support more text
    # messages in the future, we'd have to store the last sent message type on
    # the Person object, probably as a CHOICES enum
    user_id = event.get("user")
    try:
        person = Person.objects.get(user_id=user_id)
    except Person.DoesNotExist:
        # user is unregistered, send an informational message
        pools = Pool.objects.all()
        channels_list = "\n".join(
            [f"• <#{pool.channel_id}|{pool.channel_name}>" for pool in pools]
        )
        message_text = event.get("text")
        logger.info(f"Received query from unregistered user {user_id}: "\
            f"\"{message_text}\".")
        send_dm(user_id,
            text=messages.UNREGISTERED_PERSON.format(channels=channels_list))
        return HttpResponse(204)
    message_map = {
        QUESTIONS["intro"]: update_intro,
        QUESTIONS["met"]: update_met,
        QUESTIONS["availability"]: update_availability
    }
    message = event.get("text")
    if not person.last_query:
        # the bot didn't ask the user anything, tell them we don't know how to
        # respond
        if ADMIN_SLACK_USER_ID:
            contact_phrase = f", <@{ADMIN_SLACK_USER_ID}>."
        else:
            contact_phrase = "."
        logger.info(f"Received unknown query from {person}: \"{message}\".")
        send_dm(user_id,
            text=messages.UNKNOWN_QUERY.format(contact_phrase=contact_phrase))
        return HttpResponse(204)
    try:
        handler_func = message_map[person.last_query]
    except KeyError:
        return JsonResponse(status=500,
            data={"error": f"unknown last query \"{person.last_query}\""})
    return handler_func(event, person)


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
    send_dm(user_id, text=message)
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
        send_dm(person.user_id, text=messages.UNSURE_YES_NO_ANSWER)
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
    logger.info(f"Set the availability of {person} in {pool} to {available}.")
    if available:
        message = messages.UPDATED_AVAILABLE
    else:
        message = messages.UPDATED_UNAVAILABLE
    send_dm(person.user_id, text=message)
    ask_if_met(person, pool)
    return HttpResponse(204)


def ask_if_met(person, pool):
    """ask this person if they met up with their last match (if any)
    """
    # ask this person if they met up with their last match in this pool, if 
    # any, and if we don't know yet
    # a Person can be either `person_1` or `person_2` on a Match; it's random
    user_matches = (
        Match.objects.filter(round__pool=pool, person_1=person) |
        Match.objects.filter(round__pool=pool, person_2=person)
    )
    if not user_matches:
        # if the Person hasn't matched with anyone yet, skip sending this
        # message
        return HttpResponse(204)
    latest_match = user_matches.latest("round__end_date")
    # if the Person or their match hasn't already provided feedback on their
    # last match, continue to ask if they met
    if latest_match.met is None:
        other_person = get_other_person_from_match(person.user_id,
            latest_match)
        send_dm(person.user_id, text=messages.ASK_IF_MET.format(
            other_person=other_person, pool=pool))
        person.last_query = QUESTIONS["met"]
        person.last_query_pool = pool
        person.save()
    return HttpResponse(204)


def update_met(event, person):
    """update a Match's `met` status with the provided yes/no answer
    """
    message_text = event.get("text", "")
    try:
        met = determine_yes_no_answer(message_text)
    except ValueError:
        logger.info(f"Unsure yes/no query from {person}: \"{message_text}\".")
        send_dm(person.user_id, text=messages.UNSURE_YES_NO_ANSWER)
        return HttpResponse(204)
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
    send_dm(person.user_id, text=message)
    return HttpResponse(204)
