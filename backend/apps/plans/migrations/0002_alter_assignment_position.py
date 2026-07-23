from django.core.validators import MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("plans", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assignment",
            name="position",
            field=models.PositiveIntegerField(validators=[MaxValueValidator(2_147_483_647)]),
        ),
    ]
