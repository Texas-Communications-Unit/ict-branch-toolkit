from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fcc_data", "0001_initial")]

    operations = [
        migrations.AddIndex(
            model_name="antennastructure",
            index=models.Index(
                fields=["batch", "latitude", "longitude"],
                name="fcc_data_an_batch_i_b7f844_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ulslocation",
            index=models.Index(
                fields=["asr_registration_number"],
                name="fcc_data_ul_asr_reg_950a02_idx",
            ),
        ),
    ]
