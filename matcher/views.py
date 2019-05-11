import json

from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
import logging

import messages
from .models import Pool, Person, Round, Match
from .slack import client, send_dm
from meetups.settings import ADMIN_SLACK_USERNAME


# Get an instance of a logger
logger = logging.getLogger(__name__)

def handle_slack_action(request):
    # map action names (stored on their respective blocks) to handler functions
    action_map = {
        "availability": update_availability,
        "met": update_met
    }
    if request.method != "POST":
        return JsonResponse(status=405, 
            data={"error": f"\"{request.method}\" method not supported"})
    try:
        req = json.loads(request.body)
    except ValueError:
        return JsonResponse(status=400, 
            data={"error": "request body is not valid JSON"})
    try:
        action = req["payload"]["actions"][0]
    except KeyError:
        return JsonResponse(status=400, 
            data={"error": "request payload is missing an action"})
    try:
        block_type = action["block_id"].split('-')[0]
        block_id = action["block_id"].split('-')[1]
        action_func = action_map[block_type]
    except KeyError:
        return JsonResponse(status=400, 
            data={"error": f"unknown action type \"{action.get('block_id')}\""})
    return action_func(req["payload"], action, block_id)


def handle_slack_message(request):
    if request.method != "POST":
        return JsonResponse(status=405, 
                data={"error": f"\"{request.method}\" method not supported"})
    try:
        req = json.loads(request.body)
    except ValueError:
        return JsonResponse(status=400, 
            data={"error": "request body is not valid JSON"})
    event_type = req.get("event", {}).get("type")
    if event_type != "message":
        return JsonResponse(status=400, 
            data={"error": f"invalid event type \"{event_type}\""})
    # Currently the only free-text (as opposed to action blocks) message we
    # expect from the user is their intro. If we wanted to support more text
    # messages in the future, we'd have to store the last sent message type on
    # the Person object, probably as a CHOICES enum
    return update_intro(req["event"])
    
    

def update_availability(payload, action, block_id):
    if action.get("value") == "yes":
        available = True
    elif action.get("value") == "no":
        available = False
    else:
        return JsonResponse(status=400, 
            data={"error": f"invalid action value \"{action.get('value')}\""})
    # TODO: validate input
    try:
        user_id = payload["user"]["id"]
    except KeyError:
        return JsonResponse(status=400, 
            data={"error": "request payload is missing user ID"})
    person = People.objects.get(user_id=user_id)
    person.available = available
    person.save()
    logger.info(f"Set the availability of {person} to {person.available}.")
    if available:
        message = messages.UPDATED_AVAILABLE
    else:
        message = messages.UPDATED_UNAVAILABLE
    send_dm(user_id, text=message)
    # a Person can be either `person_1` or `person_2` on a Match; it's random
    user_matches = Match.objects.filter(person_1=user_id) | Match.objects.filter(person_2=user_id)
    if not len(user_matches):
        # if the Person hasn't matched with anyone yet, skip this
        return HttpResponse(204)
    latest_match = user_matches.latest("round__pool__end_date")
    # if the Person or their match hasn't already provided feedback on their
    # last match, ask if they met
    if latest_match.met is None:
        # variable used in message string
        other_person = get_other_person_from_match(user_id, latest_match)
        # example: "Monday, May 5"
        date_format = "%A, %b %-d"
        send_dm(user_id, blocks=messages.BLOCKS["ASK_IF_MET"])
    return HttpResponse(204)


def update_met(payload, action, block_id):
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
    user_matches = Match.objects.filter(person_1=user_id) | Match.objects.filter(person_2=user_id)
    try:
        match = user_matches.get(id=block_id)
    except Match.DoesNotExist:
        return JsonResponse(status=404, 
            data={"error": f"match for user \"{user_id}\" with ID \"{block_id}\" does not exist"})
    # variables used in message string
    person = get_person_from_match(user_id, match)
    other_person = get_other_person_from_match(user_id, match)
    if match.met is not None and match.met != met:
        logger.warning(f"Conflicting \"met\" info for match \"{match}\". Original value was {match.met}, new value from {person} is {met}.")
    match.met = met
    match.save()
    logger.info(f"Updated match \"{match}\" \"met\" value to {match.met}.")
    if met:
        message = messages.MET
    else:
        message = messages.DID_NOT_MEET
    send_dm(user_id, text=message)
    return HttpResponse(204)
    

def update_intro(event):
    user_id = event.get("user")
    message_text = event.get("text", "")
    try:
        person = Person.objects.get(user_id=user_id)
    except Person.DoesNotExist:
        return JsonResponse(status=404, 
            data={"error": f"user with ID \"{user_id}\" not found"})
    if person.intro:
        if ADMIN_SLACK_USERNAME:
            contact_phrase = f", @{ADMIN_SLACK_USERNAME}!"
        else:
            contact_phrase = "."
        logger.warn(f"Received unknown query from {person}: \"{message_text}\".")
        send_dm(user_id, text=messages.UNKNOWN_QUERY)
    else:
        person.intro = message_text
        # assume availability for a person's first time
        # if the have an issue with this, they can contact 
        # `ADMIN_SLACK_USERNAME`. Might revisit if this causes issues.
        person.available = True
        person.save()
        logger.info(f"Onboarded {person} with intro!")
        message = messages.INTRO_RECEIVED
        if ADMIN_SLACK_USERNAME:
            message += (" " + messages.INTRO_RECEIVED_QUESTIONS)
        send_dm(user_id, text=message)
    return HttpResponse(204)


def get_person_from_match(user_id, match):
    if match.person_1.user_id == user_id:
        return match.person_1
    elif match.person_2.user_id == user_id:
        return match.person_2
    else:
        raise Exception(f"Person with user ID \"{user_id}\" is not part of the passed match ({match}).")


def get_other_person_from_match(user_id, match):
    if match.person_1.user_id == user_id:
        return match.person_2
    elif match.person_2.user_id == user_id:
        return match.person_1
    else:
        raise Exception(f"Person with user ID \"{user_id}\" is not part of the passed match ({match}).")
