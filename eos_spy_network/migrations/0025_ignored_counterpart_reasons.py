from django.db import migrations, models


def as_entry(stored) -> dict:
    """A counterpart ignored before reasons was stored by its name alone; it keeps that name, without a reason."""
    if isinstance(stored, dict):
        return stored
    return {"name": stored, "reason": "", "by": "", "at": ""}


def forwards(apps, schema_editor):
    SpyConfiguration = apps.get_model("eos_spy_network", "SpyConfiguration")
    for config in SpyConfiguration.objects.all():
        if config.ignored_network_counterparts:
            config.ignored_network_counterparts = {
                eve_id: as_entry(stored) for eve_id, stored in config.ignored_network_counterparts.items()
            }
            config.save(update_fields=["ignored_network_counterparts"])


def backwards(apps, schema_editor):
    SpyConfiguration = apps.get_model("eos_spy_network", "SpyConfiguration")
    for config in SpyConfiguration.objects.all():
        if config.ignored_network_counterparts:
            config.ignored_network_counterparts = {
                eve_id: as_entry(stored)["name"] for eve_id, stored in config.ignored_network_counterparts.items()
            }
            config.save(update_fields=["ignored_network_counterparts"])


class Migration(migrations.Migration):

    dependencies = [
        ('eos_spy_network', '0024_network_min_connections'),
    ]

    operations = [
        migrations.AlterField(
            model_name='spyconfiguration',
            name='ignored_network_counterparts',
            field=models.JSONField(blank=True, default=dict, help_text='Payments and contracts with these counterparts count neither for the Network nor for the markers ISK and Contracts. Remove one to count it again.', verbose_name='Ignored counterparts'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
