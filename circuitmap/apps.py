from __future__ import unicode_literals

from django.apps import AppConfig

class CircuitmapConfig(AppConfig):
    name = 'circuitmap'

    def get_config(self):
        from circuitmap import control
        return {
            'seg_name': control.SEGMENTATION_NAME,
            'seg_access_url': control.CLOUDVOLUME_URL,
            'seg_storage': control.GOOGLE_SEGMENTATION_STORAGE,
            'skeleton_key': control.CLOUDVOLUME_SKELETONS,
            'import_user': control.DEFAULT_IMPORT_USER,
            'connector_id_offset': control.CONNECTORID_OFFSET,
        }
