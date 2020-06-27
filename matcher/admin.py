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

from .models import Pool, Person, PoolMembership, Round, Match
from .utils import get_set_element, get_other_person_from_match


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


class AvailabilityListFilter(admin.SimpleListFilter):
    title = "availability for pool"
    parameter_name = "available_for_pool"

    def lookups(self, request, model_admin):
        return tuple((pool.pk, pool.name) for pool in Pool.objects.all())

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        else:
            return queryset.filter(pools=self.value(), poolmembership__available=True)


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
    list_display = ("user_name", "full_name", "has_intro", "joined")
    # "pools" cannot be display as an editable field here because of the
    # custom "through" model on the many-to-many relation
    readonly_fields = ("pools", "joined", "last_query", "last_query_pool")
    list_filter = (IntroListFilter, "pools", AvailabilityListFilter)
    ordering = ("-joined",)
    search_fields = ("user_name", "full_name", "casual_name")


@admin.register(PoolMembership, site=ADMIN_SITE)
class PoolMembershipAdmin(admin.ModelAdmin):
    list_display = ("person", "pool", "available", "get_has_intro")
    list_filter = ("pool", "available")
    search_fields = ("person__user_name", "person__full_name")

    def get_has_intro(self, pool_membership):
        return pool_membership.person.has_intro()
    get_has_intro.short_description = "Has intro"
    get_has_intro.boolean = True


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
    list_filter = ("round__pool", "met")
    ordering = ("-round__start_date",)
    search_fields = ("person_1__user_name", "person_1__full_name",
        "person_2__user_name", "person_2__full_name")

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


def get_round_participants(round):
    """return a randomly-ordered queryset of participants for this Round.
    excludes someone if there are an odd number, and throws and error if no
    one is marked as excludable
    """
    # don't rematch if matches already exist for this round
    existing_matches = Match.objects.filter(round=round).count()
    if existing_matches:
        raise Exception(f"{existing_matches} matches already exist for this "
            "round. If you want to rematch, please delete the existing "
            "matches for this round first.")
    # randomly order the people for "fairer" matching, see `create_matches`
    # function docstring
    # note: this can be a slow query for large tables
    people_to_match = Person.objects\
        .filter(pools=round.pool, poolmembership__available=True)\
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
    return people_to_match


def create_matches(round, people_to_match):
    """given a queryset of people to match, creates matches with a bias toward
    matching people with those they haven't been paired with before (avoiding
    duplicates), where feasible.
    Important considerations:
    - the time complexity of this function is O(N^2) where N is the number of
      participants
    - the space complexity of this function is O(N+M) where N is the number of
      participants and M is the highest number of past matches an individual
      participant has
    - the pairing algorithm may not prevent duplicate pairings in certain
      cases where a "solution" was possible that didn't involve duplicates,
      because such an algorithm would be significantly more complex and have a
      higher time complexity
    - the `people_to_match` passed to this function should be randomly
      ordered. this is due to the fact that people toward the end of the loop
      have a higher chance of receiving a duplicate match because there are
      fewer unmatched people remaining to choose from, and this is a greedy
      algorithm that doesn't backtrack. phrased anothre way, all of the 
      non-duplicate options for matches may have been "used up" in previous
      interations of the loop whne we get to the final few people to match.
    """
    print(f"people to match: {people_to_match}")
    # cast the QuerySet to a Set to avoid mutating the variable over which
    # we'll be iterating
    available_people = set(people_to_match)
    for person in people_to_match:
        if person not in available_people:
            # this person is already matched; do nothing
            print(f"skipping loop for {person}")
            continue

        # remaining people available to match, excluding this person (you
        # can't be matched with yourself)
        potential_matches = available_people - set([person])

        # get the person's past matches, regardless of pool
        past_matches = (Match.objects.filter(person_1=person) |
                        Match.objects.filter(person_2=person))
        past_match_people = {
            get_other_person_from_match(person.user_id, match)
            for match in past_matches
        }

        # set difference; a new set of other people this person hasn't yet met
        nonduplicate_matches = potential_matches - past_match_people
        if nonduplicate_matches:
            # if there are non-duplicate matches available at ths point, match
            # this person with one of them
            potential_matches = nonduplicate_matches
            print(f"non-duplicate matches for {person}: {potential_matches}")
        else:
            # otherwise, match them with anyone still available to match
            logger.warn(f"No non-duplicate matches available for {person}.")
            print(f"duplicate matches for {person}: {potential_matches}")
        # pick an arbitrary person from the available options
        # N.B. this is different than a "random" person in the sense of
        # picking a random element from the set; it's simply the first person
        # pointed to by the set iterator
        other_person = get_set_element(potential_matches)
        print(f"other person for {person}: {other_person}")
        new_match = Match(person_1=person, person_2=other_person, round=round)
        # save the match and send matching messages
        new_match.save()
        # remove both newly matched people from the set of available people to
        # match
        available_people.remove(person)
        available_people.remove(other_person)


def match(round):
    """make pairings for all participants who've opted in (responded saying
    they're available) for the current round. this function will also cause
    matching messages to be send in each Match.save() call. one person won't
    recieve a Match if there are an odd number of People in the Round.
    """
    people_to_match = get_round_participants(round)
    create_matches(round, people_to_match)


def download_pool_members(pool):
    """return an HttpResponse with a CSV file of all the members in the given
    pool
    """
    members = Person.objects.filter(pools=pool)
    response = HttpResponse(content_type='text/csv')
    response["Content-Disposition"] = "attachment; "\
        f"filename=\"{pool.name} members ({date.today()}).csv\""
    writer = csv.writer(response)
    # start with a header row describing the columns
    writer.writerow(["User ID", "User name", "Full name", "Has intro"])
    for person in members:
        writer.writerow([person.user_id, person.user_name, person.full_name,
            person.has_intro()])
    return response
