from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eos_spy_network', '0019_ignored_characters'),
    ]

    operations = [
        migrations.AddField(
            model_name='spyconfiguration',
            name='ignored_network_counterparts',
            field=models.JSONField(blank=True, default=dict, help_text='Payments and contracts with these counterparts do not count for the Network. Remove one to count it again.', verbose_name='Ignored counterparts'),
        ),
    ]
