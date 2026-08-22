from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fcc_data", "0004_allow_repeated_uls_location_numbers")]

    operations = [
        migrations.AlterField(
            model_name="ulsemission",
            name="antenna_number",
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name="ulsfrequency",
            name="antenna_number",
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name="ulsfrequency",
            name="number_of_units",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
