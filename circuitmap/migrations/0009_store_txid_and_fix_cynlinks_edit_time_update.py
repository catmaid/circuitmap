from django.db import migrations


class Migration(migrations.Migration):
    """Remove the circuitmap_on_edit() trigger for the synlinks table, because
    it is not supporsed to be updated and hence has no edition time field in the
    first place.

    Also add transaction ID to the synlinks rows during edit.
    """

    dependencies = [
        ('circuitmap', '0007_add_auto_update_timestamp'),
    ]

    operations = [
            migrations.RunSQL("""
                DROP TRIGGER on_edit_circuitmap_on_edit ON circuitmap_synlinks;

                CREATE OR REPLACE FUNCTION circuitmap_on_edit() RETURNS trigger
                    LANGUAGE plpgsql
                    AS $$BEGIN
                    NEW."edition_time" := now();
                    NEW."txid" := txid_current();
                    RETURN NEW;
                END;
                $$;
            """, """
                CREATE OR REPLACE FUNCTION circuitmap_on_edit() RETURNS trigger
                    LANGUAGE plpgsql
                    AS $$BEGIN
                    NEW."edition_time" := now();
                    RETURN NEW;
                END;
                $$;

                CREATE TRIGGER on_edit_circuitmap_on_edit BEFORE UPDATE ON
                circuitmap_synlinks FOR EACH ROW EXECUTE PROCEDURE circuitmap_on_edit();
            """)
    ]
