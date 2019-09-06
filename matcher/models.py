from datetime import date, timedelta
import logging
import pytz

from django.db import models

import matcher.messages as messages
from .slack import client, send_dm
from .constants import QUESTIONS


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
    channel_id.help_text = "Slack channel ID. You can get this from the URL "\
        "for the Slack channel when loaded in a web browser."
    channel_name = models.CharField(max_length=80)
    channel_name.help_text = "Name of the Slack channel, like “#interns-2020”"
    TIMEZONE_CHOICES = zip(pytz.common_timezones, pytz.common_timezones)
    timezone = models.CharField(max_length=30, default="UTC",
        choices=TIMEZONE_CHOICES)
    timezone.help_text = "Timezone of this pool for automated, scheduled "\
        "matching."

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
    user_name.help_text = "Slack user name. Note: Slack “user names” are "\
        "not like traditional usernames and may not be unique."
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
    LAST_QUERY_CHOICES = [
        (QUESTIONS["intro"], "intro"),
        (QUESTIONS["met"], "met"),
        (QUESTIONS["availability"], "availability")
    ]
    last_query = models.CharField(max_length=3, choices=LAST_QUERY_CHOICES,
        null=True, blank=True)
    last_query.help_text = "The last question the bot asked the user, so "\
        "when they reply we know what question they responded to."

    class Meta:
        verbose_name_plural = "people"
        ordering = ["full_name"]

    @staticmethod
    def get_first_name(full_name):
        """"gets the first part of a Person's full name
        """
        # If the person only has one name on Slack, it will return their full
        # name. N.B. This function is used in the context of getting a user's
        # given name, and this heuristic does not hold in places like China
        # where surname is first.
        return full_name.strip().split(" ")[0]

    def has_intro(self):
        """whether or not this person has an intro
        """
        return bool(self.intro)
    has_intro.boolean = True

    def __str__(self):
        return f"{self.full_name} ({self.user_name})"

class Round(models.Model):
    """a time interval for a Pool in which specific People are paired together
    in a Match to meet each other
    """
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(default=get_default_end_date)

    class Meta:
        ordering = ["-start_date"]

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
    conversation_id = models.CharField(max_length=11, unique=True, null=True,
        blank=True)
    conversation_id.help_text = "ID of the Slack direct message between "\
        "these people"
    # whether or not this pair actually met
    met = models.BooleanField(null=True) # `null` corresponds to unknown
    met.help_text = "Whether or not this pair actually met up"

    class Meta:
        verbose_name_plural = "matches"

    def save(self, *args, **kwargs):
        if not self.pk:
            # automatically send matching message when a match is created
            open_match_dm(self)
        super(Match, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.person_1} ↔ {self.person_2} for round “{self.round}”"


def ask_availability(round):
    """message all members of a Round's Pool to ask if they're available for
    the upcoming round, adding and removing Pool members based on the current
    Slack channel membership
    """

    def send_availability_question(person):
        """actually send a direct message to ask if a person is available
        and update the person's last_query accordingly
        """
        send_dm(person.user_id,
            text=messages.ASK_IF_AVAILABLE.format(person=person))
        person.last_query = QUESTIONS["availability"]
        person.save()
    
    channel_members = get_channel_members(round.pool.channel_id)
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
        else:
            send_availability_question(person)
    for user_id in channel_members:
        try:
            person = Person.objects.get(user_id=user_id)
            # if the person isn't in this pool, add them and ask for their
            # availability
            if round.pool not in person.pools.all():
                person.pools.add(round.pool)
                logger.info(f"Added {person} to pool \"{round.pool}\".")
                send_availability_question(person)
        # if a person has joined the pool, create a Person in the database and
        # ask them to introduce themselves
        except Person.DoesNotExist:
            # get the user's Slack profile
            # https://api.slack.com/methods/users.info
            user = client.users_info(user=user_id)
            # don't add a Person if the user is a bot
            if user["user"]["is_bot"]:
                continue
            try:
                # keys on "profile" are not guaranteed to exist
                full_name = user["user"]["profile"]["real_name"]
            except KeyError:
                send_dm(user_id, text=messages.PERSON_MISSING_NAME)
                logger.warning("Slack \"real_name\" field missing for user: "
                    f"{user_id}")
                continue
            person = Person(user_id=user_id, user_name=user["user"]["name"],
                full_name=full_name,
                casual_name=Person.get_first_name(full_name))
            person.save()
            person.pools.add(round.pool)
            logger.info(f"Added {person} to pool \"{round.pool}\".")
            send_dm(user_id, text=messages.WELCOME_INTRO.format(person=person,
                    pool=round.pool))
            person.last_query = QUESTIONS["intro"]
            person.save()
    logger.info(f"Sent messages to ask availability for round \"{round}\".")


def get_channel_members(channel_id, limit=200):
    """get members from a Slack channel, using pagination as necessary
    https://api.slack.com/methods/conversations.members
    """
    members = []
    cursor = ""
    while True:
        response = client.conversations_members(channel=channel_id,
            cursor=cursor, limit=limit)
        members += response.get("members", [])
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return members


def open_match_dm(self):
    """create a group direct message between the two people in a match and
    introduce them to each other
    """
    user_ids = ",".join([self.person_1.user_id, self.person_2.user_id])
    response = client.conversations_open(users=user_ids)
    try:
        self.conversation_id = response["channel"]["id"]
    except KeyError:
        return logger.error(f"Failed to create conversation for match between"
            f" {self.person_1} and {self.person_2}.")
    # send people's introductions to each other in the channel
    # `unfurl_links=False` prevents link previews from appearing if someone
    # included a link in their intro
    client.chat_postMessage(channel=self.conversation_id, as_user=True,
        text=messages.MATCH_INTRO.format(person_1=self.person_1,
        person_2=self.person_2), unfurl_links=False)
    logger.info(f"Sent matching messages for match: {self}.")
