# Generated by Django 3.0.7 on 2020-07-07 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('circuitmap', '0004_add_import_job_tables'),
    ]

    operations = [
        migrations.AlterField(
            model_name='synapseimport',
            name='status',
            field=models.IntegerField(choices=[(0, 'Created'), (1, 'Queued'), (2, 'Computing'), (3, 'Done'), (4, 'Error'), (5, 'Fetch Pre Partners'), (6, 'Fetch Post Partners'), (7, 'No Data')], default=0),
        ),
    ]