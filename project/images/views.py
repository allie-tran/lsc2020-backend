import json
import os
import time
from collections import defaultdict

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from images.query import es, es_date, get_gps, get_timeline, get_timeline_group, individual_es, get_multiple_scenes_from_images

saved = defaultdict(lambda: [])
session = None
submit_time = defaultdict(lambda: [])
messages = defaultdict(lambda: {})
last_message = {}


def jsonize(response):
    # JSONize
    response = JsonResponse(response)
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response["Access-Control-Allow-Credentials"] = "true"
    response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
    return response


@csrf_exempt
def restart(request):
    global saved
    global session
    global submit_time
    global messages
    global last_message
    saved = defaultdict(lambda: [])
    session = datetime.strftime(datetime.now(), "%Y%m%d_%H%M%S")
    submit_time = defaultdict(lambda: [])
    messages = defaultdict(lambda: {})
    last_message = {}
    return jsonize({"success": True})


@csrf_exempt
def save(request):
    global saved
    global messages
    global last_message
    query_id = request.GET.get('query_id')
    image = request.GET.get('image_id')
    if image not in saved[query_id]:
        saved[query_id].append(image)
    messages[query_id] = last_message
    return jsonize({"success": True})


@csrf_exempt
def remove(request):
    global saved
    global messages
    global last_message
    query_id = request.GET.get('query_id')
    image = request.GET.get('image_id')
    saved[query_id] = [img for img in saved[query_id] if img != image]
    messages[query_id] = last_message
    return jsonize({"success": True})


@csrf_exempt
def export(request):
    global saved
    global session
    global submit_time
    global messages
    global last_message
    query_id = request.GET.get('query_id')
    time = request.GET.get('time')
    submit_time[query_id] = time
    json.dump({"time": submit_time, "saved": saved},
              open(f'results/{session}.json', 'w'))
    messages[query_id] = last_message
    return jsonize({"success": True})


@csrf_exempt
def images(request):
    # Get message
    message = json.loads(request.body.decode('utf-8'))
    # Calculations
    queryset, scores, info = es(message['query'], message["gps_bounds"])
    response = {'results': queryset[:100], 'info': info}
    return jsonize(response)


@csrf_exempt
def gps(request):
    # Get message
    message = json.loads(request.body.decode('utf-8'))
    # Calculations
    gps = get_gps([message['image']])[0]
    response = {'gps': gps}
    return jsonize(response)

# IMAGE CLEF
@csrf_exempt
def date(request):
    global messages
    global last_message
    # Get message
    message = json.loads(request.body.decode('utf-8'))
    # Calculations
    print(message["starting_from"])
    queryset, size, info  = es_date(message['query'], message["gps_bounds"], message["size"] if "size" in message else 2000, message["starting_from"])
    message["query"]["info"] = info
    last_message = message.copy()
    response = {'results': queryset, 'info': info, 'size': size}
    return jsonize(response)


@csrf_exempt
def get_saved(request):
    global saved
    global messages
    query_id = request.GET.get('query_id')
    message = messages[query_id]
    if message:
        queryset, _ = es_date(message['query'], message["gps_bounds"])
        return jsonize({"saved": saved[query_id], 'results': queryset[:100], 'query': message['query'], 'gps_bounds': message["gps_bounds"]})
    else:
        return jsonize({"saved": saved[query_id], 'results': [], 'query': {}, 'gps_bounds': None})


@csrf_exempt
def timeline_group(request):
    # Get message
    message = json.loads(request.body.decode('utf-8'))
    timeline = get_timeline_group(message['date'])
    response = {'timeline': timeline}
    return jsonize(response)


@csrf_exempt
def timeline(request):
    # Get message
    message = json.loads(request.body.decode('utf-8'))
    timeline, position, group = get_timeline(
        message['images'], message["timeline_type"], message["direction"])
    response = {'timeline': timeline, 'position': position, 'group': group}
    return jsonize(response)


@csrf_exempt
def gpssearch(request):
    # Get message
    message = json.loads(request.body.decode('utf-8'))
    # Calculations
    images = message["scenes"]
    display_type = message["display_type"]
    queryset = es_gps(es, message['query'], images, display_type)
    response = {'results': queryset,
                'error': None}
    return jsonize(response)

@csrf_exempt
def aaron(request):
    query = request.GET.get('query')
    size = request.GET.get('size')
    size = size if size else 2000
    group_factor = request.GET.get('group_factor')
    event_id_start = request.GET.get('event_id_start')
    event_id_end = request.GET.get('event_id_end')
    event_id = request.GET.get('event_id')
    print(f"query: {query}")
    print(f"group_factor: {group_factor}")
    print(f"event_id_start: {event_id_start}")
    print(f"event_id_end: {event_id_end}")
    print(f"event_id: {event_id}")
    if event_id_start or event_id_end:
        if event_id_end is None:
            event_id_end = event_id_start
        elif event_id_start is None:
            event_id_start = event_id_end
        result = get_multiple_scenes_from_images(event_id_start, event_id_end, group_factor=group_factor)
        response = {'results': result}
        return jsonize(response)
    elif event_id:
        result = get_multiple_scenes_from_images(event_id, event_id, group_factor=group_factor)
        response = {'results': result}
        return jsonize(response)
    else:
        # Calculations
        # queryset = individual_es(query, size=2000, group_factor=group_factor)
        (queryset, *_), _  = individual_es(
                query, group_factor=group_factor, size=size, starting_from=0, use_simple_process=True)
        result = [group["current"] for group in queryset]
        response = {'results': result}
        return jsonize(response)
