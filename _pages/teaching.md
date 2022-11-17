---
layout: page
permalink: /teaching/
title: teaching
description: Materials for courses you taught. Replace this text with your description.
nav: true
nav_order: 5
---
<article>

{% assign sorted = site.data.teaching.lectures | sort: "year" | reverse %}
    {% for lecture in sorted %}
    {% include lecture.html lecture=lecture %}
{% endfor %}

</article>