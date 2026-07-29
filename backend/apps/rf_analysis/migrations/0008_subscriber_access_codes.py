from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rf_analysis", "0007_terrainanalysis"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriberprofileversion",
            name="rx_access_code",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="subscriberprofileversion",
            name="tx_access_code",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
