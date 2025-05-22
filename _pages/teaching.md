---
layout: page
permalink: /teaching/
title: Teaching
description: 
nav: true
nav_order: 6
---

<article>

{% assign sorted = site.data.teaching.lectures | sort: "year" | reverse %}
    {% for lecture in sorted %}
        {% if lecture.source_type == 'pdf' %}
            {% include teaching/lecture_pdf.html lecture=lecture %}
        {% endif %}
        {% if lecture.source_type == 'notebook-html' %}
            {% include teaching/lecture_html.html lecture=lecture %}
        {% endif %}


{% endfor %}

</article>
