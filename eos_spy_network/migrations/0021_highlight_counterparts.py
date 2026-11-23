from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eos_spy_network', '0020_ignored_network_counterparts'),
    ]

    operations = [
        migrations.AddField(
            model_name='spyconfiguration',
            name='highlight_counterparts',
            field=models.JSONField(blank=True, default=dict, help_text='Characters, Corporations and Alliances that get a tile on the Markers page, with the number of accounts that deal with them in the Network.', verbose_name='Highlighted counterparts'),
        ),
    ]
