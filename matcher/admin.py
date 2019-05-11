import random

from django.contrib import admin
import logging

from .models import Pool, Person, Round, Match
from .slack import client
from .utils import group


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    pass


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    pass


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    change_form_template = "round_change_form.html"

    def response_change(self, request, obj):
        if "do-round-matching" in request.POST:
            match(obj)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    pass


def match(round):
    logger.info(f"Starting matching for round \"{round}\" with {len(people_to_match)} participants.")
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
        people_to_match = people_to_match.exclude(person_to_exclude)
        logger.info(f"Odd number of people ({len(people_to_match)}) for round \"{round}\", excluded {person_to_exclude}.")
    # IMPORTANT: list must have an even length before calling `group` below
    for pair in group(random.shuffle(people_to_match), 2):
        match = Match(person_1=pair[0], person_2=pair[1], round=round)
        match.save()
        logger.info(f"Matched: {match}")
    return super().response_change(request, obj)
