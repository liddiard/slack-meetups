# all messages sent to the user are stored here
# prefer the use of F-strings unless there's a need to deviate
# https://www.python.org/dev/peps/pep-0498/

WELCOME_INTRO_1 = "Hey {person.given_name}, welcome and thanks for joining #{person.pools[0].channel_name}! 🙂 Please *introduce yourself* below with a short description of what you do. This will be sent to the people you match with."
WELCOME_INTRO_2 = "Once we have your introduction, we’ll get you your first match!"
MATCH_1 = """Hey {recipient.given_name}, meet your match for this week, {match.given_name} {match.surname}. Here’s a little about {match.given_name} in their own words: 

> {match.intro}
"""
MATCH_2 = "Send a message to @{match.username} to pick a time to meet this week!"
UPDATED_AVAILABLE = "Great! You’ll be matched with someone shortly."
UPDATED_UNAVAILABLE = "Okay, thanks for updating that you’re not availble this round. We’ll ask again next time!"
MET = "Great! Hope you enjoyed meeting {other_person.given_name}. 🙂"
DID_NOT_MEET = "Thanks for the feedback! Hope you have a chance to meet next time. 🙂"
UNKNOWN_QUERY = "Sorry, the bot doesn’t know how to respond to most messages! 😬 If you have a question or feedback, you can contact the bot’s admin{contact_phrase}"
INTRO_RECEIVED = "Thanks for the intro, {person.given_name}! You’ll receive your first match at the start of the upcoming round."
INTRO_RECEIVED_QUESTIONS = "If you have any questions in the meantime, feel free to ask @{ADMIN_SLACK_USERNAME}."

BLOCKS = {
    "ASK_IF_MET": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Last time on {start_date}, you matched with {other_person.given_name} {other_person.surname} (@{other_person.username}). Did you have a chance to meet with {other_person.given_name}?"
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
                        "text": "Yes, we met!",
                        "value": "yes"
                    },
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "No, we didn’t have a chance to meet",
                        "value": "no"
                    }
                }
            ]
        }
    ],
    "ASK_IF_AVAILABLE": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Hey {person.given_name}, want to be matched to meet someone new this week?"
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
                        "text": "Yes, I want to be matched!",
                        "value": "yes"
                    }
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Not this week, maybe later",
                        "value": "no"
                    }
                }
            ]
        }
    ]
}

def format_block_text(block_name, block_id, dictionary):
    """Format a 2-element block where the first item is a text block and the 
    second item is an action block"""
    # make a copy so we don't mutate the existing block
    block = dict(BLOCKS[block_name])
    text = block[0]["text"]["text"]
    id = block[1]["block_id"]
    text = text.format(dictionary)
    id = id.format({ "id": block_id })
    return block
