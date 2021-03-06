# Generated by Django 3.0.5 on 2020-05-09 14:35

import catmaid.fields
from django.conf import settings
import django.contrib.postgres.fields
import django.contrib.postgres.functions
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catmaid', '0102_update_client_settings_field'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('circuitmap', '0003_auto_20200117_0517'),
    ]

    operations = [
        migrations.CreateModel(
            name='SynapseImport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creation_time', catmaid.fields.DbDefaultDateTimeField(default=django.contrib.postgres.functions.TransactionNow)),
                ('edition_time', catmaid.fields.DbDefaultDateTimeField(default=django.contrib.postgres.functions.TransactionNow)),
                ('status', models.IntegerField(choices=[(0, 'Created'), (1, 'Queued'), (2, 'Computing'), (3, 'Done'), (4, 'Error')], default=0)),
                ('status_detail', models.TextField(default='')),
                ('runtime', models.FloatField(default=0)),
                ('request_id', models.TextField(blank=True, null=True)),
                ('skeleton_id', models.BigIntegerField(db_index=True)),
                ('n_imported_links', models.IntegerField(blank=True, default=0)),
                ('n_imported_connectors', models.IntegerField(blank=True, default=0)),
                ('n_upstream_partners', models.IntegerField(blank=True, default=0)),
                ('n_downstream_partners', models.IntegerField(blank=True, default=0)),
                ('tags', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ('annotations', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ('upstream_partner_syn_threshold', models.IntegerField(default=5)),
                ('downsteam_partner_syn_threshold', models.IntegerField(default=5)),
                ('distance_threshold', models.IntegerField(default=1000)),
                ('with_autapses', models.BooleanField(default=False)),
                ('txid', models.BigIntegerField(blank=True, null=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='catmaid.Project')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='SegmentImport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.TextField()),
                ('segment_id', models.BigIntegerField(db_index=True)),
                ('n_imported_nodes', models.IntegerField(default=0)),
                ('voxel_x', models.FloatField()),
                ('voxel_y', models.FloatField()),
                ('voxel_z', models.FloatField()),
                ('physical_x', models.FloatField()),
                ('physical_y', models.FloatField()),
                ('physical_z', models.FloatField()),
                ('synapse_import', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='circuitmap.SynapseImport')),
            ],
        ),
    ]
