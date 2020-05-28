from autocorrect import Speller
from nltk import pos_tag
from collections import defaultdict
from ..nlp_utils.common import *
from ..nlp_utils.pos_tag import *
from ..nlp_utils.time import *


init_tagger = Tagger(locations)
e_tag = ElementTagger()


def add_time_query(time_filters, prep, time):
    query = time_es_query(prep, time[0], time[1])
    if query:
        time_filters.add(query)
    return time_filters


def extract_info_from_tag(tag_info):
    objects = set()
    locations = set()
    weekdays = set()
    time_filters = set()
    date_filters = set()
    region = set()
    times = set()
    # loc, split_keywords, info, weekday, month, timeofday,
    for action in tag_info['action']:
        if action.name:
            objects.add(" ".join(action.name))
        if action.in_obj:
            objects.add(" ".join(action.in_obj))
        if action.in_loc:
            locations.add(" ".join(action.in_loc))

    for obj in tag_info['object']:
        for name in obj.name:
            objects.add(name)

    for loc in tag_info['location']:
        for name, info in zip(loc.name, loc.info):
            if info == "REGION":
                region.add(name)
            locations.add(name)

    start = (0, 0)
    end = (24, 0)
    for time in tag_info['time']:
        if time.info == "WEEKDAY":
            weekdays.add(" ".join(time.name))
        elif time.info == "TIMERANGE":
            s, e = " ".join(time.name).split("-")
            start = adjust_start_end("start", start, *am_pm_to_num(s))
            end = adjust_start_end("end", end, *am_pm_to_num(e))
            # time_filters = add_time_query(time_filters, "after", start)
            # time_filters = add_time_query(time_filters, "before", end)
        elif time.info == "TIME":
            if set(time.prep).intersection(["before", "earlier than", "sooner than"]):
                end = adjust_start_end(
                    "end", end, *am_pm_to_num(" ".join(time.name)))
            elif set(time.prep).intersection(["after", "later than"]):
                start = adjust_start_end(
                    "start", start, *am_pm_to_num(" ".join(time.name)))
            else:
                h, m = am_pm_to_num(" ".join(time.name))
                start = adjust_start_end("start", start, h - 1, m)
                end = adjust_start_end("end", end, h + 1, m)
        elif time.info == "DATE":
            y, m, d = get_day_month(" ".join(time.name))
            this_filter = []
            if y:
                this_filter.append(
                    f" (doc['time'].value.getYear() == {y}) ")
            if m:
                this_filter.append(
                    f" (doc['time'].value.getMonthValue() == {m}) ")
            if d:
                this_filter.append(
                    f" (doc['time'].value.getDayOfMonth() == {d}) ")
            date_filters.add(f' ({"&&".join(this_filter)}) ')
        elif time.info == "TIMEOFDAY":
            t = time.name[0]
            if "early" in time.prep:
                if "early; " + time.name[0] in timeofday:
                    t = "early; " + time.name[0]
            elif "late" in time.prep:
                if "late; " + time.name[0] in timeofday:
                    t = "late; " + time.name[0]
            if t in timeofday:
                s, e = timeofday[t].split("-")
                start = adjust_start_end("start", start, *am_pm_to_num(s))
                end = adjust_start_end("end", end, *am_pm_to_num(e))
            else:
                print(t)
        print(time, start, end)
    print("Start:", start, "End:", end)
    time_filters = add_time_query(time_filters, "after", start)
    time_filters = add_time_query(time_filters, "before", end)
    if (end[0] < start[0]) or (end[0] == start[0] and end[1] < start[1]):
        time_filters = [
            f' ({"||".join(time_filters)}) '] if time_filters else []
    else:
        time_filters = [
            f' ({"&&".join(time_filters)}) '] if time_filters else []
    date_filters = [f' ({"||".join(date_filters)}) '] if date_filters else []

    split_keywords = {"descriptions": {"exact": [], "expanded": []},
                      "coco": {"exact": [], "expanded": []},
                      "microsoft": {"exact": [], "expanded": []}}
    objects = objects.difference({""})
    new_objects = set()
    for keyword in objects:
        if keyword not in all_keywords:
            corrected = speller(keyword)
            if corrected in all_keywords:
                print(keyword, '--->', corrected)
                keyword = corrected
        new_objects.add(keyword)
        for kw in microsoft:
            if kw == keyword:
                split_keywords["microsoft"]["exact"].append(kw)
            if intersect(kw, keyword):
                split_keywords["microsoft"]["expanded"].append(kw)
        for kw in coco:
            if kw == keyword:
                split_keywords["coco"]["exact"].append(kw)
            if intersect(kw, keyword):
                split_keywords["coco"]["expanded"].append(kw)
        for kw in all_keywords:
            if kw == keyword:
                split_keywords["descriptions"]["exact"].append(kw)
            if intersect(kw, keyword):
                split_keywords["descriptions"]["expanded"].append(kw)

    return list(new_objects), split_keywords, list(region), list(locations.difference({""})), list(weekdays), time_filters, date_filters


def extract_info_from_sentence(sent):
    sent = sent.replace(', ', ',')
    tense_sent = sent.split(',')

    past_sent = ''
    present_sent = ''
    future_sent = ''

    for current_sent in tense_sent:
        split_sent = current_sent.split()
        if split_sent[0] == 'after':
            past_sent += ' '.join(split_sent) + ', '
        elif split_sent[0] == 'then':
            future_sent += ' '.join(split_sent) + ', '
        else:
            present_sent += ' '.join(split_sent) + ', '

    past_sent = past_sent[0:-2]
    present_sent = present_sent[0:-2]
    future_sent = future_sent[0:-2]

    list_sent = [past_sent, present_sent, future_sent]

    info = {}
    info['past'] = {}
    info['present'] = {}
    info['future'] = {}

    for idx, tense_sent in enumerate(list_sent):
        tags = init_tagger.tag(tense_sent)
        obj = []
        loc = []
        period = []
        time = []
        timeofday = []
        for word, tag in tags:
            if word not in stop_words:
                if tag in ['NN', 'NNS']:
                    obj.append(word)
                if tag in ['SPACE', 'LOCATION']:
                    loc.append(word)
                if tag in ['PERIOD']:
                    period.append(word)
                if tag in ['TIMEOFDAY']:
                    timeofday.append(word)
                if tag in ['TIME', 'DATE', 'WEEKDAY']:
                    time.append(word)
        if idx == 0:
            info['past']['obj'] = obj
            info['past']['loc'] = loc
            info['past']['period'] = period
            info['past']['time'] = time
            info['past']['timeofday'] = timeofday
        if idx == 1:
            info['present']['obj'] = obj
            info['present']['loc'] = loc
            info['present']['period'] = period
            info['present']['time'] = time
            info['present']['timeofday'] = timeofday
        if idx == 2:
            info['future']['obj'] = obj
            info['future']['loc'] = loc
            info['future']['period'] = period
            info['future']['time'] = time
            info['future']['timeofday'] = timeofday

    return info


def extract_info_from_sentence_full_tag(sent):
    # sent = sent.replace(', ', ',')
    # tense_sent = sent.split(';')
    #
    # past_sent = ''
    # present_sent = ''
    # future_sent = ''
    #
    # for current_sent in tense_sent:
    #     split_sent = current_sent.split()
    #     if split_sent[0] == 'after':
    #         past_sent += ' '.join(split_sent) + ', '
    #     elif split_sent[0] == 'then':
    #         future_sent += ' '.join(split_sent) + ', '
    #     else:
    #         present_sent += ' '.join(split_sent) + ', '
    #
    # past_sent = past_sent[0:-2]
    # present_sent = present_sent[0:-2]
    # future_sent = future_sent[0:-2]
    #
    # list_sent = [past_sent, present_sent, future_sent]

    info = {}
    info['past'] = {}
    info['present'] = {}
    info['future'] = {}

    for idx, tense_sent in enumerate(["", sent]):
        if len(tense_sent) > 2:
            tags = init_tagger.tag(tense_sent)
            print(tags)
            info_full = e_tag.tag(tags)
            obj = []
            loc = []
            period = []
            time = []
            timeofday = []

            if len(info_full['object']) != 0:
                for each_obj in info_full['object']:
                    split_term = each_obj.split(', ')
                    if len(split_term) == 2:
                        obj.append(split_term[1])

            if len(info_full['period']) != 0:
                for each_period in info_full['period']:
                    if each_period not in ['after', 'before', 'then', 'prior to']:
                        period.append(each_period)

            if len(info_full['location']) != 0:
                for each_loc in info_full['location']:
                    split_term = each_loc.split('> ')
                    if split_term[0][-3:] != 'not':
                        word_tag = pos_tag(split_term[1].split())
                        final_loc = []
                        for word, tag in word_tag:
                            if tag not in ['DT']:
                                final_loc.append(word)
                        final_loc = ' '.join(final_loc)
                        loc.append(final_loc)

            if len(info_full['time']) != 0:
                for each_time in info_full['time']:
                    if 'from' in each_time or 'to' in each_time:
                        timeofday.append(each_time)
                    else:
                        timetag = init_tagger.time_tagger.tag(each_time)
                        if timetag[-1][1] in ['TIME', 'TIMEOFDAY']:
                            timeofday.append(each_time)
                        elif timetag[-1][1] in ['WEEKDAY', 'DATE']:
                            time.append(timetag[-1][0])

            if idx == 0:
                info['past']['obj'] = obj
                info['past']['loc'] = loc
                info['past']['period'] = period
                info['past']['time'] = time
                info['past']['timeofday'] = timeofday
            if idx == 1:
                info['present']['obj'] = obj
                info['present']['loc'] = loc
                info['present']['period'] = period
                info['present']['time'] = time
                info['present']['timeofday'] = timeofday
            if idx == 2:
                info['future']['obj'] = obj
                info['future']['loc'] = loc
                info['future']['period'] = period
                info['future']['time'] = time
                info['future']['timeofday'] = timeofday

    return info


speller = Speller(lang='en')


def process_query(sent):
    must_not = re.findall(r"-\S+", sent)
    must_not_terms = []
    for word in must_not:
        sent = sent.replace(word, '')
        must_not_terms.append(word.strip('-'))

    tags = init_tagger.tag(sent)
    timeofday = []
    weekday = []
    loc = []
    info = []
    activity = []
    month = []
    region = []
    keywords = []
    print(tags)
    for word, tag in tags:
        if word == "airport":
            activity.append("airplane")
        # if word == "candle":
            # keywords.append("lamp")
        if tag == 'TIMEOFDAY':
            timeofday.append(word)
        elif tag == "WEEKDAY":
            weekday.append(word)
        elif word in ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                      "november", "december"]:
            month.append(word)
        elif tag == "ACTIVITY":
            if word == "driving":
                activity.append("transport")
                info.append("car")
            elif word == "flight":
                activity.append("airplane")
            else:
                activity.append(word)
            keywords.append(word)
        elif tag == "REGION":
            region.append(word)
        elif tag == "KEYWORDS":
            keywords.append(word)
        elif tag in ['NN', 'SPACE', "VBG", "NNS"]:
            if word in ["office", "meeting"]:
                loc.append("work")
            corrected = speller(word)
            if corrected in all_keywords:
                keywords.append(corrected)
            info.append(word)

    print(f"Location: {loc}, weekday: {weekday}, month: {month}, timeofday: {timeofday}, activity: {activity}, region: {region}, must-not: {must_not_terms}")
    print(f"Keywords:", keywords, "Rest:", info)

    split_keywords = {"descriptions": {"exact": [], "expanded": []},
                      "coco": {"exact": [], "expanded": []},
                      "microsoft": {"exact": [], "expanded": []}}

    for keyword in keywords:
        for kw in microsoft:
            if kw == keyword:
                split_keywords["microsoft"]["exact"].append(kw)
            if kw in keyword or keyword in kw:
                split_keywords["microsoft"]["expanded"].append(kw)
        for kw in coco:
            if kw == keyword:
                split_keywords["coco"]["exact"].append(kw)
            if kw in keyword or keyword in kw:
                split_keywords["coco"]["expanded"].append(kw)
        for kw in all_keywords:
            if kw == keyword:
                split_keywords["descriptions"]["exact"].append(kw)
            if kw in keyword or keyword in kw:
                split_keywords["descriptions"]["expanded"].append(kw)

    return loc, split_keywords, info, weekday, month, timeofday, list(set(activity)), list(set(region)), must_not_terms


def process_query2(sent):
    tags = init_tagger.tag(sent)
    tags = e_tag.tag(tags)
    return extract_info_from_tag(tags)


if __name__ == "__main__":
    tags = init_tagger.tag(
        "a flowre in the dedk")
    print(tags)
    tags = e_tag.tag(tags)
    print(tags)
    print(extract_info_from_tag(tags))
