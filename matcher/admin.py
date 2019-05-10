from django.contrib import admin
from django.contrib import admin
from .models import Pool, Person, Round, Match

from .slack import client


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
        # TODO do matching function here
        return super().response_change(request, obj)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    pass
