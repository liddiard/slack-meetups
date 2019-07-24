import json
import logging

from django.http import HttpResponse, JsonResponse

import matcher.messages as messages
from meetups.settings import DEBUG, ADMIN_SLACK_USER_ID
from .models import Person, Match
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
    user_id = event.get("user")
    try:
        person = Person.objects.get(user_id=user_id)
    except Person.DoesNotExist:
        return JsonResponse(status=404,
            data={"error": f"user with ID \"{user_id}\" not found"})
    message_map = {
        QUESTIONS["INTRO"]: update_intro,
        QUESTIONS["MET"]: update_met,
        QUESTIONS["AVAILABILITY"]: update_availability
    }
    message = event.get("text")
    if not person.last_query:
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
    # assume availability for a person's first time
    # if people have an issue with this, they can contact
    # `ADMIN_SLACK_USER_ID`. Might revisit if this causes issues.
    person.available = True
    person.last_query = None
    person.save()
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
    try:
        available = determine_yes_no_answer(event.get("text", ""))
    except ValueError:
        send_dm(person.user_id, text=messages.UNSURE_YES_NO_ANSWER)
        return HttpResponse(204)
    person.available = available
    person.last_query = None
    person.save()
    logger.info(f"Set the availability of {person} to {person.available}.")
    if available:
        message = messages.UPDATED_AVAILABLE
    else:
        message = messages.UPDATED_UNAVAILABLE
    send_dm(person.user_id, text=message)
    ask_if_met(person)
    return HttpResponse(204)


def ask_if_met(person):
    """ask this person if they met up with their last match (if any)
    """
    # a Person can be either `person_1` or `person_2` on a Match; it's random
    user_matches = (Match.objects.filter(person_1__user_id=person.user_id) |
                    Match.objects.filter(person_2__user_id=person.user_id))
    if not user_matches:
        # if the Person hasn't matched with anyone yet, skip sending this
        # message
        return HttpResponse(204)
    latest_match = user_matches.latest("round__end_date")
    # if the Person or their match hasn't already provided feedback on their
    # last match, continue to ask if they met
    if latest_match.met is None:
        # example: "Monday, May 5"
        date_format = "%A, %b %-d"
        other_person = get_other_person_from_match(person.user_id,
            latest_match)
        send_dm(person.user_id, text=messages.ASK_IF_MET.format(
            other_person=other_person, 
            start_date=latest_match.round.start_date.strftime(date_format)))
        person.last_query = QUESTIONS["MET"]
        person.save()
    return HttpResponse(204)


def update_met(event, person):
    """update a Match's `met` status with the provided yes/no answer
    """
    try:
        met = determine_yes_no_answer(event.get("text", ""))
    except ValueError:
        send_dm(person.user_id, text=messages.UNSURE_YES_NO_ANSWER)
        return HttpResponse(204)
    # a Person can be either `person_1` or `person_2` on a Match; it's random
    user_matches = (Match.objects.filter(person_1__user_id=person.user_id) |
                    Match.objects.filter(person_2__user_id=person.user_id))
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
    person.save()
    logger.info(f"Updated match \"{match}\" \"met\" value to {match.met}.")
    if met:
        other_person = get_other_person_from_match(person.user_id, match)
        message = messages.MET.format(other_person=other_person)
    else:
        message = messages.DID_NOT_MEET
    send_dm(person.user_id, text=message)
    return HttpResponse(204)
