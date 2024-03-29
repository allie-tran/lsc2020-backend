import json
import os
from .utils import *
from ..nlp_utils.common import FILES_DIRECTORY, basic_dict

TIMELINE_SPAN = 9  # If they want more, submit more
groups = json.load(open(f"{FILES_DIRECTORY}/group_segments.json"))
scene_segments = {}
for group_name in groups:
    for scene_name, images in groups[group_name]["scenes"]:
        assert "S_" in scene_name, f"{scene_name} is not a valid scene id"
        scene_segments[scene_name] = images
time_info = json.load(open(f"{FILES_DIRECTORY}/backend/time_info.json"))


def to_full_key(image):
    return f"{image[:6]}/{image[6:8]}/{image}"

# NEW LSC22
def get_all_scenes(images):
    images = [basic_dict[image]for image in images]
    scene_id = images[0]["scene"]
    group_id = int(images[0]["group"].split('G_')[-1])
    group_results = []
    group_range = range(group_id - 1, group_id + 2)
    group_range = [f"G_{index}" for index in group_range]
    print(group_range)
    line = 0
    done = False
    space = 0
    for group in group_range:
        if group in groups:
            scenes = []
            for scene_name, images in groups[group]["scenes"]:
                scenes.append(
                    (scene_name, images, time_info[scene_name]))
                if scene_id == scene_name:
                    line += (len(scenes) - 1) // 4 + 1
                    done = True
            if scenes:
                if not done:
                    space += 1
                    line += (len(scenes) - 1) // 4 + 1
                group_results.append(
                    (group, groups[group]["location"], scenes))

    print("Line:", line, ", scene_id", scene_id)
    return group_results, line, space, scene_id

def get_more_scenes(group_id, direction="top"):
    group_id = int(group_id.split('G_')[-1])
    group_results = []
    if direction == "bottom":
        group_range = range(group_id + 1, group_id + 3)
    else:
        group_range = range(group_id - 2, group_id)
    line = 0
    space = 0
    group_range = [f"G_{index}" for index in group_range]
    for group in group_range:
        if group in groups:
            scenes = []
            for scene_name, images in groups[group]["scenes"]:
                scenes.append(
                    (scene_name, images, time_info[scene_name]))
            if scenes:
                space += 1
                line += (len(scenes) - 1) // 4 + 1
                group_results.append(
                    (group, groups[group]["location"], scenes))
    return group_results, line, space

def get_full_scene(image):
    scene_id = basic_dict[image]["scene"]
    return [img for img in scene_segments[scene_id]]
