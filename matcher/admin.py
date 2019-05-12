import random

from django.contrib import admin
import logging

from .models import Pool, Person, Round, Match
from .slack import client
from .utils import group


class MatcherAdmin(admin.AdminSite):
    site_header = "Matching administration"
    site_title = "Matching admin"
    index_title = "Bot administration"
    site_url = None


admin_site = MatcherAdmin()
admin.site = admin_site # register our custom admin site with Django


@admin.register(Pool, site=admin_site)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("name", "channel_name")
    search_fields = ("name", "channel_name")


@admin.register(Person, site=admin_site)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("username", "given_name", "surname", "joined", "available")
    list_filter = ("available",)
    ordering = ("-joined",)
    search_fields = ("username", "given_name", "surname")


@admin.register(Round, site=admin_site)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("pool", "start_date", "end_date")
    list_filter = ("pool",)
    ordering = ("-start_date",)
    change_form_template = "round_change_form.html"

    def response_change(self, request, obj):
        if "do-round-matching" in request.POST:
            match(obj)


@admin.register(Match, site=admin_site)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("person_1", "person_2", "round", "met")
    list_filter = ("met", "round")
    ordering = ("-round__start_date",)
    search_fields = ("person_1__username", "person_2__username")


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
