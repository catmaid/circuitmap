from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('circuitmap', '0007_add_auto_update_timestamp'),
    ]

    operations = [
            migrations.RunSQL("""
                CREATE TRIGGER on_edit_circuitmap_synapseimport BEFORE UPDATE ON
                circuitmap_synapseimport FOR EACH ROW EXECUTE PROCEDURE circuitmap_on_edit();
            """, """
                DROP TRIGGER on_edit_circuitmap_on_edit ON circuitmap_synapseimport;
            """)
    ]
