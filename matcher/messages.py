import copy

# all messages sent to the user are stored here
# use strings with named variables that can be formatted with str.format()

# Slack message formatting reference:
# https://api.slack.com/docs/message-formatting

PERSON_MISSING_NAME = "Sorry, you must have a name set on your Slack profile to participate. Please add your name to your Slack profile."
WELCOME_INTRO = """Welcome, {person.casual_name}! Thanks for joining <#{pool.channel_id}|{pool.channel_name}>. 🎉

Please *introduce yourself* by sending me a short description of what you do. This will be sent to people you match with.

After I have your introduction, you’ll get your first match!
"""
MATCH_1 = """Hey {recipient.casual_name}, meet your match for this week, {match.full_name} (<@{match.user_id}>)! Here’s a little about {match.casual_name} in their own words: 

> {match.intro}
"""
MATCH_2 = "*Message <@{match.user_id}> to pick a time to meet this week!*"
UPDATED_AVAILABLE = "Sounds good! I’ll match you with someone at the start of the upcoming round."
UPDATED_UNAVAILABLE = "Okay, thanks for letting me know. I’ll ask again next time!"
MET = "Great! Hope you enjoyed meeting {other_person.casual_name} 🙂"
DID_NOT_MEET = "Thanks for the feedback! Hope you have a chance to meet next time 🙂"
UNKNOWN_QUERY = "Sorry, I don’t know how to respond to most messages! 😬 If you have a question or feedback, you can contact my admin{contact_phrase}"
INTRO_RECEIVED = "Thanks for the intro, {person.casual_name}! You’ll receive your first match at the start of the upcoming round."
INTRO_RECEIVED_QUESTIONS = "If you have any questions in the meantime, feel free to ask <@{ADMIN_SLACK_USER_ID}>."

BLOCKS = {
    "ASK_IF_MET": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Last time on {start_date}, you matched with {other_person.full_name} (<@{other_person.user_id}>). Did you have a chance to meet up with {other_person.casual_name}?"
            }
        },
        {
            "type": "actions",
            "block_id": "met-{id}",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {
                        "type": "plain_text",
                        "text": "Yes, we met"
                    },
                    "value": "yes"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "No, we didn’t meet"
                    },
                    "value": "no"
                }
            ]
        }
    ],
    "ASK_IF_AVAILABLE": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Hey {person.casual_name}, want to be matched to meet someone new this week?"
            }
        },
        {
            "type": "actions",
            "block_id": "availability-{id}",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {
                        "type": "plain_text",
                        "text": "Yes, I want to be matched!"
                    },
                    "value": "yes"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Not this week, maybe later"
                    },
                    "value": "no"
                }
            ]
        }
    ]
}

def format_block_text(block_name, block_id, dictionary):
    """Format a 2-element block where the first item is a text block and the
    second item is an action block"""
    # make a deep copy so we don't mutate the block template
    block = copy.deepcopy(BLOCKS[block_name])
    block[0]["text"]["text"] = block[0]["text"]["text"].format_map(dictionary)
    block[1]["block_id"] = block[1]["block_id"].format(id=block_id)
    return block
