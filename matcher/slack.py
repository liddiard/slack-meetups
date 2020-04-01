import os
import logging
from random import random

import slack
from celery import Celery

from meetups import settings
import matcher.messages as messages

# Note: The Celery worker requires this environment variable to be set in this
# file for the `open_match_dm` task to work, or it will raise exception:
# "django.core.exceptions.ImproperlyConfigured: Requested setting
# INSTALLED_APPS, but settings are not configured. You must either define the
# environment variable DJANGO_SETTINGS_MODULE or call settings.configure()
# before accessing settings."
# I am not 100% sure why, but I suspect it is because of the dynamic import in
# that task.
os.environ["DJANGO_SETTINGS_MODULE"] = "meetups.settings"

# Celery setup
app = Celery("tasks", broker=settings.CELERY_BROKER_URL)
# how many times to retry a request
# https://github.com/celery/celery/issues/976#issuecomment-233663171
app.Task.max_retries = 5
# maximum time to wait before retrying a request in seconds
MAX_WAIT_TIME = 60 * 2

logger = logging.getLogger(__name__)
client = slack.WebClient(token=settings.SLACK_API_TOKEN)


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
def send_dm(self, user_id, **kwargs):
    """send a direct message to a user as the bot
    """
    message_text = kwargs.get("text", kwargs.get("blocks"))
    try:
        client.chat_postMessage(channel=user_id, as_user=True, **kwargs)
    except Exception as exception: # see [1] (bottom of file)
        wait_time = get_wait_time(exception, self.request)
        logger.warning(f"Failed to send message \"{message_text}\" to user "
            f"{user_id}. Retrying in {wait_time} seconds. Error: "
            f"{exception}. {get_retries_remaining(self)} retries remaining.")
        raise self.retry(exc=exception, countdown=wait_time)
    return f"{user_id}: \"{message_text}\"" # logged to Celery worker


@app.task(bind=True)
def open_match_dm(self, match_id):
    """create a group direct message between the two people in a match and
    introduce them to each other
    """
     # import within the function to avoid a circular ImportError
    import matcher.models as models
    match = models.Match.objects.get(pk=match_id)
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
            person_2=match.person_2, pool=match.round.pool),
            unfurl_links=False)
    except Exception as exception: # see [1] (bottom of file)
        wait_time = get_wait_time(exception, self.request)
        logger.warning(f"Failed to send message for match: {match}. "
            f"Retrying in {wait_time} seconds. Error: {exception}. "
            f"{get_retries_remaining(self)} retries remaining.")
        raise self.retry(exc=exception, countdown=wait_time)
    logger.info(f"Sent message for match: {match}.")
    return match # logged to Celery worker


# [1]: It's a bit of an antipattern to catch all exceptions in Python. The
# reason we're doing it here is because there are simply too many HTTP-related
# exceptions that can be raised from different modules that aren't direct
# dependencies of this project. As such, we don't want to create a dependency
# on an implementation detail of, for example, the HTTP client that the Slack
# SDK uses by importing its error messages in this file, as this would go
# against the principle of encapsulation.