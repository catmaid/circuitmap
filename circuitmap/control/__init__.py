# -*- coding: utf-8 -*-
"""Methods called by API endpoints"""
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.db import connection
from django.utils.decorators import method_decorator

import numpy as np
import pandas as pd
import scipy.spatial as sp
import fafbseg
import networkx as nx
import sqlite3
import logging
from timeit import default_timer as timer

from cloudvolume import CloudVolume
from cloudvolume.datasource.precomputed.skeleton.sharded import ShardedPrecomputedSkeletonSource

from celery.task import task
from celery.utils.log import get_task_logger

from .settings import *
from circuitmap import CircuitMapError
from circuitmap.models import SynapseImport, SegmentImport
from django.conf import settings

from catmaid.control.common import get_request_bool, get_request_list
from catmaid.consumers import msg_user
from catmaid.models import Message, User, UserRole
from catmaid.control.message import notify_user
from catmaid.control.authentication import requires_user_role

cv = CloudVolume(CLOUDVOLUME_URL, use_https=True, parallel=False)
cv.meta.info['skeletons'] = CLOUDVOLUME_SKELETONS
cv.skeleton.meta.refresh_info()
cv.skeleton = ShardedPrecomputedSkeletonSource(cv.skeleton.meta, cv.cache, cv.config)

cols = ["id", "pre_x","pre_y","pre_z","post_x","post_y","post_z","scores",
            "cleft_id","cleft_scores","clust_con_offset","dist","offset",
            "prob_count","prob_max","prob_mean","prob_min","prob_sum",
            "segmentid_post","segmentid_pre"]

task_logger = get_task_logger(__name__)


def get_links(cursor, segment_id, where='segmentid_pre', table='circuitmap_synlinks'):
    #print('execute')
    query = 'SELECT * from {} where {} = {};'.format(table, where, segment_id)
    cursor.execute(query)
    #print('fetch all')
    pre_links = cursor.fetchall()
    #print('fetch from db done')
    return pd.DataFrame.from_records(pre_links, columns=cols)


def get_links_from_offset(cursor, offsets, table='circuitmap_synlinks'):
    #print('execute')
    cursor.execute('SELECT * from {} where "offset" in ({});'.format(table, ','.join(map(str,offsets))))
    #print('fetch all')
    pre_links = cursor.fetchall()
    #print('fetch from db done')
    return pd.DataFrame.from_records(pre_links, columns=cols)


def load_subgraph(cursor, start_segment_id, order = 0):
    """ Return a NetworkX graph with segments as nodes and synaptic connection
    as edges with synapse counts

    start_segment_id: starting segment for subgraph loading

    order: number of times to expand along edges
    """
    fetch_segments = set([start_segment_id])
    fetched_segments = set()
    g = nx.DiGraph()

    for ordern in range(order+1):
        task_logger.debug(f'order {ordern} need to fetch {len(fetch_segments)} segments')
        for i, segment_id in enumerate(list(fetch_segments)):

            task_logger.debug(f'process segment {i} with segment_id {segment_id}')

            task_logger.debug('retrieve pre_links')
            pre_links = get_links(cursor, segment_id, where='segmentid_pre')

            task_logger.debug('retrieve post_links')
            post_links = get_links(cursor, segment_id, where='segmentid_post')

            task_logger.debug('build graph ...')

            task_logger.debug(f'number of pre_links {len(pre_links)}')
            for idx, r in pre_links.iterrows():
                from_id = int(r['segmentid_pre'])
                to_id = int(r['segmentid_post'])
                if g.has_edge(from_id,to_id):
                    ed = g.get_edge_data(from_id,to_id)
                    ed['count'] += 1
                else:
                    g.add_edge(from_id, to_id, count= 1)

            task_logger.debug(f'number of post_links {len(post_links)}')
            for idx, r in post_links.iterrows():
                from_id = int(r['segmentid_pre'])
                to_id = int(r['segmentid_post'])
                if g.has_edge(from_id,to_id):
                    ed = g.get_edge_data(from_id,to_id)
                    ed['count'] += 1
                else:
                    g.add_edge(from_id, to_id, count= 1)

            fetched_segments.add(segment_id)

            if len(pre_links) > 0:
                all_postsynaptic_segments = set(pre_links['segmentid_post'])
                fetch_segments = fetch_segments.union(all_postsynaptic_segments)

            if len(post_links) > 0:
                all_presynaptic_segments = set(post_links['segmentid_pre'])
                fetch_segments = fetch_segments.union(all_presynaptic_segments)

        # remove all segments that were already fetched
        fetch_segments = fetch_segments.difference(fetched_segments)

        # always remove 0
        if 0 in fetch_segments:
            fetch_segments.remove(0)

    return g

def get_presynaptic_skeletons(g, segment_id, synaptic_count_threshold = 0):
    res = set()
    for nid in g.predecessors(segment_id):
        if nid == segment_id or nid == 0:
            continue
        ed = g.get_edge_data(nid, segment_id)
        if ed['count'] > synaptic_count_threshold:
            res.add(nid)
    return list(res)


def get_postsynaptic_skeletons(g, segment_id, synaptic_count_threshold = 0):
    res = set()
    for nid in g.successors(segment_id):
        if nid == segment_id or nid == 0:
            continue
        ed = g.get_edge_data(segment_id, nid)
        if ed['count'] > synaptic_count_threshold:
            res.add(nid)
    return list(res)


@api_view(['GET'])
def get_neighbors_graph(request, segment_id):
    cur = connection.cursor()
    g = load_subgraph(cur, segment_id, order = 0)
    from networkx.readwrite import json_graph
    return JsonResponse({'graph': json_graph.node_link_data(g)})


@api_view(['GET'])
def get_synapses(request, segment_id):
    cur = connection.cursor()

    task_logger.debug('retrieve pre_links')
    pre_links = get_links(cursor, segment_id, where='segmentid_pre')

    task_logger.debug('retrieve post_links')
    post_links = get_links(cursor, segment_id, where='segmentid_post')

    return JsonResponse({'pre_links': pre_links.to_json(), 'post_links': post_links.to_json()})


@api_view(['GET'])
def is_installed(request, project_id=None):
    """Check whether the extension circuitmap is installed."""
    return JsonResponse({'is_installed': True, 'msg': 'circuitmap is installed'})

@api_view(['GET'])
def index(request, project_id=None):
    return JsonResponse({'version': '0.1', 'app': 'circuitmap'})

@api_view(['GET'])
def test(request, project_id=None):
    task = testtask.delay()
    return JsonResponse({'msg': 'testtask'})

@task()
def testtask():
    task_logger.info('testtask')


@api_view(['POST'])
def fetch_synapses(request: HttpRequest, project_id=None):
    x = int(round(float(request.POST.get('x', -1))))
    y = int(round(float(request.POST.get('y', -1))))
    z = int(round(float(request.POST.get('z', -1))))

    fetch_upstream = get_request_bool(request.POST, 'fetch_upstream', False)
    fetch_downstream = get_request_bool(request.POST, 'fetch_downstream', False)
    with_autapses = get_request_bool(request.POST, 'with_autapses', False)
    distance_threshold = int(request.POST.get('distance_threshold', 1000 ))
    active_skeleton_id = int(request.POST.get('active_skeleton', -1 ))
    upstream_syn_count = int(request.POST.get('upstream_syn_count', 5 ))
    downstream_syn_count = int(request.POST.get('downstream_syn_count', 5 ))
    annotations = [a.strip() for a in get_request_list(request.POST, 'annotations', [])]
    tags = [a.strip() for a in get_request_list(request.POST, 'tags', [])]

    request_id = request.POST.get('request_id')

    pid = int(project_id)

    if x == -1 or y == -1 or z == -1:
        raise ValueError(f"Invalid location coordinate: ({x}, {y}, {z})")

    msg_payload = {
        'request_id': request_id,
    }

    status = dict()
    if active_skeleton_id == -1:

        msg_payload['task'] = 'import-location'
        msg_payload['x'], msg_payload['y'], msg_payload['z'] = x, y, z

        voxel_x, voxel_y, voxel_z = x//2, y//2, z

        # look up segment id at location and fetch synapses
        try:
            segment_id = int(cv[voxel_x,voxel_y,voxel_z,0][0][0][0][0])
        except Exception as ex:
            task_logger.debug('Exception occurred: {}'.format(ex))
            segment_id = None
            raise CircuitMapError(f"No segment found at stack location ({x}, {y}, {z}). Error: {ex}")

        if segment_id is None or segment_id == 0:
            raise CircuitMapError(f"No segment found at stack location ({x}, {y}, {z})")
        else:
            # Create result entry
            synapse_import = SynapseImport.objects.create(user=request.user,
                    project_id=pid, request_id=request_id,
                    skeleton_id=-1, status=SynapseImport.Status.QUEUED,
                    upstream_partner_syn_threshold=upstream_syn_count,
                    downsteam_partner_syn_threshold=downstream_syn_count,
                    distance_threshold=distance_threshold,
                    with_autapses=with_autapses)
            segment_import = SegmentImport.objects.create(
                    synapse_import=synapse_import, segment_id=segment_id,
                    source=CLOUDVOLUME_URL,
                    voxel_x=voxel_x, voxel_y=voxel_y, voxel_z=voxel_z,
                    physical_x=x, physical_y=y, physical_z=z)

            import_synapses_and_segment.delay(pid, request.user.id,
                    synapse_import.id, segment_id, fetch_upstream,
                    fetch_downstream, upstream_syn_count, downstream_syn_count,
                    True, msg_payload, with_autapses, annotations, tags)


            return JsonResponse({
                'project_id': pid,
                'segment_id': str(segment_id),
                'import_ref': synapse_import.id
            })
    else:
        # Create result entry
        synapse_import = SynapseImport.objects.create(user=request.user,
                project_id=pid, request_id=request_id,
                skeleton_id=active_skeleton_id,
                status=SynapseImport.Status.QUEUED,
                upstream_partner_syn_threshold=upstream_syn_count,
                downsteam_partner_syn_threshold=downstream_syn_count,
                distance_threshold=distance_threshold,
                with_autapses=with_autapses)

        # fetch synapses for manual skeleton
        import_synapses_for_existing_skeleton.delay(pid, request.user.id,
            synapse_import.id, distance_threshold, active_skeleton_id, None,
            True, msg_payload, with_autapses, annotations=annotations, tags=tags)

        return JsonResponse({
            'project_id': pid,
            'import_ref': synapse_import.id,
        })


@task
def import_synapses_and_segment(project_id, user_id, import_id, segment_id,
        fetch_upstream, fetch_downstream, upstream_syn_count,
        downstream_syn_count, message_user=True, message_payload=None,
        with_autapses=False, annotations=None, tags=None):

    start_time = timer()

    message_payload['task'] = 'import-location-partners'
    task_logger.debug('task: import_synapses_and_segment')
    task_logger.debug('call: import_autoseg_skeleton_with_synapses')
    seg_import_task = import_autoseg_skeleton_with_synapses(project_id,
            user_id, import_id, segment_id, message_user, message_payload,
            with_autapses, annotations=annotations, tags=tags)

    task_logger.debug('call: import_upstream_downstream_partners')
    partner_import_task = import_upstream_downstream_partners(project_id,
            user_id, import_id, segment_id, fetch_upstream, fetch_downstream,
            upstream_syn_count, downstream_syn_count, message_user, message_payload,
            with_autapses, annotations=annotations, tags=tags)

    # Only attempt to load import data after the processing is done to not
    # override the newly createad state.
    synapse_import = SynapseImport.objects.get(id=import_id)
    if synapse_import.status != SynapseImport.Status.ERROR:
        synapse_import.status = SynapseImport.Status.DONE
    synapse_import.runtime = timer() - start_time
    synapse_import.save()
    task_logger.debug('task: import_synapses_and_segment: done')

@task()
def import_upstream_downstream_partners(project_id, user_id, import_id, segment_id,
        fetch_upstream, fetch_downstream, upstream_syn_count,
        downstream_syn_count, message_user=True, message_payload=None,
        with_autapses=False, annotations=None, tags=None):
    error = None
    n_upstream_partners = 0
    n_downstream_partners = 0
    try:
        task_logger.info(f'task: import_upstream_downstream_partners start {segment_id}')

        # get all partners partners
        cur = connection.cursor()

        task_logger.debug('load subgraph')
        g = load_subgraph(cur, segment_id)

        task_logger.debug('start fetching ...')
        n_upstream_partners = 0
        if fetch_upstream:
            upstream_partners = get_presynaptic_skeletons(g, segment_id, synaptic_count_threshold = upstream_syn_count)
            n_upstream_partners = len(upstream_partners)
            for partner_segment_id in upstream_partners:
                task_logger.debug(f'spawn task for presynaptic segment_id {partner_segment_id}')
                task = import_autoseg_skeleton_with_synapses.delay(pid, user_id,
                        import_id, partner_segment_id, False,
                        with_autapses=with_autapses, set_status=False,
                        annotations=annotations, tags=tags)

        n_downstream_partners = 0
        if fetch_downstream:
            downstream_partners = get_postsynaptic_skeletons(g, segment_id, synaptic_count_threshold = downstream_syn_count)
            n_downstream_partners = len(downstream_partners)
            for partner_segment_id in downstream_partners:
                task_logger.debug(f'spawn task for postsynaptic segment_id {partner_segment_id}')
                task = import_autoseg_skeleton_with_synapses.delay(pid, user_id,
                        import_id, partner_segment_id, False,
                        with_autapses=with_autapses, set_status=False,
                        annotations=annotations, tags=tags)

        if message_user:
            payload = {
                'task': 'import-partner-fragments',
                'segment_id': segment_id,
                'n_upstream_partners': n_upstream_partners,
                'n_downstream_partners': n_downstream_partners,
            }
            if message_payload:
                payload.update(message_payload)
            msg_user(user_id, 'circuitmap-update', payload)

    except Exception as ex:
        error = ex
        task_logger.error(f'Exception import_upstream_downstream_partners: {ex}')

    if message_user:
        partners = []
        if fetch_downstream:
            partners.append('downstream')
        if fetch_upstream:
            partners.append('upstream')
        user = User.objects.get(pk=user_id)
        msg = Message()
        msg.user = user
        msg.read = False
        if error:
            msg.title = f"Error while importing {' and '.join(partners)} partners for skeleton/fragment #{segment_id}"
            msg.text = f"No partners could be created due to the following error: {error}"
            msg.action = ""
        else:
            msg.title = f"Synapses imported for skeleton #{segment_id}"
            msg.title = f"Imported {' and '.join(partners)} partners for skeleton/fragment #{segment_id}"
            msg.text = (f"Imported {n_upstream_partners} upstream partners and " +
                "{n_downstream_partners} partners for skeleton/fragment #{segment_id}")
            msg.action = f"?pid={project_id}&active_skeleton_id={segment_id}&tool=tracingtool"
        msg.save()

        notify_user(user.id, msg.id, msg.title)

        payload = {
            'task': 'import-partner-fragments',
            'segment_id': segment_id,
            'n_upstream_partners': n_upstream_partners,
            'n_downstream_partners': n_downstream_partners,
        }
        if error:
            payload['error'] = str(error)
        if message_payload:
            payload.update(message_payload)
        task_logger.debug(f'{user_id} {payload}')
        msg_user(user_id, 'circuitmap-update', payload)


#Code like this might be needed for make it work with RabbitMQ:
#@task()
#def import_synapses_for_existing_skeleton(project_id, user_id, distance_threshold, active_skeleton_id,
#        autoseg_segment_id = None, message_user=True, message_payload=None):
#    asyncio.run(import_synapses_for_existing_skeleton(project_id, user_id,
#            distance_threshold, active_skeleton_id, autoseg_segment_id,
#            message_user, message_payload))
#
#async def _import_synapses_for_existing_skeleton(project_id, user_id, distance_threshold, active_skeleton_id,

@task()
def import_synapses_for_existing_skeleton(project_id, user_id, import_id,
        distance_threshold, active_skeleton_id, autoseg_segment_id = None,
        message_user=True, message_payload=None, with_autapses=False,
        set_status=True, annotations=None, tags=None):
    """Find and import all synapses for the existing skeleton. If status is
    provided.
    """
    task_logger.debug('task: import_synapses_for_existing_skeleton started')
    error = None
    connectors = {}
    treenode_connector = {}
    start_time = timer()

    synapse_import = None
    try:
        # Set status to computing
        synapse_import = SynapseImport.objects.get(id=import_id)
        synapse_import.status = SynapseImport.Status.COMPUTING
        synapse_import.save()

        # retrieve skeleton with all nodes directly from the database
        cursor = connection.cursor()
        cursor.execute('''
            SELECT t.id, t.parent_id, t.location_x, t.location_y, t.location_z
            FROM treenode t
            WHERE t.skeleton_id = %s AND t.project_id = %s
            ''', (int(active_skeleton_id), int(project_id)))

        # convert record to pandas data frame
        skeleton = pd.DataFrame.from_records(cursor.fetchall(),
            columns=['id', 'parent_id', 'x', 'y', 'z'])

        task_logger.debug(f'skeleton shape {len(skeleton)}')

        # accessing the most recent autoseg data
        fafbseg.use_google_storage(GOOGLE_SEGMENTATION_STORAGE)
        task_logger.debug(f'Using google storage {GOOGLE_SEGMENTATION_STORAGE}')

        if not autoseg_segment_id is None:
            task_logger.debug('active skeleton {} is derived from segment id {}'.format(active_skeleton_id, autoseg_segment_id))
            overlapping_segmentids = set([int(autoseg_segment_id)])
        else:
            # retrieve segment ids
            task_logger.debug('getting autoseg segments')
            segment_ids = fafbseg.segmentation.get_seg_ids(skeleton[['x','y','z']])

            task_logger.debug(f'found segment ids for skeleton: {segment_ids}')

            overlapping_segmentids = set()
            for seglist in segment_ids:
                for s in seglist:
                    overlapping_segmentids.add(s)
            task_logger.debug(f'found {len(overlapping_segmentids)} overlapping segments')

            # Debug: explicitly remove segments with ID=0, because there seem
            # to be problems with the data.
            if hasattr(settings, 'CIRCUITMAP_IGNORED_SEGMENT_IDS'):
                overlapping_segmentids = overlapping_segmentids - set(settings.CIRCUITMAP_IGNORED_SEGMENT_IDS)
                task_logger.debug(f'Removed segments with the following IDs: {settings.CIRCUITMAP_IGNORED_SEGMENT_IDS}')

        # store skeleton in kdtree for fast distance computations
        tree = sp.KDTree( skeleton[['x', 'y', 'z']] )
        task_logger.debug('KD tree built for skeleton')

        all_pre_links = []
        all_post_links = []

        cur = connection.cursor()

        # retrieve synaptic links for each autoseg skeleton
        # todo: list shouldn't be needed
        task_logger.debug('iterating overlapping segments')
        for segment_id in overlapping_segmentids:
            task_logger.debug(f'process segment: {segment_id}')
            all_pre_links.append(get_links(cur, segment_id, 'segmentid_pre'))
            all_post_links.append(get_links(cur, segment_id, 'segmentid_post'))

        all_pre_links_concat = pd.concat(all_pre_links)
        all_post_links_concat = pd.concat(all_post_links)

        task_logger.debug(f'total nr prelinks collected: {len(all_pre_links_concat)}')
        task_logger.debug(f'total nr postlinks collected: {len(all_post_links_concat)}')

        # for all pre/post links, if clust_con_offset > 0, retrieve the respective
        # links and use the presynaptic location as representative location for the link
        tmp_list = all_pre_links_concat[all_pre_links_concat['clust_con_offset']>0]['clust_con_offset'].tolist()
        if len(tmp_list) == 0:
            all_pre_links_concat_remap_connector = None
        else:
            all_pre_links_concat_remap_connector = get_links_from_offset(cursor, tmp_list)
            all_pre_links_concat_remap_connector = all_pre_links_concat_remap_connector.set_index('offset')
            task_logger.debug(f'total nr representative prelinks collected: {len(all_pre_links_concat_remap_connector)}')

        tmp_list = all_post_links_concat[all_post_links_concat['clust_con_offset']>0]['clust_con_offset'].tolist()
        if len(tmp_list) == 0:
            all_post_links_concat_remap_connector = None
        else:
            all_post_links_concat_remap_connector = get_links_from_offset(cursor, tmp_list)
            all_post_links_concat_remap_connector = all_post_links_concat_remap_connector.set_index('offset')
            task_logger.debug(f'total nr representative postlinks collected: {len(all_post_links_concat_remap_connector)}')

        # Faciltate autapse checking
        seen_skeleton_connectors_links = set()

        if len(all_pre_links_concat) > 0:
            task_logger.debug('find closest distances to skeleton for pre')
            res = tree.query(all_pre_links_concat[['pre_x','pre_y', 'pre_z']])
            all_pre_links_concat['dist2'] = res[0]
            all_pre_links_concat['skeleton_node_id_index'] = res[1]

            for idx, r in all_pre_links_concat.iterrows():
                # skip link if beyond distance threshold
                if distance_threshold >= 0 and r['dist2'] > distance_threshold:
                    continue
                if r['segmentid_pre'] == r['segmentid_post']:
                    # skip selflinks
                    continue

                skid = int(skeleton.loc[r['skeleton_node_id_index']]['id'])

                # if representative presynaptic location found, use it
                if r['clust_con_offset'] > 0 and not all_pre_links_concat_remap_connector is None:
                    l = all_pre_links_concat_remap_connector.loc[r['clust_con_offset']]
                    connector_id = CONNECTORID_OFFSET + int(r['clust_con_offset']) * 10
                    task_logger.debug('found representative connector (prelink) {} for skid {}'.format(connector_id, skid))
                    if not connector_id in connectors:
                        connectors[connector_id] = l.to_dict()
                else:
                    # otherwise, use presynaptic location of link instead
                    connector_id = CONNECTORID_OFFSET + int(r['offset']) * 10
                    if not connector_id in connectors:
                        connectors[connector_id] = r.to_dict()

                # add treenode_connector link
                treenode_connector[ \
                    (skid, connector_id)] = {'type': 'presynaptic_to'}

                # remember skeleton link
                if not with_autapses:
                    seen_skeleton_connectors_links.add((active_skeleton_id, connector_id))

        if len(all_post_links_concat) > 0:
            task_logger.debug('find closest distances to skeleton for post')
            res = tree.query(all_post_links_concat[['post_x','post_y', 'post_z']])
            all_post_links_concat['dist2'] = res[0]
            all_post_links_concat['skeleton_node_id_index'] = res[1]

            for idx, r in all_post_links_concat.iterrows():
                # skip link if beyond distance threshold
                if distance_threshold >= 0 and r['dist2'] > distance_threshold:
                    continue
                if r['segmentid_pre'] == r['segmentid_post']:
                    # skip selflinks
                    continue

                skid = int(skeleton.loc[r['skeleton_node_id_index']]['id'])

                # if representative presynaptic location found, use it
                if r['clust_con_offset'] > 0 and not all_post_links_concat_remap_connector is None:
                    l = all_post_links_concat_remap_connector.loc[r['clust_con_offset']]
                    connector_id = CONNECTORID_OFFSET + int(r['clust_con_offset']) * 10
                    task_logger.debug('found representative connector (postlink) {} for skid {}'.format(connector_id, skid))
                    if not connector_id in connectors:
                        connectors[connector_id] = l.to_dict()
                else:
                    connector_id = CONNECTORID_OFFSET + int(r['offset']) * 10
                    if not connector_id in connectors:
                        connectors[connector_id] = r.to_dict()
                # skip post links that form autapses
                if (active_skeleton_id, connector_id) in seen_skeleton_connectors_links:
                    task_logger.debug(f'skipping autapse: {active_skeleton_id}, {connector_id}')
                    continue
                # add treenode_connector link
                treenode_connector[ \
                    (skid, connector_id)] = {'type': 'postsynaptic_to'}

        # insert into database
        task_logger.debug('fetch relations')
        cursor.execute("SELECT id,relation_name from relation where project_id = {project_id};".format(project_id=project_id))
        res = cursor.fetchall()
        relations = dict([(v,u) for u,v in res])

        with_multi = True
        queries = []
        query = 'BEGIN;'
        if with_multi:
            queries.append(query)
        else:
            cursor.execute(query)

        # insert connectors
        task_logger.debug('start inserting connectors')
        for connector_id, r in connectors.items():
            q = """
        INSERT INTO connector (id, user_id, editor_id, project_id, location_x, location_y, location_z)
                    VALUES ({},{},{},{},{},{},{}) ON CONFLICT (id) DO NOTHING;
                """.format(
                connector_id,
                DEFAULT_IMPORT_USER,
                DEFAULT_IMPORT_USER,
                project_id,
                int(r['pre_x']),
                int(r['pre_y']),
                int(r['pre_z']))

            if with_multi:
                queries.append(q)
            else:
                cursor.execute(q)

        # insert links
        # TODO: optimize based on scores
        confidence_value = 5

        task_logger.debug('start insert links')
        for idx, val in treenode_connector.items():
            skeleton_node_id, connector_id = idx
            q = """
                INSERT INTO treenode_connector (user_id, project_id,
                    treenode_id, connector_id, relation_id, skeleton_id,
                    confidence)
                VALUES ({},{},{},{},{},{},{})
                ON CONFLICT ON CONSTRAINT treenode_connector_project_id_treenode_id_connector_id_relation DO NOTHING;
                """.format(
                DEFAULT_IMPORT_USER,
                project_id,
                skeleton_node_id,
                connector_id,
                relations[val['type']],
                active_skeleton_id,
                confidence_value)

            if with_multi:
                queries.append(q)
            else:
                cursor.execute(q)

        q = 'COMMIT;'
        if with_multi:
            queries.append(q)
        else:
            cursor.execute(q)

        if with_multi:
            #task_logger.debug('run multiquery. nr queries {}'.format(len(queries))
            task_logger.debug(f'Inserting {len(queries)} synaptic links')
            cursor.execute('\n'.join(queries))
            task_logger.debug('multiquery done')

        # add tags to connectors
        if tags:
            task_logger.debug('Add tags')
            cursor.execute("""
                WITH label_rel AS (
                    SELECT id FROM relation
                    WHERE relation_name = 'labeled_as'
                    AND project_id = %(project_id)s
                ), label_class AS (
                    SELECT id FROM class
                    WHERE class_name = 'label'
                    AND project_id = %(project_id)s
                ), insert_missing_labels AS (
                    INSERT INTO class_instance (user_id, project_id, class_id, name)
                    SELECT %(user_id)s, %(project_id)s, lc.id, label.name
                    FROM label_class lc,
                    UNNEST(%(label_names)s::text[]) label(name)
                    LEFT JOIN LATERAL(
                        SELECT id FROM class_instance ci
                        WHERE ci.name = label.name
                        AND ci.project_id = %(project_id)s
                        AND ci.class_id = lc.id
                    ) ci ON TRUE
                    WHERE ci.id IS NULL
                )
                INSERT INTO connector_class_instance
                    (user_id, project_id, relation_id, connector_id, class_instance_id)
                SELECT %(user_id)s, %(project_id)s, lr.id, c.id, ci.id
                FROM label_rel lr, label_class lc,
                UNNEST(%(label_names)s::text[]) label(name)
                JOIN LATERAL (
                    SELECT id FROM class_instance ci
                    WHERE ci.name = label.name
                    AND ci.project_id = %(project_id)s
                    AND ci.class_id = lc.id
                ) ci ON TRUE
                CROSS JOIN UNNEST(%(connector_ids)s::bigint[]) c(id)
            """, {
                'project_id': project_id,
                'user_id': DEFAULT_IMPORT_USER,
                'connector_ids': list(connectors.keys()),
                'label_names': tags,
            })

        if set_status:
            synapse_import.status = SynapseImport.Status.DONE
            synapse_import.status_detail = ""
        synapse_import.runtime = timer() - start_time
        synapse_import.n_imported_connectors = len(connectors)
        synapse_import.n_imported_links = len(treenode_connector)
        synapse_import.save()
        task_logger.debug('task: import_synapses_for_existing_skeleton started: done')
    except Exception as ex:
        error = ex
        task_logger.error(f'Exception occurred: {ex}')
        if synapse_import:
            duration = timer() - start_time
            synapse_import.runtime = duration
            synapse_import.status = SynapseImport.Status.ERROR
            synapse_import.status_detail = str(error)
            synapse_import.save()

    if message_user:
        task_logger.debug('Creating user message')
        user = User.objects.get(pk=user_id)
        msg = Message()
        msg.user = user
        msg.read = False
        has_zero_results = len(connectors) == 0 and len(treenode_connector) == 0
        if error:
            msg.title = f"Error while importing synapses for skeleton #{active_skeleton_id}"
            msg.text = f"No synapses could be created due to the following error: {error}"
            msg.action = ""
        elif has_zero_results:
            msg.title = f"No synapses were found that could be added to skeleton #{active_skeleton_id}"
            msg.action = f"?pid={project_id}&active_skeleton_id={active_skeleton_id}&tool=tracingtool"
        else:
            msg.title = f"Synapses imported for skeleton #{active_skeleton_id}"
            msg.text = (f"Imported {len(connectors)} synapses (connector nodes) " +
                f"and created {len(treenode_connector)}")
            msg.action = f"?pid={project_id}&active_skeleton_id={active_skeleton_id}&tool=tracingtool"
        msg.save()

        notify_user(user.id, msg.id, msg.title)

        payload = {
            'task': 'import-synapses',
            'n_inserted_synapses': len(connectors),
            'n_inserted_links': len(treenode_connector),
            'skeleton_id': active_skeleton_id,
        }
        if error:
            payload['error'] = str(error)
        if message_payload:
            payload.update(message_payload)
        msg_user(user_id, 'circuitmap-update', payload)
        task_logger.debug('Created DB message and ASGI message')


@task
def import_autoseg_skeleton_with_synapses(project_id, user_id, import_id,
        segment_id, message_user=True, message_payload=None,
        with_autapses=False, set_status=True, annotations=None, tags=None):

    synapse_import = SynapseImport.objects.get(id=import_id)
    segment_import = synapse_import.segmentimport_set.all()
    if len(segment_import) > 1:
        raise ValueError('Expected single segment import entry')
    else:
        segment_import = segment_import[0]

    try:
        # ID handling: method globally unique ID
        def mapping_skel_nid(segment_id, nid, project_id):
            max_nodes = 100000 # max. number of nodes / autoseg skeleton allowed
            nr_projects = 10 # max number of projects / instance allowed
            return int( int(segment_id) * max_nodes * nr_projects + int(nid) * nr_projects + int(project_id) )

        task_logger.debug('task: import_autoseg_skeleton_with_synapses started')
        cursor = connection.cursor()

        # check if skeleton of autoseg segment_id was previously imported
        task_logger.debug('check if already imported')
        cursor.execute('SELECT id, skeleton_id FROM treenode WHERE project_id = {} and id = {}'.format( \
            int(project_id), mapping_skel_nid(segment_id, 0, int(project_id))))
        res = cursor.fetchone()
        task_logger.debug(f'fetched: {res}')

        if not res is None:
            node_id, skeleton_class_instance_id = res
            if set_status:
                synapse_import.skeleton_id = skeleton_class_instance_id
                synapse_import.save()
            task_logger.debug('autoseg skeleton was previously imported. skip reimport. (current skeletonid is {})'.format(skeleton_class_instance_id))
        else:
            # fetch and insert autoseg skeleton at location
            task_logger.debug('fetch skeleton for segment_id {}'.format(segment_id))

            s1 = cv.skeleton.get(int(segment_id))
            task_logger.debug('fetched.')
            nr_of_vertices = len(s1.vertices)
            task_logger.debug('number of vertices {} for {}'.format(nr_of_vertices, segment_id))

            task_logger.debug('autoseg skeleton for {} has {} nodes'.format(segment_id, nr_of_vertices))

            task_logger.debug('generate graph for skeleton')
            g=nx.Graph()
            attrs = []
            for idx in range(nr_of_vertices):
                x,y,z=map(int,s1.vertices[idx,:])
                r = s1.radius[idx]
                attrs.append((int(idx),{'x':x,'y':y,'z':z,'r':float(r) }))
            g.add_nodes_from(attrs)
            edgs = []
            for u,v in s1.edges:
                edgs.append((int(u), int(v)))
            g.add_edges_from(edgs)

            # TODO: check if it skeleton already imported
            # this check depends on the chosen implementation
            task_logger.debug('check number of connected components')
            nr_components = nx.number_connected_components(g)
            if nr_components > 1:
                task_logger.debug('more than one component in skeleton graph. use only largest component')
                graph = max(nx.connected_component_subgraphs(g), key=len)
            else:
                graph = g

            # do relabeling and choose root node
            g2 = nx.relabel_nodes(g, lambda x: mapping_skel_nid(segment_id, x, project_id))
            root_skeleton_id = mapping_skel_nid(segment_id, 0, project_id)
            new_tree = nx.bfs_tree(g2, root_skeleton_id)

            task_logger.debug('fetch relations and classes')
            cursor.execute("SELECT id,relation_name from relation where project_id = {project_id};".format(project_id=project_id))
            res = cursor.fetchall()
            relations = dict([(v,u) for u,v in res])

            cursor.execute("SELECT id,class_name from class where project_id = {project_id};".format(project_id=project_id))
            res = cursor.fetchall()
            classes = dict([(v,u) for u,v in res])


            query = """
            INSERT INTO class_instance (user_id, project_id, class_id, name)
                        VALUES ({},{},{},'{}') RETURNING id;
            """.format(DEFAULT_IMPORT_USER, project_id, classes['neuron'] ,"neuron {}".format(segment_id))
            task_logger.debug(query)
            cursor.execute(query)
            neuron_class_instance_id = cursor.fetchone()[0]
            task_logger.debug(f'got neuron: {neuron_class_instance_id}')

            query = """
            INSERT INTO class_instance (user_id, project_id, class_id, name)
                        VALUES ({},{},{},'{}') RETURNING id;
            """.format(DEFAULT_IMPORT_USER, project_id, classes['skeleton'] ,"skeleton {}".format(segment_id))
            task_logger.debug(query)
            cursor.execute(query)
            skeleton_class_instance_id = cursor.fetchone()[0]
            task_logger.debug(f'got skeleton: {skeleton_class_instance_id}')

            query = """
            INSERT INTO class_instance_class_instance (user_id, project_id, class_instance_a, class_instance_b, relation_id)
                        VALUES ({},{},{},{},{}) RETURNING id;
            """.format(DEFAULT_IMPORT_USER, project_id, skeleton_class_instance_id, neuron_class_instance_id, relations['model_of'])
            task_logger.debug(query)
            cursor.execute(query)
            cici_id = cursor.fetchone()[0]

            # insert treenodes

            queries = []
            with_multi = True
            q = 'BEGIN;'
            if with_multi:
                queries.append(q)
            else:
                cursor.execute(q)

            # insert root node
            parent_id = ""
            n = g2.nodes[root_skeleton_id]
            query = """INSERT INTO treenode (id, project_id, location_x, location_y, location_z, editor_id,
                        user_id, skeleton_id, radius) VALUES ({},{},{},{},{},{},{},{},{}) ON CONFLICT (id) DO NOTHING;
                """.format(
                 root_skeleton_id,
                 project_id,
                 n['x'],
                 n['y'],
                 n['z'],
                 DEFAULT_IMPORT_USER,
                 DEFAULT_IMPORT_USER,
                 skeleton_class_instance_id,
                 n['r'])
            if with_multi:
                queries.append(query)
            else:
                cursor.execute(query)

            # insert all chidren
            n_imported_nodes = 0
            for parent_id, skeleton_node_id in new_tree.edges(data=False):
                n = g2.nodes[skeleton_node_id]
                query = """INSERT INTO treenode (id,project_id, location_x, location_y, location_z, editor_id,
                            user_id, skeleton_id, radius, parent_id) VALUES ({},{},{},{},{},{},{},{},{},{}) ON CONFLICT (id) DO NOTHING;
                    """.format(
                     skeleton_node_id,
                     project_id,
                     n['x'],
                     n['y'],
                     n['z'],
                     DEFAULT_IMPORT_USER,
                     DEFAULT_IMPORT_USER,
                     skeleton_class_instance_id,
                     n['r'],
                    parent_id)
                if with_multi:
                    queries.append(query)
                else:
                    cursor.execute(query)
                n_imported_nodes += 1

            query = 'COMMIT;'
            if with_multi:
                queries.append(query)
            else:
                cursor.execute(query)

            if set_status:
                synapse_import.skeleton_id = skeleton_class_instance_id
                synapse_import.save()
            segment_import.n_imported_nodes += n_imported_nodes
            segment_import.save()

            task_logger.debug('run multiquery')
            if with_multi:
                cursor.execute('\n'.join(queries))

            # add annotations to imported neurons
            if annotations:
                task_logger.debug('Add annotations')
                cursor.execute("""
                    WITH ann_rel AS (
                        SELECT id FROM relation
                        WHERE relation_name = 'annotated_with'
                        AND project_id = %(project_id)s
                    ), ann_class AS (
                        SELECT id FROM class
                        WHERE class_name = 'annotation'
                        AND project_id = %(project_id)s
                    ), insert_missing_annotations AS (
                        INSERT INTO class_instance (user_id, project_id, class_id, name)
                        SELECT %(user_id)s, %(project_id)s, ac.id, ann.name
                        FROM ann_class ac,
                        UNNEST(%(annotation_names)s::text[]) ann(name)
                        LEFT JOIN LATERAL (
                            SELECT id FROM class_instance ci
                            WHERE ci.name = ann.name
                            AND ci.class_id = ac.id
                            AND ci.project_id = %(project_id)s
                        ) ci ON TRUE
                        WHERE ci.id IS NULL
                    )
                    INSERT INTO class_instance_class_instance
                        (user_id, project_id, relation_id, class_instance_a, class_instance_b)
                    SELECT %(user_id)s, %(project_id)s, ar.id, n.id, ci.id
                    FROM ann_rel ar, ann_class ac,
                    UNNEST(%(annotation_names)s::text[]) ann(name)
                    JOIN LATERAL (
                        SELECT id FROM class_instance ci
                        WHERE ci.name = ann.name
                        AND ci.project_id = %(project_id)s
                        AND ci.class_id = ac.id
                    ) ci ON TRUE
                    CROSS JOIN UNNEST(%(neuron_ids)s::bigint[]) n(id)
                """, {
                    'project_id': project_id,
                    'user_id': DEFAULT_IMPORT_USER,
                    'neuron_ids': [neuron_class_instance_id],
                    'annotation_names': annotations,
                })

        # call import_synapses_for_existing_skeleton with autoseg skeleton as seed
        task_logger.debug('call task: import_synapses_for_existing_skeleton')

        import_synapses_for_existing_skeleton(project_id, user_id, import_id,
            -1,  skeleton_class_instance_id, segment_id, message_user,
            message_payload, with_autapses, set_status=False,
            annotations=annotations, tags=tags)

        task_logger.debug('task: import_autoseg_skeleton_with_synapses done')


    except Exception as ex:
        task_logger.error(f'Exception occurred: {ex}')


class SynapseImportList(APIView):

    @method_decorator(requires_user_role(UserRole.Browse))
    def get(self, request:HttpRequest, project_id) -> JsonResponse:
        """List all available point clouds or optionally a sub set.
        ---
        parameters:
          - name: project_id
            description: Project of the returned synapse imports
            type: integer
            paramType: path
            required: true
        """
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, user_id, project_id, creation_time, edition_time, status,
                status_detail, runtime, request_id, skeleton_id, n_imported_links,
                n_imported_connectors, n_upstream_partners, n_downstream_partners,
                upstream_partner_syn_threshold, downsteam_partner_syn_threshold,
                distance_threshold, with_autapses
            FROM circuitmap_synapseimport si
            WHERE project_id = %(project_id)s
        """, {
            'project_id': project_id,
        })
        return JsonResponse([{
            'id': r[0],
            'user_id': r[1],
            'project_id': r[2],
            'creation_time': r[3],
            'edition_time': r[4],
            'status': SynapseImport.Status.labels[r[5]],
            'status_detail': r[6],
            'runtime': r[7],
            'request_id': r[8],
            'skeleton_id': r[9],
            'n_imported_links': r[10],
            'n_imported_connectors': r[11],
            'n_upstream_partners': r[12],
            'n_downstream_partners': r[13],
            'upstream_partner_syn_threshold': r[14],
            'downsteam_partner_syn_threshold': r[15],
            'distance_threshold': r[16],
            'with_autapses': r[17],
        } for r in cursor.fetchall()], safe=False)
