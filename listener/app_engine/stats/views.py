from datetime import datetime, timedelta

from django.contrib.auth.decorators import user_passes_test
from django.views.generic.simple import direct_to_template
from django.core.urlresolvers import reverse
from django.http import HttpResponse

from google.appengine.ext import db
from google.appengine.api.labs import taskqueue

from app.utils import log
from stats.utils import count
from stats.models import Stats

registered = {}

def intervals(date):
    return [
        ["timestamp >= ", datetime(date.year, date.month, date.day, 0, 0, 0)], 
        ["timestamp <= ", datetime(date.year, date.month, date.day, 23, 59, 59)]
    ]

def start(request):
    date = (datetime.today() - timedelta(days=1)).date()
    create(date)
    return HttpResponse("total started")
    
def create(date):
    existing = Stats.all().filter("date = ", date)
    if not existing:
        stats = Stats()
    else:
        stats = existing[0]
    stats.date = date
    stats.save()
    keys = []
    for key in registered.keys():
        taskqueue.add(url=reverse("stats-action", kwargs={"action":key, "pk":stats.id}))
        keys.append(key)
    data = dict([(key, None) for key in keys])
    stats.set_stats(data)
    stats.save()
    
def get_action(request, action, pk):
    stats = Stats.get(pk)
    current = stats.get_stats()
    if action not in registered:
        raise ValueError, "Action: %s not registered" % action
    current[action] = registered[action](stats)
    stats.set_stats(current)
    stats.save()
    return HttpResponse("total done: %s" % current)

def get_total(stats):
    return count(*intervals(stats.date))

def get_status(stats):
    times = intervals(stats.date)
    return {
        "500":count(("status = ", "500"), *times),
        "404":count(("status = ", "404"), *times),
        "403":count(("status = ", "403"), *times),
    }

registered["total"] = get_total
registered["status"] = get_status

@user_passes_test(lambda u: u.is_staff)
def view(request):
    stats = Stats.all().filter("completed = ", True).order("-date")[:30]
    stats = [ {"object":s, "stats":s.get_stats()} for s in stats ]
    return direct_to_template(request, "stats.html", {
        "stats": stats,
        "nav": {"selected": "stats",}
        })