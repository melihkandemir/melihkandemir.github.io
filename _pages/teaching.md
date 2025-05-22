---
layout: page
permalink: /teaching/
title: Teaching
description: The reinforcement learning lecture notes took some proofs from Mannor et al., Reinforcement Learning Foundations, and some others from Berstekas & Tsitsiklis, Neuro-Dynamic Programming. The related credit should be given to these authors instead of myself.
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
