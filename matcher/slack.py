import slack

from meetups import settings


client = slack.WebClient(token=settings.SLACK_API_TOKEN)
