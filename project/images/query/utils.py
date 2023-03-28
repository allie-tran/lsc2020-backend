import json
import os
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import numpy as np
import geopy.distance
import requests
from ..nlp_utils.common import cache, basic_dict, FILES_DIRECTORY

all_images = list(basic_dict.keys())
groups = json.load(open(f"{FILES_DIRECTORY}/group_segments.json"))
scene_segments = {}
for group_name in groups:
    for scene_name, images in groups[group_name]["scenes"]:
        assert "S_" in scene_name, f"{scene_name} is not a valid scene id"
        scene_segments[scene_name] = images
time_info = json.load(open(f"{FILES_DIRECTORY}/backend/time_info.json"))

def get_dict(image):
    if "/" not in image:
        image = f"{image[:6]}/{image[6:8]}/{image}"
    return basic_dict[image]

@cache
def get_date_info(image):
    time = datetime.strptime(get_dict(image)["time"], "%Y/%m/%d %H:%M:%S%z")
    return time.strftime("%A, %d %B %Y")

def get_location(image):
    return get_dict(image)["location"]

def get_gps(images):
    if images:
        if isinstance(images[0], tuple): #images with weights
            images = [image[0] for image in images]
        if isinstance(images[0], str):
            images = [get_dict(image) for image in images]
        sorted_by_time = [image["gps"] for image in sorted(
            images, key=lambda x: x["time"])]
        return sorted_by_time
    return []

def post_request(json_query, index, scroll=False):
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        f"http://localhost:9200/{index}/_search{'?scroll=5m' if scroll else ''}", headers=headers, data=json_query)
    if response.status_code == 200:
        # stt = "Success"
        response_json = response.json()  # Convert to json as dict formatted
        id_images = [[d["_source"], d["_score"]]
                     for d in response_json["hits"]["hits"]]
        scroll_id = response_json["_scroll_id"] if scroll else None
    else:
        print(f'Response status {response.status_code}')
        print(response.text)
        id_images = []
        scroll_id = None

    if not id_images:
        with open("request.log", "a") as f:
            f.write(json_query + '\n')
        # print(json_query)
        print(f'Empty results. Output in request.log')
    return id_images, scroll_id


def post_mrequest(json_query, index):
    headers = {"Content-Type": "application/x-ndjson"}
    response = requests.post(
        f"http://localhost:9200/{index}/_msearch", headers=headers, data=json_query)
    if response.status_code == 200:
        # stt = "Success"
        response_json = response.json()  # Convert to json as dict formatted
        id_images = []
        for res in response_json["responses"]:
            try:
                id_images.append([[d["_source"], d["_score"]]
                            for d in res["hits"]["hits"]])
            except KeyError as e:
                print(res)
                id_images.append([])
    else:
        print(f'Response status {response.status_code}')
        id_images = []

    # with open('request.log', 'w') as f:
        # f.write(json_query + '\n')
    return id_images

def group_scene_results(results, factor="group"):
    size = len(results)
    if size == 0:
        return [], []
    if factor == "group":
        grouped_results = defaultdict(lambda: [])
        for result in results:
            group = result[0]["group"]
            grouped_results[group].append(result)

        results_with_info = []
        scores = []
        for scenes_with_scores in grouped_results.values():
            score = scenes_with_scores[0][1]
            scenes = [res[0] for res in scenes_with_scores]
            new_scenes = []
            for scene in scenes:
                scene["start_time"] = datetime.strptime(scene["start_time"], "%Y/%m/%d %H:%M:%S%z")
                scene["end_time"] = datetime.strptime(scene["end_time"], "%Y/%m/%d %H:%M:%S%z")
                new_scenes.append(scene)
            scenes = new_scenes
            scenes = sorted(scenes, key=lambda x: x["start_time"])
            scores.append(score)
            results_with_info.append({
                "current": [image for scene in scenes for image in scene["images"]],
                "start_time": scenes[0]["start_time"],
                "end_time": scenes[-1]["end_time"],
                "location": scenes[0]["location"] + "\n" + \
                            scenes[0]["country"].capitalize() + "\n" + \
                            datetime.strftime(scenes[0]["start_time"], "%Y/%m/%d"),
                "group": scenes[0]["group"],
                "scene": scenes[0]["scene"]})
        return results_with_info, scores
    return zip(*results.items())
