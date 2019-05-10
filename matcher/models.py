import random
from datetime import date, timedelta

from django.db import models

from .slack import client
from .utils import group


class Pool(models.Model):
    name = models.CharField(max_length=64, unique=True)
    channel_id = models.CharField(max_length=9, unique=True)
    channel_name = models.CharField(max_length=21)

    def __str__(self):
        return self.name

class Person(models.Model):
    user_id = models.CharField(max_length=9, unique=True)
    username = models.CharField(max_length=32, unique=True)
    given_name = models.CharField(max_length=64)
    surname = models.CharField(max_length=64)
    intro = models.TextField(blank=True)
    available = models.BooleanField(default=False)
    can_be_excluded = models.BooleanField(default=False)
    pools = models.ManyToManyField(Pool, blank=True)

    class Meta:
        verbose_name_plural = "people"

    def __str__(self):
        return "%s (%s)" % (self.name, self.username)

class Round(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    # rounds typically start on a Monday and end on a Friday (5 days later)
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(default=(date.today() + timedelta(days=5)))

    def save(self, *args, **kwargs):
        if not self.pk:
            ask_availability(self)
        super(Round, self).save(*args, **kwargs)

    def __str__(self):
        # example: "Monday, Jan 9, 2019"
        date_format = "%A, %b %-d, %Y"
        return "%s: %s – %s" % (self.pool, 
            self.start_date.strftime(date_format), 
            self.end_date.strftime(date_format))

class Match(models.Model):
    person_1 = models.ForeignKey(Person, on_delete=models.CASCADE, 
        related_name="+")
    person_2 = models.ForeignKey(Person, on_delete=models.CASCADE, 
        related_name="+")
    round = models.ForeignKey(Round, on_delete=models.CASCADE)
    met = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "matches"

    def save(self, *args, **kwargs):
        if not self.pk:
            send_matching_message(self)
        super(MyModel, self).save(*args, **kwargs)

    def __str__(self):
        return "%s ↔ %s for round “%s”" % (self.person_1, self.person_2, self.round)


def ask_availability(round):
    response = client.channels_info(channel=round.pool.channel_id)
    for user_id in response["channel"]["members"]:
        try:
            person = Person.objects.get(user_id=user_id)
        except Person.DoesNotExist:
            user = client.users_info(user=user_id)
            person = Person(user_id=user_id, 
                username=user["user"]["name"], 
                given_name=user["user"]["profile"]["first_name"],
                surname=user["user"]["profile"]["last_name"])
            person.save()
            person.pools.add(obj)
            client.chat_postMessage(channel=user_id, as_user=True,
                text="Introduce yourself, %s" % \
                person.given_name)
    people = Person.objects.filter(pools=round.pool)
    # initially set everyone's availability to False
    people.update(available=False)
    for person in people:
        client.chat_postMessage(channel=person.user_id, as_user=True,
            blocks=[{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Hey %s, want to be matched with an RCG to meet this week?" % person.given_name
                    }
                },
                {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Yes, I want to be matched!"
                        },
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Not this week, maybe later"
                        }
                    }
                ]
            }])


def match(round):
    people_to_match = Person.objects.filter(pool=round.pool, available=True)
    if len(people_to_match) % 2 != 0:
        # we have an odd number of people and need to exclude someone from
        # this round
        person_to_exclude = random.choice(people_to_match.filter(can_be_excluded=True))
        if person_to_exclude is None:
            raise Exception("There are an odd number of people to match this"
                "round, which means somone must be excluded. However, no one "
                "in this pool is marked as a person who can be excluded. "
                "Please select at least one person from this pool who can be "
                "excluded.")
        print("Odd number of people this round, excluding %s", person_to_exclude)
        people_to_match = people_to_match.exclude(person_to_exclude)
    # IMPORTANT: list must have an even length before calling `group` below
    for pair in group(random.shuffle(people_to_match), 2):
        match = Match(person_1=pair[0], person_2=pair[1], round=round)
        match.save()

def send_matching_message(match):
    pass
