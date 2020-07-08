from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('circuitmap', '0006_add_partner_expectation_fields'),
    ]

    operations = [
            migrations.RunSQL("""
                CREATE FUNCTION circuitmap_on_edit() RETURNS trigger
                    LANGUAGE plpgsql
                    AS $$BEGIN
                    NEW."edition_time" := now();
                    RETURN NEW;
                END;
                $$;

                CREATE TRIGGER on_edit_circuitmap_on_edit BEFORE UPDATE ON
                circuitmap_synlinks FOR EACH ROW EXECUTE PROCEDURE circuitmap_on_edit();
            """, """
                DROP TRIGGER on_edit_circuitmap_on_edit ON circuitmap_synlinks;
                DROP FUNCTION circuitmap_on_edit;
            """)
    ]
