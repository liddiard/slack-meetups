import random
import logging
import csv
from datetime import date

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
from django.http import HttpResponse

from .models import Pool, Person, Round, Match
from .utils import group


logger = logging.getLogger(__name__)


class IntroListFilter(admin.SimpleListFilter):
    title = "has intro"
    parameter_name = "has_intro"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(intro="")
        if self.value() == "no":
            return queryset.filter(intro="")


class MatcherAdmin(admin.AdminSite):
    site_header = "Matching administration"
    site_title = "Matching admin"
    index_title = "Bot administration"
    site_url = None


ADMIN_SITE = MatcherAdmin()
admin.site = ADMIN_SITE # register our custom admin site with Django


@admin.register(Pool, site=ADMIN_SITE)
class PoolAdmin(admin.ModelAdmin):
    change_form_template = "pool_change_form.html"
    list_display = ("name", "channel_name")
    search_fields = ("name", "channel_name")

    def response_change(self, request, pool):
        if "download-pool-members" in request.POST:
            return download_pool_members(pool)
        return super().response_change(request, pool)


@admin.register(Person, site=ADMIN_SITE)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("user_name", "full_name", "available", "has_intro",
        "joined")
    list_filter = (IntroListFilter, "available", "pools")
    ordering = ("-joined",)
    search_fields = ("user_name", "full_name", "casual_name")


@admin.register(Round, site=ADMIN_SITE)
class RoundAdmin(admin.ModelAdmin):
    change_form_template = "round_change_form.html"
    list_display = ("pool", "start_date", "end_date")
    list_filter = ("pool",)
    ordering = ("-start_date",)

    def response_change(self, request, round):
        if "do-round-matching" in request.POST:
            match(round)
        return super().response_change(request, round)


@admin.register(Match, site=ADMIN_SITE)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("person_1", "person_2", "get_round_pool",
        "get_round_start_date", "met")
    list_display_links = ("person_1", "person_2")
    list_filter = ("met", "round")
    ordering = ("-round__start_date",)
    search_fields = ("person_1__user_name", "person_2__user_name")

    def get_round_pool(self, match):
        return match.round.pool
    get_round_pool.short_description = "Pool"

    def get_round_start_date(self, match):
        return match.round.start_date
    get_round_start_date.short_description = "Round start date"


# readd the built-in "authentication and authorization" models to our custom
# admin site
# note: it's important to register Users and Groups with their respective 
# admins, otherwise they will be missing important methods like the one to 
# hash User passwords, see: https://stackoverflow.com/a/32852793
admin.site.register(User, UserAdmin)
admin.site.register(Group, GroupAdmin)


def match(round):
    """make random pairings for all participants who've opted in (responded
    saying they're available) for the current round. this function will also
    cause matching messages to be send in each Match.save() call. one person
    won't recieve a Match if there are an odd number of People in the Round.
    """
    # don't rematch if matches already exist for this round
    existing_matches = Match.objects.filter(round=round).count()
    if existing_matches:
        raise Exception(f"{existing_matches} matches already exist for this "
            "round. If you want to rematch, please delete the existing "
            "matches for this round first.")
    # randomly order the people for random matching
    # note: this can be a slow query for large tables
    people_to_match = Person.objects.filter(pools=round.pool, available=True)\
        .order_by("?")
    logger.info(f"Starting matching for round \"{round}\" with "
        f"{len(people_to_match)} participants.")
    if len(people_to_match) % 2 != 0:
        # we have an odd number of people and need to exclude someone from
        # this round
        excludable_people = people_to_match.filter(can_be_excluded=True)
        if not excludable_people:
            raise Exception("There are an odd number of people to match this "
                "round, which means somone must be excluded. However, no one "
                "in this pool is marked as available and as a person who can "
                "be excluded. Please ensure at least one person from this "
                "pool is both available and can be excluded.")
        person_to_exclude = random.choice(excludable_people)
        people_to_match = people_to_match.exclude(id=person_to_exclude.id)
        logger.info(f"Odd number of people ({len(people_to_match)}) for round "
            f"\"{round}\", excluded {person_to_exclude}.")
    # match adjacent people in our randomly-ordered list
    # IMPORTANT: list must have an even length before calling `group` below
    for pair in group(people_to_match, 2):
        match = Match(person_1=pair[0], person_2=pair[1], round=round)
        match.save()
        logger.info(f"Matched: {match}")


def download_pool_members(pool):
    """return an HttpResponse with a CSV file of all the members in the given
    pool
    """
    members = Person.objects.filter(pools=pool)
    response = HttpResponse(content_type='text/csv')
    response["Content-Disposition"] = "attachment; "\
        f"filename=\"{pool.name} members ({date.today()}).csv\""
    writer = csv.writer(response)
    # write a header row describing the columns
    writer.writerow(["User ID", "User name", "Full name", "Has intro"])
    for person in members:
        writer.writerow([person.user_id, person.user_name, person.full_name,
            person.has_intro()])
    return response
