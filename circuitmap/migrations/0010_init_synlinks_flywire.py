# Generated by Django 2.2.5 on 2019-11-25 05:36

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('circuitmap', '0009_store_txid_and_fix_synlinks_edit_time_update'),
    ]

    operations = [
        migrations.CreateModel(
            name='SynlinksFlywire',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pre_pt_root_id', models.BigIntegerField()),
                ('pre_pt_sv_id', models.BigIntegerField()),
                ('pre_pt_position_x', models.BigIntegerField()),
                ('pre_pt_position_y', models.BigIntegerField()),
                ('pre_pt_position_z', models.BigIntegerField()),
                ('ctr_pt_position_x', models.BigIntegerField()),
                ('ctr_pt_position_y', models.BigIntegerField()),
                ('ctr_pt_position_z', models.BigIntegerField()),
                ('post_pt_root_id', models.BigIntegerField()),
                ('post_pt_sv_id', models.BigIntegerField()),
                ('post_pt_position_x', models.BigIntegerField()),
                ('post_pt_position_y', models.BigIntegerField()),
                ('post_pt_position_z', models.BigIntegerField()),
            ],
        ),
    ]