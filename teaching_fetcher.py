import os
import yaml # pip install pyyaml

config_path = '_config.yml'
with open(config_path, 'r') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

webpage_url = config['url']

data_path = '_data/teaching.yml'

def get_teaching():
    with open(data_path, 'r') as f:
        teaching = yaml.load(f, Loader=yaml.FullLoader)
    return teaching


lectures = get_teaching()['lectures']

for lecture in lectures:

    if 'source_type' not in lectures[1].keys() or lecture['source_type'] != 'notebook-html' or 'schedule' not in lecture.keys():
        continue

    schedule = lecture['schedule']
    title = lecture['title']
    institution = lecture['institution']
    term = lecture['term']
    year = lecture['year']

    for data in schedule:
        week = data['week']
        topic = data['topic']
        html_file = data['file']
        url = data['url']
        md_file =  '_' + url + '.md'
        dir_name = os.path.dirname(md_file)

        base_path = '../' * (len(dir_name.split('/')))

        os.makedirs(dir_name, exist_ok=True)

        with open(md_file, 'w') as f:
            to_write = \
f"""\
---
layout: page
permalink: {url}
title: {title} - {topic}
description: {institution}, {term}, {year}, Week {week}
nav: false
---
<article>

    <iframe src="{base_path}{html_file}" width="100%" height="600"> </iframe>

</article>
"""
            f.write(to_write)

print('Done!')




    

