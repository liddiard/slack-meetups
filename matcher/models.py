from datetime import date, timedelta

from django.db import models
import logging

import messages
from .slack import client


# Get an instance of a logger
logger = logging.getLogger(__name__)

class Pool(models.Model):
    name = models.CharField(max_length=64, unique=True)
    channel_id = models.CharField(max_length=9, unique=True)
    channel_name = models.CharField(max_length=21)

    def __str__(self):
        return self.name

class Person(models.Model):
    user_id = models.CharField(max_length=9, unique=True, index=True)
    username = models.CharField(max_length=32, unique=True)
    given_name = models.CharField(max_length=64)
    surname = models.CharField(max_length=64)
    intro = models.TextField(blank=True)
    available = models.BooleanField(default=False)
    can_be_excluded = models.BooleanField(default=False)
    pools = models.ManyToManyField(Pool, blank=True)
    joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "people"

    def __str__(self):
        return f"{self.given_name} {self.surname} ({self.username})"

class Round(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    # rounds typically start on a Monday and end on a Friday (5 days later)
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(default=(date.today() + timedelta(days=5)))

    def save(self, *args, **kwargs):
        if not self.pk:
            # automatically ask availability when a round is created
            ask_availability(self)
        super(Round, self).save(*args, **kwargs)

    def __str__(self):
        # example: "Monday, Jan 9, 2019"
        date_format = "%A, %b %-d, %Y"
        return f"{self.pool}: {self.start_date.strftime(date_format)} – {self.end_date.strftime(date_format)}"

class Match(models.Model):
    person_1 = models.ForeignKey(Person, on_delete=models.CASCADE, 
        related_name="+")
    person_2 = models.ForeignKey(Person, on_delete=models.CASCADE, 
        related_name="+")
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    met = models.BooleanField(null=True) # `null` corresponds to unknown

    class Meta:
        verbose_name_plural = "matches"

    def save(self, *args, **kwargs):
        if not self.pk:
            # automatically send matching messages when a match is created
            send_matching_message(self.person_1, self.person_2)
            send_matching_message(self.person_2, self.person_1)
        super(MyModel, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.person_1} ↔ {self.person_2} for round “{self.round}”"


def ask_availability(round):
    channel_info = client.channels_info(channel=round.pool.channel_id)
    channel_members = channel_info["channel"]["members"]
    people = Person.objects.filter(pools=round.pool)
    # initially set everyone's availability to False
    people.update(available=False)
    for person in people:
        # if this person has left this pool, update the database to reflect 
        # this and don't send them a request for availability
        if person.user_id not in channel_members:
            person.pools.remove(round.pool)
            logger.info(f"Removed {person} from pool \"{round.pool}\".")
            continue
        client.send_dm(person.user_id, 
            blocks=messages.BLOCKS["ASK_IF_AVAILABLE"])
    for user_id in channel_members:
        try:
            Person.objects.get(user_id=user_id)
        # if a person has joined the pool, create a Person in the database and
        # ask them to introduce themselves
        except Person.DoesNotExist:
            user = client.users_info(user=user_id)
            Person(user_id=user_id, 
                username=user["user"]["name"], 
                given_name=user["user"]["profile"]["first_name"],
                surname=user["user"]["profile"]["last_name"])
            person.save()
            person.pools.add(obj)
            logger.info(f"Added {person} to pool \"{round.pool}\".")
            client.send_dm(user_id, text=messages.WELCOME_INTRO_1)
            client.send_dm(user_id, text=messages.WELCOME_INTRO_2)
    logger.info(f"Sent messages to ask availability for round \"{round}\".")


def send_matching_message(recipient, match):
    client.send_dm(recipient.user_id, text=messages.MATCH_1)
    client.send_dm(recipient.user_id, text=messages.MATCH_2)
    logger.info(f"Sent matching messages for match: {match}.")
