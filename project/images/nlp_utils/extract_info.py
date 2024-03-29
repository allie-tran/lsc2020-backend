from gensim.models.phrases import Phraser
from gensim.models import Word2Vec
from scipy.spatial.distance import cosine
from nltk import pos_tag
from collections import defaultdict
from ..nlp_utils.common import *
from ..nlp_utils.pos_tag import *
from ..nlp_utils.time import *
import numpy as np
init_tagger = Tagger(locations)
time_tagger = TimeTagger()
e_tag = ElementTagger()

def process_for_ocr(text):
    final_text = defaultdict(lambda : defaultdict(float))
    for word in text:
        final_text[word][word] = 1
        for i in range(0, len(word)-1):
            if len(word[:i+1]) > 1:
                final_text[word][word[:i+1]] += (i+1) / len(word)
            if len(word[i+1:]) > 1:
                final_text[word][word[i+1:]] += 1 - (i+1)/len(word)
    return final_text

def search(wordset, text):
    results = []
    text = " " + text + " "
    for keyword in wordset:
        if keyword:
            if " " + keyword + " " in text:
                results.append(keyword)
            # if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
                # results.append(keyword)
    return results

# Partial match only
def search_possible_location(text):
    results = []
    for location in locations:
        for i, extra in enumerate(locations[location]):
            if re.search(r'\b' + re.escape(extra) + r'\b', text, re.IGNORECASE):
                if extra not in results:
                    results.append(location)
    return results

# gps_location_sets = {location: set([pl for pl in location.lower().replace(',', ' ').split() if pl not in stop_words]) for location, gps in map_visualisation}
gps_not_lower = {}
for loc in locations:
    for origin_doc, (lat, lon) in map_visualisation:
        if loc == origin_doc.lower():
            gps_not_lower[loc] = origin_doc

def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)

class Query:
    def __init__(self, text, shared_filters=None):
        self.negative = ""
        self.disable_region = False
        if "—disable_region" in text:
            print("Disabling region")
            self.disable_region = True
            text = text.replace("—disable_region", "")
        self.disable_location = False
        if "—disable_location" in text:
            print("Disabling location")
            self.disable_location = True
            text = text.replace("—disable_location", "")
        if "NOT" in text:
            text, self.negative = text.split("NOT")
            self.negative = self.negative.strip(". \n").lower()
            self.negative = [word for word in self.negative.split() if word in all_keywords]
        text = text.strip(". \n").lower()
        self.time_filters = None
        self.date_filters = None
        self.driving = False
        self.on_airplane = False
        self.ocr_queries = []
        self.location_queries = []
        self.query_visualisation = defaultdict(list)
        self.location_filters = []
        self.country_to_visualise = []
        self.extract_info(text, shared_filters)

    def extract_info(self, text, shared_filters=None):
        def search_words(wordset):
            return search(wordset, text)
        self.original_text = text

        quoted_text = " ".join(re.findall(r'\"(.+?)\"', text))
        text = text.replace(f'"{quoted_text}"', "")
        if "driving" in text:
            self.driving = True
            text = text.replace("driving", "")
        if "on airplane" in text:
            self.on_airplane = True
            # text = text.replace("on airplane", "")

        self.ocr = process_for_ocr(quoted_text.split())

        if not self.disable_location:
            self.locations = search_words(locations)
            self.place_to_visualise = [gps_not_lower[location] for location in self.locations]
            if self.locations:
                self.query_visualisation["LOCATION"].extend(self.locations)
            else:
                possible_locations = search_possible_location(text)
                if possible_locations:
                    self.query_visualisation["POSSIBLE LOCATION(S)"].extend(possible_locations)
        else:
            self.locations = []
            self.place_to_visualise = []


        print("Locations:", self.locations)
        for loc in self.locations:
            text = rreplace(text, loc, "", 1) #TODO!

        if not self.disable_region:
            self.regions = search_words(regions)
        else:
            self.regions = []

        for reg in self.regions:
            self.query_visualisation["REGION"].append(reg)
            for country in countries:
                if reg == country.lower():
                    self.country_to_visualise.append({"country": country, "geojson": countries[country]})
        for region in self.regions:
            text = rreplace(text, region, "", 1) #TODO!


        # processed = set([w.strip(",.") for word in self.regions +
                        #  self.locations for w in word.split()])
        # if not full_match:
        #     # self.locations.extend(search_words(
        #         # [w for w in ["hotel", "restaurant", "airport", "station", "cafe", "bar", "church"] if w not in self.locations]))
        #     for loc in self.locations[len(self.gps_results):]:
        #         for place, _ in map_visualisation:
        #             if loc in place.lower().split():
        #                 self.place_to_visualise.append(place)

        # if full_match:
        #     for loc in self.locations:
        #         self.query_visualisation["LOCATION"].append(loc)
        # else:
        #     for loc in self.locations:
        #         self.query_visualisation["POSSIBLE LOCATION"].append(loc)

        self.weekdays = []
        self.dates = None
        self.start = (0, 0)
        self.end = (24, 0)

        tags = time_tagger.tag(text)
        processed = set()
        for i, (word, tag) in enumerate(tags):
            if word in processed:
                continue
            if tag in ["WEEKDAY", "TIMERANGE", "TIMEPREP", "DATE", "TIME", "TIMEOFDAY"]:
                processed.add(word)
                # self.query_visualisation["TIME" if "TIME" in tag else tag].append(word)
            if tag == "WEEKDAY":
                self.weekdays.append(word)
            elif tag == "TIMERANGE":
                s, e = word.split("-")
                self.start = adjust_start_end(
                    "start", self.start, *am_pm_to_num(s))
                self.end = adjust_start_end("end", self.end, *am_pm_to_num(e))
            elif tag == "TIME":
                if word in ["2015", "2016", "2018", "2019", "2020"]:
                    self.dates = get_day_month(word)
                else:
                    timeprep = ""
                    if i > 1 and tags[i-1][1] == 'TIMEPREP':
                        timeprep = tags[i-1][0]
                    if timeprep in ["before", "earlier than", "sooner than"]:
                        self.end = adjust_start_end(
                            "end", self.end, *am_pm_to_num(word))
                    elif timeprep in ["after", "later than"]:
                        self.start = adjust_start_end(
                            "start", self.start, *am_pm_to_num(word))
                    else:
                        h, m = am_pm_to_num(word)
                        self.start = adjust_start_end(
                            "start", self.start, h - 1, m)
                        self.end = adjust_start_end("end", self.end, h + 1, m)
            elif tag == "DATE":
                self.dates = get_day_month(word)
            elif tag == "TIMEOFDAY":
                if word not in ["lunch", "breakfast", "dinner", "sunrise", "sunset"]:
                    processed.add(word)
                # self.query_visualisation["TIME" if "TIME" in tag else tag].append(word)
                timeprep = ""
                if i > 1 and tags[i-1][1] == 'TIMEPREP':
                    timeprep = tags[i-1][0]
                if "early" in timeprep:
                    if "early; " + word in timeofday:
                        word = "early; " + word
                elif "late" in timeprep:
                    if "late; " + word in timeofday:
                        word = "late; " + word
                if word in timeofday:
                    s, e = timeofday[word].split("-")
                    self.start = adjust_start_end(
                        "start", self.start, *am_pm_to_num(s))
                    self.end = adjust_start_end(
                        "end", self.end, *am_pm_to_num(e))
                else:
                    print(
                        word, f"is not a registered time of day ({timeofday})")
        print(processed)
        print(tags)
        if shared_filters:
            if not self.weekdays:
                self.weekdays.extend(shared_filters.weekdays)
            if self.dates is None:
                self.dates = shared_filters.dates
        unprocessed = [(word, tag) for (word, tag) in tags if word not in processed]

        last_non_prep = 0
        self.clip_text = ""
        for i in range(1, len(unprocessed)  + 1):
            if unprocessed[-i][1] not in ["DT", "IN"] and unprocessed[-i][0] not in stop_words:
                last_non_prep = i
                break
        if last_non_prep > 1:
            self.clip_text = " ".join([word for word, tag in unprocessed[:-(last_non_prep - 1)]])
        else:
            self.clip_text = " ".join(
                [word for word, tag in unprocessed])
        self.clip_text = self.clip_text.strip(", ")
        print("CLIP:", self.clip_text)
        # self.query_visualisation[self.clip_text] = "CLIP"

    def get_info(self):
        return {"query_visualisation": [(hint, ", ".join(value)) for hint, value in self.query_visualisation.items()],
                "country_to_visualise": self.country_to_visualise,
                "place_to_visualise": self.place_to_visualise}

    def time_to_filters(self):
        if not self.time_filters:
            # Time
            s, e = self.start[0], self.end[0]
            if s > e: # TODO!
                s, e = e, 24
            self.time_filters = {
                                    "range":
                                    {
                                        "hour":
                                        {
                                            "gte": s,
                                            "lte": e
                                        }
                                    }
                                }

            # Date
            self.date_filters = []
            if self.dates:
                y, m, d = self.dates
                if y:
                    self.date_filters.append({"term": {"year": str(y)}})
                if m:
                    self.date_filters.append(
                        {"term": {"month": str(m).rjust(2, "0")}})
                if d:
                    self.date_filters.append(
                        {"term": {"date": str(d).rjust(2, "0")}})
            if self.start[0] != 0 and self.end[0] != 24:
                self.query_visualisation["TIME"] = [f"{self.start[0]}:00 - {self.end[0]}:00"]
            if str(self.dates) != "None":
                self.query_visualisation["DATE"] = [str(self.dates)]
        return self.time_filters, self.date_filters

    def make_ocr_query(self):
        if not self.ocr_queries:
            self.ocr_queries = []
            for ocr_word in self.ocr:
                dis_max = []
                for ocr_word, score in self.ocr[ocr_word].items():
                    dis_max.append(
                        {"rank_feature": {"field": f"ocr_score.{ocr_word}", "boost": 200 * score, "linear": {}}})
                self.ocr_queries.append({"dis_max": {
                    "queries": dis_max,
                    "tie_breaker": 0.0}})
        return self.ocr_queries
        #TODO: multiple word in OCR

    def make_location_query(self):
        if not self.location_filters:
            for loc in self.locations:
                place = gps_not_lower[loc]
                place = gps_not_lower[loc]
                dist = "0.5km"
                pivot = "5m"
                if "airport" in loc or "home" in loc:
                    dist = "2km"
                    pivot = "200m"
                elif "dcu" in loc:
                    dist = "1km"
                    pivot = "100m"

                for place_iter, (lat, lon) in map_visualisation:
                    if place == place_iter:
                        # self.location_queries.append({
                        #         "distance_feature": {
                        #             "field": "gps",
                        #             "pivot": pivot,
                        #             "origin": [lon, lat],
                        #             "boost": score * 50
                        #         }
                        #     })
                        self.location_filters.append({
                            "geo_distance": {
                                "distance": dist,
                                "gps": [lon, lat]
                            }
                        })
                        break

            # # General:
            # if len(self.gps_results) < len(self.locations):
            #     for loc in self.locations[len(self.gps_results):]:
            #         loc_set = set(loc.split())
            #         for place, (lat, lon) in map_visualisation:
            #             set_place = gps_location_sets[place]
            #             if loc_set.issubset(set_place):
            #                 pivot = "5m"
            #                 if "airport" in set_place:
            #                     pivot = "200m"
            #                     self.location_filters.append({
            #                         "geo_distance": {
            #                             "distance": "2km",
            #                             "gps": [lon, lat]
            #                         }
            #                     })
            #                 elif "dcu" in set_place:
            #                     pivot = "100m"

            #                 self.location_queries.append({
            #                     "distance_feature": {
            #                         "field": "gps",
            #                         "pivot": pivot,
            #                         "origin": [lon, lat],
            #                         "boost": len(loc_set) / len(set_place) * 50
            #                     }
            #                 })
        # if self.location_queries:
            # return {"dis_max": {"queries": self.location_queries, "tie_breaker": 0.0}}
        return self.location_filters
