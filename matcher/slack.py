import logging

import slack

from meetups import settings
 # importing in this format to avoid circular ImportError
import matcher.models as models


logger = logging.getLogger(__name__)
client = slack.WebClient(token=settings.SLACK_API_TOKEN)

# send a direct message to a user as the bot
def send_dm(user_id, *args, **kwargs):
    try:
        client.chat_postMessage(channel=user_id, as_user=True, *args, **kwargs)
    except slack.errors.SlackApiError as error:
        message_text = kwargs.get("text")
        logger.error(f"Failed to send Slack message \"{message_text}\" to "
            f"user {user_id}. Error: {error}")
