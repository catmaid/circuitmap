# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url

import circuitmap.control

app_name = 'circuitmap'

urlpatterns = [
    url(r'^is-installed$', circuitmap.control.is_installed),
    url(r'^index$', circuitmap.control.index),
    url(r'^test$', circuitmap.control.test),
    url(r'^(?P<project_id>\d+)/synapses/fetch$', circuitmap.control.fetch_synapses),
    url(r'^(?P<project_id>\d+)/imports/$', circuitmap.control.SynapseImportList.as_view()),
    url(r'^(?P<project_id>\d+)/imports/last-update$', circuitmap.control.LastGeneralImportUpdate.as_view()),
    url(r'^(?P<project_id>\d+)/imports/(?P<import_id>\d+)/last-update$', circuitmap.control.LastImportUpdate.as_view()),
    url(r'^(?P<project_id>\d+)/flywire/fetch$', circuitmap.control.fetch_flywire_neuron),
    url(r'^(?P<project_id>\d+)/flywire/partners/fetch$', circuitmap.control.fetch_flywire_neuron_partners),
]
