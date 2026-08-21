from django.db import migrations, models

SUPPORTED_WIDTHS = {6_250, 12_500, 25_000}


def populate_channel_widths(apps, schema_editor):
    Assignment = apps.get_model("plans", "Assignment")
    assignments = Assignment.objects.filter(
        conventional_channel__isnull=False,
    ).select_related("conventional_channel")
    for assignment in assignments.iterator():
        width = assignment.conventional_channel.bandwidth_hz
        if width in SUPPORTED_WIDTHS:
            update_fields = []
            if assignment.rx_frequency_hz is not None:
                assignment.rx_channel_width_hz = width
                update_fields.append("rx_channel_width_hz")
            if assignment.tx_frequency_hz is not None:
                assignment.tx_channel_width_hz = width
                update_fields.append("tx_channel_width_hz")
            if update_fields:
                assignment.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [("plans", "0006_contact_publication_placement")]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="rx_channel_width_hz",
            field=models.PositiveIntegerField(
                blank=True,
                choices=[
                    (6250, "6.25 kHz"),
                    (12500, "12.5 kHz"),
                    (25000, "25 kHz legacy wideband"),
                ],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="assignment",
            name="tx_channel_width_hz",
            field=models.PositiveIntegerField(
                blank=True,
                choices=[
                    (6250, "6.25 kHz"),
                    (12500, "12.5 kHz"),
                    (25000, "25 kHz legacy wideband"),
                ],
                null=True,
            ),
        ),
        migrations.RunPython(populate_channel_widths, migrations.RunPython.noop),
    ]
