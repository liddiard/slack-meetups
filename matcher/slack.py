import slack

from meetups import settings
 # importing in this format to avoid circular ImportError
import matcher.models as models


client = slack.WebClient(token=settings.SLACK_API_TOKEN)

# send a direct message to a user as the bot
def send_dm(user_id, *args, **kwargs):
    client.chat_postMessage(channel=user_id, as_user=True, *args, **kwargs)
