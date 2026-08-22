from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fcc_data", "0003_expand_fcc_frequency_range")]

    operations = [
        migrations.RemoveConstraint(
            model_name="ulslocation",
            name="unique_uls_location_license",
        ),
        migrations.AddIndex(
            model_name="ulslocation",
            index=models.Index(
                fields=["license", "location_number"],
                name="fcc_uls_loc_license_num_idx",
            ),
        ),
    ]
