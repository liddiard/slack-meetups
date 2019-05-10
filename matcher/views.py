import json

from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

from .models import Pool, Person, Round, Match
from .slack import client


def person(request):
    if request.method == "POST":
        req = json.loads(request.body)
        info = client.channels_info(
            channel="CHFJ2P3DE"
        )
        print(info)
        # response = client.chat_postMessage(
        #     channel="#bot-testing",
        #     text="Hello world!")
        return JsonResponse(req)
        # request.body.person
        # request.body.pool
    elif request.method == "DELETE":
        pass
    else:
        return HttpResponse(status=405) # method not supported

def ask_availability(request):
    if request.method != "POST":
        return HttpResponse(status=405) # method not supported 
    req = json.loads(request.body)
    if not req.pool:
        return HttpResponse(status=400)

def update_availability(request):
    if request.method != "POST":
        return HttpResponse(status=405) # method not supported 
    req = json.loads(request.body)
    if not req.user_id or not req.available:
        return HttpResponse(status=400)
    person = People.objects.get(user_id=user_id)
    person.available = req.available
    person.save()
    # TODO: send slack message asking if you met with your match
    return HttpResponse(204)


def update_met(request):
    if request.method != "POST":
        return HttpResponse(status=405) # method not supported 
    req = json.loads(request.body)
    if not req.match or not req.met:
        return HttpResponse(status=400)
    match = Match.objects.get(req.match)
    match.met = req.met
    # TODO: send slack message acknowledging receipt
    return HttpResponse(204)
    

def update_intro(person, intro):
    pass
