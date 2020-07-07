# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField

from catmaid.models import ClassInstance, Project, Stack
from catmaid.fields import DbDefaultDateTimeField


class Synlinks(models.Model):
    """A synaptic link in the segmentation data, including its pre and post
    location and addition information.
    """

    pre_x = models.FloatField()
    pre_y = models.FloatField()
    pre_z = models.FloatField()
    post_x = models.FloatField()
    post_y = models.FloatField()
    post_z = models.FloatField()
    scores = models.FloatField()
    cleft_scores = models.IntegerField()
    dist = models.FloatField()
    segmentid_pre = models.BigIntegerField(db_index=True)
    segmentid_post = models.BigIntegerField(db_index=True)
    offset = models.IntegerField(db_index=True)
    prob_min = models.IntegerField()
    prob_max = models.IntegerField()
    prob_sum = models.IntegerField()
    prob_mean = models.IntegerField()
    prob_count = models.IntegerField()
    cleft_id = models.BigIntegerField(default=0)
    clust_con_offset = models.IntegerField()


class SynapseImport(models.Model):
    """An import that used an existing skeleton and attached synapses to to it.
    Along with the transaction ID and edition time so that all affected rows can
    be looked up.

    All constraints and indices are created in the migration directly in SQL. We
    don't want Django to interfer there.
    """

    class Status(models.IntegerChoices):
        CREATED = 0
        QUEUED = 1
        COMPUTING = 2
        DONE = 3
        ERROR = 4
        FETCH_PRE_PARTNERS = 5
        FETCH_POST_PARTNERS = 6
        NO_DATA = 7

    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    creation_time = DbDefaultDateTimeField()
    edition_time = DbDefaultDateTimeField()
    # Processing status: computing, done, error. Constraints are defined in
    # database.
    status = models.IntegerField(choices=Status.choices, default=Status.CREATED)
    status_detail = models.TextField(default="")
    runtime = models.FloatField(default=0)
    # This is a hash for the front-end widget this was initiated from. It allows
    # anonymous users to look up results for individual widgets.
    request_id = models.TextField(null=True, blank=True)
    # The skeleton ID after the import along with the number of nodes. This
    # is explicitely no foreign key so that we can easily keep this record when
    # a skeleton is merged or deleted. If needed, it can be retrieved from
    # CATMAID's history.
    skeleton_id = models.BigIntegerField(db_index=True)
    # The number of imported synapses and links.
    n_imported_links = models.IntegerField(blank=True, default=0)
    n_imported_connectors = models.IntegerField(blank=True, default=0)
    # The number of upstream and downstream partners that were imported.
    n_upstream_partners = models.IntegerField(blank=True, default=0)
    n_downstream_partners = models.IntegerField(blank=True, default=0)
    n_expected_upstream_partners = models.IntegerField(blank=True, default=0)
    n_expected_downstream_partners = models.IntegerField(blank=True, default=0)
    # Tags and annotations stored with this import. We don't really need
    # referential integrety here, as this is more of a task description.
    tags = ArrayField(models.TextField(), blank=True, default=list)
    annotations = ArrayField(models.TextField(), blank=True, default=list)

    # Different thresholds
    upstream_partner_syn_threshold = models.IntegerField(default=5)
    downsteam_partner_syn_threshold = models.IntegerField(default=5)
    distance_threshold = models.IntegerField(default=1000)

    # Whether autapses were allowed
    with_autapses = models.BooleanField(default=False)

    # This transaction ID is assigned when the import is actually performed. It
    # allows us to quickly find all database objects that were modified during
    # the actual import.
    txid = models.BigIntegerField(blank=True, null=True)


class SegmentImport(models.Model):
    """An imported segment at a defined location in a particular image stack and
    project. Along with the transaction ID and edition time so that all affected
    rows can be looked up.

    All constraints and indices are created in the migration directly in SQL. We
    don't want Django to interfer there.
    """
    # If this skeleton was imported from an autoseg segment, meta data on this
    # is linked here.
    synapse_import = models.ForeignKey(SynapseImport, on_delete=models.CASCADE,
            db_index=True)
    # A reference to the source of this segment
    source = models.TextField()
    # The imported segment.
    segment_id = models.BigIntegerField(db_index=True)
    n_imported_nodes = models.IntegerField(default=0)
    # The location in the dataset this was computed for.
    voxel_x = models.FloatField()
    voxel_y = models.FloatField()
    voxel_z = models.FloatField()
    # The physical location of the voxel, how it was mapped into CATMAID's space.
    physical_x = models.FloatField()
    physical_y = models.FloatField()
    physical_z = models.FloatField()
