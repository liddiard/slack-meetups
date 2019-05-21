import logging
from datetime import date, timedelta

from django.db import models

import matcher.messages as messages
from .slack import client, send_dm


logger = logging.getLogger(__name__)

# this function must be defined before it's passed in the Round class below
def get_default_end_date():
    """calculate the default end date for a Round from the curent date
    """
    # https://stackoverflow.com/a/12654998
    # rounds typically start on a Monday and end on a Friday (5 days later)
    return date.today() + timedelta(days=5)


class Pool(models.Model):
    """a group of People in a Slack channel who are interested in meeting each
    other
    """
    name = models.CharField(max_length=64, unique=True)
    name.help_text = "A human-readable name for this pool, like “2020 "\
        "interns”"
    channel_id = models.CharField(max_length=9, unique=True)
    name.help_text = "Slack channel ID. You can get this from the URL for "\
        "the Slack channel when loaded in a web browser."
    channel_name = models.CharField(max_length=21)
    channel_name.help_text = "Name of the Slack channel, like “#interns-2020”"

    def __str__(self):
        return self.name

class Person(models.Model):
    """corresponds to a Slack user; a single individual
    """
    user_id = models.CharField(max_length=9, unique=True, db_index=True)
    user_id.help_text = "Slack user ID"
    # Slack user "names" are kind of confusing, may be disappearing, are not
    # guaranteed to be unique... and should we even be storing this? It's 
    # still useful though for organizations where `user_name`s correspond to
    # corp IDs/emails. See:
    # https://api.slack.com/changelog/2017-09-the-one-about-usernames
    user_name = models.CharField(max_length=32)
    user_id.help_text = "Slack user name. Note: Slack “user names” are not "\
        "like traditional usernames and may not be unique."
    full_name = models.CharField(max_length=128)
    full_name.help_text = "Person’s full name"
    # `casual_name` _usually_ corresponds to first name and should _usually_ 
    # be analogous to given name. More generally, it's how you'd say, "Hey
    # {casual_name}, nice to meet you!" In an effort to make fewer assumptions
    # about names (especially names as entered on Slack), store this as a 
    # separate, editable field.
    # https://www.kalzumeus.com/2010/06/17/falsehoods-programmers-believe-about-names/
    casual_name = models.CharField(max_length=64)
    casual_name.help_text = "How you would refer to this person in the "\
        "sentence: “Hey {casual_name}, nice to meet you!” Often synonymous "\
        "with “given name.”"
    intro = models.TextField(blank=True)
    intro.help_text = "Introduction that appears to other people when this "\
        "person is matched with them."
    available = models.BooleanField(null=True) # `null` corresponds to unknown
    available.help_text = "Whether or not this person is available for "\
        "and interested in being matched."
    can_be_excluded = models.BooleanField(default=False)
    can_be_excluded.help_text = "Whether or not, in the event of an odd "\
        "number of available people in a matching pool, this person could "\
        "be excluded. Every pool needs at least one available person who "\
        "can be excluded."
    pools = models.ManyToManyField(Pool, blank=True)
    pools.help_text = "Matching pools of which this person is a member. "\
        "This is automatically updated based on Slack channel membership "\
        "whenever a round is started in a particular pool."
    joined = models.DateTimeField(auto_now_add=True)
    joined.help_text = "When this person was first picked up by the bot, "\
        "usually the creation time of the first round in a pool they joined."

    class Meta:
        verbose_name_plural = "people"

    @staticmethod
    def get_first_name(full_name):
        # Get the first part of a Person's full name. If the person only has
        # one name on Slack, it will return their full name. 
        # N.B. This function is used in the context of getting a user's given 
        # name, and this heuristic does not hold in places like China where 
        # surname is first.
        return full_name.strip().split(" ")[0]

    def __str__(self):
        return f"{self.full_name} ({self.user_name})"

class Round(models.Model):
    """a time interval for a Pool in which specific People are paired together
    in a Match to meet each other
    """
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(default=get_default_end_date)

    def save(self, *args, **kwargs):
        if not self.pk:
            # automatically ask availability when a round is created
            ask_availability(self)
        super(Round, self).save(*args, **kwargs)

    def __str__(self):
        # example: "Monday, Jan 9, 2019"
        date_format = "%A, %b %-d, %Y"
        return (f"{self.pool}: {self.start_date.strftime(date_format)} – "
            f"{self.end_date.strftime(date_format)}")

class Match(models.Model):
    """a pairing between two People in a Round to meet each other
    """
    person_1 = models.ForeignKey(Person, on_delete=models.CASCADE, 
        related_name="+")
    person_2 = models.ForeignKey(Person, on_delete=models.CASCADE, 
        related_name="+")
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    # whether or not this pair actually met
    met = models.BooleanField(null=True) # `null` corresponds to unknown
    met.help_text = "Whether or not this pair actually met up"

    class Meta:
        verbose_name_plural = "matches"

    def save(self, *args, **kwargs):
        if not self.pk:
            # automatically send matching messages when a match is created
            send_matching_message(self.person_1, self.person_2)
            send_matching_message(self.person_2, self.person_1)
        super(Match, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.person_1} ↔ {self.person_2} for round “{self.round}”"


def ask_availability(round):
    """message all members of a Round's Pool to ask if they're available for
    the upcoming round, adding and removing Pool members based on the current
    Slack channel membership
    """
    channel_info = client.channels_info(channel=round.pool.channel_id)
    # TODO: accessing channel members this way will be deprecated in the
    # future. We will need to use conversations.members instead:
    # https://api.slack.com/methods/conversations.members
    # see: https://api.slack.com/changelog/2017-10-members-array-truncating
    channel_members = channel_info["channel"]["members"]
    # Get the People in the DB for this Pool, excluding anyone who hasn't
    # written an intro yet. We're considering them excluded, partially for
    # technical reasons: We don't currently keep track of the last message
    # sent to a Person, and if they messaged the bot before writing an intro
    # but after receiving a message asking for availability, we wouldn't know
    # if they're responding with a intro or some other query. But also for UX
    # reasons: it seems reasonable that someone who didn't respond to the
    # bot's initial query is not interested enough to participate.
    people = Person.objects.filter(pools=round.pool).exclude(intro="")
    # initially set everyone's availability to unknown
    people.update(available=None)
    for person in people:
        # if this person has left this pool, update the database to reflect
        # this and don't send them a request for availability
        if person.user_id not in channel_members:
            person.pools.remove(round.pool)
            logger.info(f"Removed {person} from pool \"{round.pool}\".")
            continue
        blocks = messages.format_block_text(
            "ASK_IF_AVAILABLE", 
            person.id,
            {"person": person}
        )
        send_dm(person.user_id, blocks=blocks)
    for user_id in channel_members:
        try:
            Person.objects.get(user_id=user_id)
        # if a person has joined the pool, create a Person in the database and
        # ask them to introduce themselves
        except Person.DoesNotExist:
            # get the user's Slack profile
            # https://api.slack.com/methods/users.info
            user = client.users_info(user=user_id)
            try:
                # keys on "profile" are not guaranteed to exist
                full_name = user["user"]["profile"]["real_name"]
            except KeyError:
                send_dm(user_id, messages.PERSON_MISSING_NAME)
                logger.warning("Slack \"real_name\" field missing for user: "
                    f"{user_id}")
                continue
            person = Person(user_id=user_id, user_name=user["user"]["name"],
                full_name=full_name,
                casual_name=Person.get_first_name(full_name))
            person.save()
            person.pools.add(round.pool)
            logger.info(f"Added {person} to pool \"{round.pool}\".")
            send_dm(user_id, 
                text=messages.WELCOME_INTRO.format(person=person,
                    pool=round.pool))
    logger.info(f"Sent messages to ask availability for round \"{round}\".")


def send_matching_message(recipient, match):
    """notify the two people in a Match that they've been paired with
    instructions to message each other to meet up
    """
    send_dm(recipient.user_id, 
        text=messages.MATCH_1.format(recipient=recipient, match=match))
    send_dm(recipient.user_id, 
        text=messages.MATCH_2.format(match=match))
    logger.info(f"Sent matching messages for match: {match}.")
