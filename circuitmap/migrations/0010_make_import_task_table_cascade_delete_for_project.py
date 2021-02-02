from django.db import migrations


forward = """
    ALTER TABLE circuitmap_synapseimport DROP CONSTRAINT circuitmap_synapseimport_project_id_96456095_fk_project_id;
    ALTER TABLE circuitmap_synapseimport ADD CONSTRAINT circuitmap_synapseimport_project_id_fkey
        FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;

    ALTER TABLE circuitmap_synapseimport DROP CONSTRAINT circuitmap_synapseimport_user_id_24458874_fk_auth_user_id;
    ALTER TABLE circuitmap_synapseimport ADD CONSTRAINT circuitmap_synapseimport_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;

    ALTER TABLE circuitmap_segmentimport DROP CONSTRAINT circuitmap_segmentim_synapse_import_id_cf3093e2_fk_circuitma;
    ALTER TABLE circuitmap_segmentimport ADD CONSTRAINT circuitmap_segmentim_synapse_import_id_fkey
        FOREIGN KEY (synapse_import_id) REFERENCES circuitmap_synapseimport(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
"""


backward = """
    ALTER TABLE circuitmap_synapseimport DROP CONSTRAINT circuitmap_synapseimport_project_id_fkey;
    ALTER TABLE circuitmap_synapseimport ADD CONSTRAINT "circuitmap_synapseimport_project_id_96456095_fk_project_id"
        FOREIGN KEY (project_id) REFERENCES project(id) DEFERRABLE INITIALLY DEFERRED;

    ALTER TABLE circuitmap_synapseimport DROP CONSTRAINT circuitmap_synapseimport_user_id_fkey;
    ALTER TABLE circuitmap_synapseimport ADD CONSTRAINT circuitmap_synapseimport_user_id_24458874_fk_auth_user_id
        FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;

    ALTER TABLE circuitmap_segmentimport DROP CONSTRAINT circuitmap_segmentim_synapse_import_id_fkey;
    ALTER TABLE circuitmap_segmentimport ADD CONSTRAINT circuitmap_segmentim_synapse_import_id_cf3093e2_fk_circuitma
        FOREIGN KEY (synapse_import_id) REFERENCES circuitmap_synapseimport(id) DEFERRABLE INITIALLY DEFERRED;
"""


class Migration(migrations.Migration):
    """Add on delete cascade constraint option to project forein key of synapse
    import tasks.
    """

    dependencies = [
        ('circuitmap', '0009_store_txid_and_fix_synlinks_edit_time_update'),
    ]

    operations = [
            migrations.RunSQL(forward, backward)
    ]

