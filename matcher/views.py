import json
import logging

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import decorator_from_middleware

import matcher.messages as messages
from meetups.settings import DEBUG, ADMIN_SLACK_USER_ID
from .middleware import VerifySlackRequest
from .models import Person, Match
from .slack import  send_dm
from .utils import get_person_from_match, get_other_person_from_match


logger = logging.getLogger(__name__)


@decorator_from_middleware(VerifySlackRequest)
def handle_slack_message(request):
    """validate that an incoming Slack message is well-formed enough to
    continue processing, and if so send to its appropriate handler function
    """
    if request.method != "POST":
        return JsonResponse(status=405, 
            data={"error": f"\"{request.method}\" method not supported"})
    try:
        req = json.loads(request.body)
    except ValueError:
        return JsonResponse(status=400, 
            data={"error": "request body is not valid JSON"})
    # To verify our app's URL, Slack sends a POST JSON payload with a 
    # "challenge" parameter with which the app must respond to verify it.
    # Only allow this in debug mode.
    if DEBUG and req.get("challenge"):
        return JsonResponse(req)
    event_type = req.get("event", {}).get("type")
    if event_type != "message":
        return JsonResponse(status=400, 
            data={"error": f"invalid event type \"{event_type}\""})
    # Currently the only free-text (as opposed to action blocks) message we
    # expect from the user is their intro. If we wanted to support more text
    # messages in the future, we'd have to store the last sent message type on
    # the Person object, probably as a CHOICES enum
    return update_intro(req["event"])


@decorator_from_middleware(VerifySlackRequest)
def handle_slack_action(request):
    """validate that an incoming Slack action is well-formed enough to 
    continue processing, and if so send to its appropriate handler function
    """
    # map action names (stored on their respective blocks) to handler functions
    action_map = {
        "availability": update_availability,
        "met": update_met
    }
    if request.method != "POST":
        return JsonResponse(status=405, 
            data={"error": f"\"{request.method}\" method not supported"})
    try:
        payload = request.POST["payload"]
    except KeyError:
        return JsonResponse(status=400, 
            data={"error": "\"payload\" missing from request POST form data"})
    try:
        req = json.loads(payload)
    except ValueError:
        return JsonResponse(status=400, 
            data={"error": "request payload is not valid JSON"})
    try:
        action = req["actions"][0]
    except KeyError:
        return JsonResponse(status=400, 
            data={"error": "request payload is missing an action"})
    try:
        # our block IDs should be of the format "[action name]-[object ID]"
        block_type = action["block_id"].split('-')[0]
        block_id = action["block_id"].split('-')[1]
        action_func = action_map[block_type]
    except KeyError:
        return JsonResponse(status=400, 
            data={"error": f"unknown action \"{action.get('block_id')}\""})
    return action_func(req, action, block_id)


def update_intro(event):
    """update a Person's intro with the message text they send, or if the 
    person already has an intro, send a default message
    """
    user_id = event.get("user")
    message_text = event.get("text", "")
    try:
        person = Person.objects.get(user_id=user_id)
    except Person.DoesNotExist:
        return JsonResponse(status=404,
            data={"error": f"user with ID \"{user_id}\" not found"})
    # if this person has an intro already, we aren't expecting any further
    # messages from them. send them a message telling them how to reach out
    # if they have questions
    if person.intro:
        if ADMIN_SLACK_USER_ID:
            contact_phrase = f", <@{ADMIN_SLACK_USER_ID}>."
        else:
            contact_phrase = "."
        logger.info(f"Received unknown query from {person}: \"{message_text}\".")
        send_dm(user_id, 
            text=messages.UNKNOWN_QUERY.format(contact_phrase=contact_phrase))
    else:
        person.intro = message_text
        # assume availability for a person's first time
        # if people have an issue with this, they can contact
        # `ADMIN_SLACK_USER_ID`. Might revisit if this causes issues.
        person.available = True
        person.save()
        logger.info(f"Onboarded {person} with intro!")
        message = messages.INTRO_RECEIVED.format(person=person)
        if ADMIN_SLACK_USER_ID:
            message += (" " + messages.INTRO_RECEIVED_QUESTIONS\
                .format(ADMIN_SLACK_USER_ID=ADMIN_SLACK_USER_ID))
        send_dm(user_id, text=message)
    return HttpResponse(204)


def update_availability(payload, action, block_id):
    """update a Person's availability based on their yes/no answer, and follow
    up asking if they met with their last Match, if any, and we don't know yet
    """
    if action.get("value") == "yes":
        available = True
    elif action.get("value") == "no":
        available = False
    else:
        return JsonResponse(status=400, 
            data={"error": f"invalid action value \"{action.get('value')}\""})
    try:
        user_id = payload["user"]["id"]
    except KeyError:
        return JsonResponse(status=400, 
            data={"error": "request payload is missing user ID"})
    person = Person.objects.get(user_id=user_id)
    person.available = available
    person.save()
    logger.info(f"Set the availability of {person} to {person.available}.")
    if available:
        message = messages.UPDATED_AVAILABLE
    else:
        message = messages.UPDATED_UNAVAILABLE
    send_dm(user_id, text=message)
    ask_if_met(user_id)
    return HttpResponse(204)


def ask_if_met(user_id):
    # ask this person if they met up with their last match (if any)
    # a Person can be either `person_1` or `person_2` on a Match; it's random
    user_matches = (Match.objects.filter(person_1__user_id=user_id) | 
        Match.objects.filter(person_2__user_id=user_id))
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
        other_person = get_other_person_from_match(user_id, latest_match)
        blocks = messages.format_block_text(
            "ASK_IF_MET", 
            latest_match.id,
            {"other_person": other_person, 
             "start_date": latest_match.round.start_date.strftime(date_format)}
        )
        send_dm(user_id, blocks=blocks)


def update_met(payload, action, block_id):
    """update a Match's `met` status with the provided yes/no answer
    """
    if action.get("value") == "yes":
        met = True
    elif action.get("value") == "no":
        met = False
    else:
        return JsonResponse(status=400, 
            data={"error": f"invalid action value \"{action.get('value')}\""})
    try:
        user_id = payload["user"]["id"]
    except KeyError:
        return JsonResponse(status=400, 
            data={"error": "request payload is missing user ID"}) 
    # a Person can be either `person_1` or `person_2` on a Match; it's random
    user_matches = (Match.objects.filter(person_1__user_id=user_id) | 
        Match.objects.filter(person_2__user_id=user_id))
    try:
        match = user_matches.get(id=block_id)
    except Match.DoesNotExist:
        return JsonResponse(status=404, 
            data={"error": f"match for user \"{user_id}\" with ID "
                f"\"{block_id}\" does not exist"})
    # variables used in message string
    person = get_person_from_match(user_id, match)
    other_person = get_other_person_from_match(user_id, match)
    if match.met is not None and match.met != met:
        logger.warning(f"Conflicting \"met\" info for match \"{match}\". "
            f"Original value was {match.met}, new value from {person} is "
            f"{met}.")
    match.met = met
    match.save()
    logger.info(f"Updated match \"{match}\" \"met\" value to {match.met}.")
    if met:
        message = messages.MET.format(other_person=other_person)
    else:
        message = messages.DID_NOT_MEET
    send_dm(user_id, text=message)
    return HttpResponse(204)
