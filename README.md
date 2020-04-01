# <img src="https://github.com/liddiard/slack-meetups/blob/master/graphics/bot_logo_thumb.png?raw=true" width="56" alt="bot logo thumbnail" /> Slack Meetups

A Slack bot that randomly pairs users in a Slack channel for 1:1 meetups. Meet new, interesting people in your company, club, or group!

## Features

- 💬 Requests a custom introduction for each person
- ❓ Asks availability each round for everyone in the matching pool
- 🎲 Randomly pairs people to meet via direct message
- 🤝 Collects feedback on who actually met up

It supports variable frequency and length for rounds of matching, multiple matching "pools", and has an admin interface to manage membership, pools, and matching rounds.

## Tech stack

- [Django](https://www.djangoproject.com/) running on Python 3.7+
- SQLite 3 (you can change databases if you need something more robust, but it's not a particularly database-intensive application)
- [Celery](http://www.celeryproject.org/) running on [RabbitMQ](https://www.rabbitmq.com/) as an async task queue for sending messages

**Need to use the Slack [Real-Time Messaging (RTM) API](https://api.slack.com/rtm) instead of the [Events API](https://api.slack.com/events-api)?** Check out the `rtm` branch. You will need to use the RTM API if you're inside a corporate intranet or firewall that won't allow you to receive events from Slack on a publicly accessible URL. The `rtm` branch has a Node.js proxy server under `rtmProxy/` that connects to the socket-based RTM API and forwards events to the Django server. 

The RTM API doesn't support Slack's interactive components like action buttons, so they are replaced with having users just type a "yes"/"no" response to the bot.

## User guide for admins

*Note: This section assumes an already-configured and deployed server. For setup instructions, [see below](#setup-instructions).*

### Add people to a Slack channel

First, get a Slack channel to work with. The bot will automatically message all channel members when you start a new round, so the people in this channel should be at the least aware, and ideally willing to participate. You can use an existing Slack channel or create a new one, but for this reason you may want to have a dedicated channel for the meetup bot.

There is no limit to the number of members who can be in the channel. The more the merrier!

![channel members](screenshots/channel_members.png)

Once you have a channel with some members, you're ready to create a matching pool.

### Create a pool

Log in to the admin interface at `https://<whatever your base url is>/admin/`. The login should look like this:

![admin login](screenshots/admin_login.png)

After logging in, you should see the admin dashboard:

![admin dashboard](screenshots/admin_dashboard.png)

Under the "Matcher" list to the right of "Pools", click the "Add" button. Fill out the info on the page:

![create pool](screenshots/create_pool.png)

- "Name": a human-readable descriptor for the pool, like “2020 interns”
- "Channel ID": Slack's unique identifier for the channel. You can find this by opening Slack in a web browser, navigating to the channel you want to use, and copying the ID from the URL. See screenshot below.
- "Channel name": The name of the Slack channel. This should match the channel name exactly as it appears in Slack.

![slack channel ID](screenshots/slack_channel_id.png)

_Example: The Slack channel ID is the highlighted part of the URL._

Finally, click "Save". Your pool is created!

### Start a round of matching

There are two steps to creating a round of matching: asking availability and actually doing the matching. It's often best to do both on Mondays: Ask for people's availability for the round Monday morning, and do the round matching a few hours later after people have had time to respond.

For people who are new to using the bot (which will be everyone on your first round), instead of being asked for availability, they'll be prompted to type a short intro about themselves. When they respond with this intro, they will automatically be marked as available for their first round.

#### Ask for availabilities/intros

Let's see what both scenarios look like by creating a round. Go back to the main page of the admin interface. Under the "Matcher" list to the right of "Rounds", click the "Add" button.

Select a pool and a start and end date. A week is usually good – start on a Monday and end on a Friday. You can set these to whatever you want though!

![create round](screenshots/create_round.png)

Click the "Save" button. When you do so, everyone in the pool (that is, everyone in the pool's Slack channel) will get a direct message. If they're a first-time user, they'll be asked for an introduction about themselves. Here's how that interaction looks:

![ask for introduction](screenshots/ask_for_introduction.png)

Once they've provided their intro, they're automatically marked as available for their first round. If they never respond with an intro, they'll still appear in the admin interface under "People", but they won't be matched or messaged asking if they're available.

Here's the "People" admin list page:

![people list](screenshots/people_list.png)

For people who've already provided an intro, they'll get a message asking if they want to be matched in the upcoming round. Their response will update their "available" status:

![ask for availability](screenshots/ask_for_availability.png)

### Do the matching!

Once you've given people enough time to write their intro or update their availability, it's time to start the round! From the admin main page, under the "Matcher" list, click "Rounds". Select the round you created, and at the bottom right, click "Do round matching". People in the pool who've responded as available will be randomly paired up. The bot will create a group DM between the two people and introduce them to each other:

![match received](screenshots/match_received.png)

You can see who was matched by going to the admin interface, and under "Matcher" click "Matches". It's not advisable to change matches after they're made because the bot will not automatically re-message people. It's also just confusing for participants.

### Find out who met up

When the current round is over and you're ready to start a new one, follow the same instructions above under "Start a round of matching". The bot will still solicit everyone's availability, but this time after each user RSVPs, the bot will check if this person met with someone before. If so, it will send a follow-up message asking if they met up with their previous match. Here's what that looks like:

![ask if met](screenshots/ask_if_met.png)

From the admin interface, under "Matcher" you can click "Matches" to see a full list of matches. You can filter by round and "met" status to get stats on how many people met up from each round.

![matches list](screenshots/matches_list.png)

## Known limitations

- The bot's message content is a bit specific in places and may not match your use case. Luckily, all content is stored within `matcher/messages.py` so it's fairly easy to customize if you want to fork the repo.
- The bot doesn't do much to handle cases where a person is a member of multiple pools. It will work, but people can't have separate intro text or availability statuses per pool. 
- The bot will only ask about a person's most recent match when asking if they met up, so overlapping rounds with the same person, either in the same pool or among multiple pools, may not give you as much data about who met up.
- The bot doesn't respond to text queries, other than to set a person's intro. Aside from that, it will repond with a generic "Sorry, I don't know how to respond!" type of message, with a mention to contact the bot's admin, if configured. Having the bot respond to other queries would require some refactoring as it would have to keep track of the last message sent to each user.
- Creation of rounds and round matching is manual: There's no automated scheduling. This could be accomplished fairly easily by setting up [custom Django admin commands](https://docs.djangoproject.com/en/dev/howto/custom-management-commands/) and calling them from a cron job.
- On the admin side, there's not a ton of input validation. The app mostly assumes that admins know what they're doing. If they do something wrong or unusual (like using a non-existent ID for a Slack channel, creating a matching round in the past, etc), unexpected behavior is likely to happen. That said, most of the error-prone tasks are in creating pools (generally an infrequent or one-time thing) and editing matches (which is inadvisable anyway). Using Django's built-in user groups, you can restrict admin users' ability to edit these things.

## Setup instructions

### Prerequisites

- Python 3.7+ (the code uses F-strings which aren't available in earlier versions of Python 3)
- Pip 3
- [RabbitMQ](https://www.rabbitmq.com/download.html)

### Installation

1. create a virtualenv folder: `mkdir meetups`
2. [install the virtualenv](https://docs.python.org/3/library/venv.html): `python3 -m venv meetups`
3. `cd meetups`, `source bin/activate`
4. clone repo into the virtualenv
5. `cd [repo]`
6. `pip3 install -r requirements.txt`

### Configuring the web server

1. Create and set required environment variables in your environment: `SECRET_KEY` (required; a long random string for Django's cryptography), `SLACK_API_TOKEN` (required; a bot token to connect to Slack, usually starts with "xoxb-"), `SLACK_SIGNING_SECRET` (required; used to verify that requests are from Slack), `ADMIN_SLACK_USER_ID` (optional; Slack user ID for the admin who people should contact if they have questions)
2. `python manage.py collectstatic` to move static files for serving
3. `python manage.py makemigrations` to set up migrations to create the database tables
5. `python manage.py migrate` to create the database tables
5. `python manage.py createsuperuser` to create your user to log in to the admin
6. Start the server! In development this will be `python3 manage.py runserver`. In production this might be `gunicorn meetups.wsgi`.
7. Log in to the admin and follow the steps above to set up a matching pool. The admin URL is `<your base url>:<port number>/admin/`.

### Configuring the Celery task queue

In order to send Slack messages from the bot, you also need to run a Celery task queue. This queue allows the bot to send messages asyncronously and retry if sending fails, which can happen if there are network issues or the bot gets rate-limited by the Slack API.

After installing RabbitMQ (see Prerequisites above), do the following:

1. Start the RabbitMQ broker by running `rabbitmq-server`
2. In a separate terminal window, source the virtualenv with the command `source bin/activate` (or whatever the path to the `activate` script is)
3. Start the Celery task queue: `celery -A matcher.slack worker --loglevel=info`

## TODO

### MVP

MVP requirements done!

### Post-MVP

- automatic reporting of stats
- analytics graphs
- unit tests? maybe? 🙃
- notify the admin when the bot receives a query it doesn't know how to handle and allow the admin to respond from the bot

_This Slack bot is in no way endorsed by or affiliated with Slack Technologies or their product, Slack._
