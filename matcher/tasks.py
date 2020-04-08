import os
import logging
from random import random

from django.http import HttpResponse

import slack
from celery import Celery

import matcher.messages as messages
from meetups import settings
from .utils import get_other_person_from_match, blockquote


# Note: The Celery worker requires this environment variable to be set in this
# file, see
# https://github.com/celery/django-celery-results/issues/11#issuecomment-268799771
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meetups.settings")


logger = logging.getLogger(__name__)
client = slack.WebClient(token=settings.SLACK_API_TOKEN)

# maximum time to wait before retrying a request in seconds
MAX_WAIT_TIME = 60 * 2

# Celery setup
app = Celery("tasks", broker=settings.CELERY_BROKER_URL)
# how many times to retry a request
# https://github.com/celery/celery/issues/976#issuecomment-233663171
app.Task.max_retries = 5



def get_wait_time(exception, request):
    """get how long a request should wait before retrying, from the Slack API
    response's Retry-After header, if available, or using an exponential
    backoff based on the current retry number
    """
    try:
        return exception.response["headers"]["Retry-After"]
    except (KeyError, AttributeError):
        # wait exponentially longer before reattempting the request with
        # random jitter. adapted from:
        # https://github.com/slackapi/python-slackclient/blob/647f7ab4182ae6055dee80d6c4e062f30fa45078/slack/rtm/client.py#L510
        return min((2 ** request.retries) + random(), MAX_WAIT_TIME)


def get_retries_remaining(self):
    """get the number of retries remaining before the task will fail
    """
    return self.max_retries - self.request.retries


@app.task(bind=True)
def send_msg(self, channel_id, **kwargs):
    """send a message to a user or channel as the bot
    """
    message_text = kwargs.get("text", kwargs.get("blocks"))
    try:
        client.chat_postMessage(channel=channel_id, as_user=True, **kwargs)
    except Exception as exception: # see [1] (bottom of file)
        wait_time = get_wait_time(exception, self.request)
        logger.warning(f"Failed to send message \"{message_text}\" to "
            f"{channel_id}. Retrying in {wait_time} seconds. Error: "
            f"{exception}. {get_retries_remaining(self)} retries remaining.")
        raise self.retry(exc=exception, countdown=wait_time)
    return f"{channel_id}: \"{message_text}\"" # logged to Celery worker


@app.task(bind=True)
def open_match_dm(self, match_id):
    """create a group direct message between the two people in a match and
    introduce them to each other
    """
     # import within the function to avoid a circular ImportError
    import matcher.models as models
    Match = models.Match

    # get the Match object
    try:
        match = Match.objects.get(pk=match_id)
    # the match *should* always exist here as this function runs post-save,
    # but it doesn't for some reason. retry to work around it, though the
    # underlying race condition should be indentified
    except Match.DoesNotExist as exception:
        wait_time = get_wait_time(exception, self.request)
        logger.warning(f"Did not find match with ID: {match_id}. Retrying in "
            f"{wait_time} seconds. Error: {exception}. "
            f"{get_retries_remaining(self)} retries remaining.")
        raise self.retry(exc=exception, countdown=wait_time)

    # open a direct message between the people in the match
    user_ids = ",".join([match.person_1.user_id, match.person_2.user_id])
    # https://api.slack.com/methods/conversations.open
    try:
        response = client.conversations_open(users=user_ids)
        match.conversation_id = response["channel"]["id"]
    except Exception as exception: # see [1] (bottom of file)
        wait_time = get_wait_time(exception, self.request)
        logger.warning(f"Failed to open conversation for match: {match}. "
            f"Retrying in {wait_time} seconds. Error: {exception}. "
            f"{get_retries_remaining(self)} retries remaining.")
        raise self.retry(exc=exception, countdown=wait_time)
    match.save()
    
    # send people's introductions to each other in the channel
    # `unfurl_links=False` prevents link previews from appearing if someone
    # included a link in their intro
    try:
        client.chat_postMessage(channel=match.conversation_id, as_user=True,
            text=messages.MATCH_INTRO.format(person_1=match.person_1,
            person_1_intro=blockquote(match.person_1.intro),
            person_2=match.person_2,
            person_2_intro=blockquote(match.person_2.intro),
            pool=match.round.pool), unfurl_links=False)
    except Exception as exception: # see [1] (bottom of file)
        wait_time = get_wait_time(exception, self.request)
        logger.warning(f"Failed to send message for match: {match}. "
            f"Retrying in {wait_time} seconds. Error: {exception}. "
            f"{get_retries_remaining(self)} retries remaining.")
        raise self.retry(exc=exception, countdown=wait_time)
    logger.info(f"Sent message for match: {match}.")
    return match # logged to Celery worker


@app.task
def ask_if_met(_, user_id, pool_id):
    """ask this person if they met up with their last match in this pool, if
    any, and if we don't know yet
    """
    # import within the function to avoid a circular ImportError
    import matcher.models as models
    Match = models.Match
    pool = models.Pool.objects.get(pk=pool_id)
    # a Person can be either `person_1` or `person_2` on a Match; it's random
    user_matches = (
        Match.objects.filter(round__pool=pool, person_1__user_id=user_id) |
        Match.objects.filter(round__pool=pool, person_2__user_id=user_id)
    )
    if not user_matches:
        # if the Person hasn't matched with anyone yet, skip sending this
        # message
        return HttpResponse(204)
    latest_match = user_matches.latest("round__end_date")
    print("latest_match", latest_match, latest_match.met)
    # if the Person or their match hasn't already provided feedback on their
    # last match, continue to ask if they met
    if latest_match.met is None:
        other_person = get_other_person_from_match(user_id, latest_match)
        blocks = messages.format_block_text(
            "ASK_IF_MET",
            latest_match.id,
            {"pool": pool, "other_person": other_person}
        )
        send_msg.delay(user_id, blocks=blocks)
    return HttpResponse(204)


# [1]: It's a bit of an antipattern to catch all exceptions in Python. The
# reason we're doing it here is because there are simply too many HTTP-related
# exceptions that can be raised from different modules that aren't direct
# dependencies of this project. As such, we don't want to create a dependency
# on an implementation detail of, for example, the HTTP client that the Slack
# SDK uses by importing its error messages in this file, as this would go
# against the principle of encapsulation.