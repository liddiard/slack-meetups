import copy

# all messages sent to the user are stored here
# use strings with named variables that can be formatted with str.format()

# Slack message formatting reference:
# https://api.slack.com/docs/message-formatting

PERSON_MISSING_NAME = "Sorry, you must have a name set on your Slack profile to participate. Please add your name to your Slack profile."
WELCOME_INTRO = """Welcome, {person.casual_name}! Thanks for joining <#{pool.channel_id}|{pool.channel_name}>. 🎉

Please *introduce yourself* by replying with a short description of what you do. This will be sent to people you pair with.

After I have your introduction, you’ll get your first pairing!
"""
MATCH_INTRO = """*{person_1.casual_name}*, meet your pairing for this week, {person_2.full_name}! Here’s a little about {person_2.casual_name} in their own words:

> {person_2.intro}


*{person_2.casual_name}*, meet your pairing for this week, {person_1.full_name}! Here’s a little about {person_1.casual_name} in their own words:

> {person_1.intro}


Message each other here to *pick a time to meet* this week!
"""
UPDATED_AVAILABLE = "Sounds good! I’ll pair you with someone at the start of the upcoming round."
UPDATED_UNAVAILABLE = "Okay, thanks for letting me know. I’ll ask again next time!"
MET = "Great! Hope you enjoyed meeting {other_person.casual_name} 🙂"
DID_NOT_MEET = "Thanks for the feedback! Hope you have a chance to meet next time 🙂"
UNREGISTERED_PERSON = """Hi there! I’m a bot that facilities 1:1 meetups between people. Join a meetup channel:

{channels}

And the next time a pairing round starts, I’ll ask you for an intro and pair you with someone!
"""
UNKNOWN_QUERY = "Sorry, I don’t know how to respond to most messages! 😬 If you have a question or feedback, you can contact my admin{contact_phrase}"
INTRO_RECEIVED = "Thanks for the intro, {person.casual_name}! You’ll receive your first pairing at the start of the upcoming round."
INTRO_RECEIVED_QUESTIONS = "If you have any questions in the meantime, feel free to ask <@{ADMIN_SLACK_USER_ID}>."
UNSURE_YES_NO_ANSWER = "Sorry, I’m not sure what you mean! Though I hope to gain sentience one day, for now I am a dumb computer 🤖😭 Please respond with “yes” or “no”:"

# questions to user, see also constants.py -> QUESTIONS
ASK_IF_MET = "Last time on {start_date}, you paired with {other_person.full_name} (<@{other_person.user_id}>). Did you have a chance to meet up with {other_person.casual_name}?"
ASK_IF_AVAILABLE = "Hey {person.casual_name}, want to be paired to meet someone new this week?"
