import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fcc_data", "0002_fcc_map_lookup_indexes")]

    operations = [
        migrations.AlterField(
            model_name="ulsfrequency",
            name="frequency_hz",
            field=models.BigIntegerField(
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(300000000000),
                ]
            ),
        ),
        migrations.AlterField(
            model_name="ulsemission",
            name="frequency_hz",
            field=models.BigIntegerField(
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(300000000000),
                ]
            ),
        ),
    ]
