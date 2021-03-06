# Generated by Django 2.2.8 on 2020-01-17 04:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('circuitmap', '0001_init_synlinks'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='synlinks',
            name='ids',
        ),
        migrations.RemoveField(
            model_name='synlinks',
            name='index',
        ),
        migrations.RemoveField(
            model_name='synlinks',
            name='max',
        ),
        migrations.AddField(
            model_name='synlinks',
            name='cleft_id',
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='synlinks',
            name='cleft_scores',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='synlinks',
            name='clust_con_offset',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='synlinks',
            name='dist',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='synlinks',
            name='offset',
            field=models.IntegerField(db_index=True, default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='synlinks',
            name='prob_count',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='synlinks',
            name='prob_max',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='synlinks',
            name='prob_mean',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='synlinks',
            name='prob_min',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='synlinks',
            name='prob_sum',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='synlinks',
            name='post_x',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='synlinks',
            name='post_y',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='synlinks',
            name='post_z',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='synlinks',
            name='pre_x',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='synlinks',
            name='pre_y',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='synlinks',
            name='pre_z',
            field=models.FloatField(),
        ),
    ]
