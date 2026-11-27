from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eos_spy_network", "0025_ignored_counterpart_reasons"),
    ]

    operations = [
        migrations.AddField(
            model_name="findingreview",
            name="items",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
