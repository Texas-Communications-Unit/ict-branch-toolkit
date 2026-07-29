import django.db.models.deletion
from django.db import migrations, models


def classify_existing_assignments(apps, schema_editor):
    Assignment = apps.get_model("plans", "Assignment")
    for assignment in Assignment.objects.all().iterator():
        if assignment.rx_frequency_hz is not None and assignment.tx_frequency_hz is not None:
            classification = "fixed_pair"
            subtype = ""
        elif assignment.rx_frequency_hz is None and assignment.tx_frequency_hz is not None:
            classification = "transmit_only"
            subtype = ""
        elif assignment.rx_frequency_hz is not None and assignment.tx_frequency_hz is None:
            classification = "receive_only"
            subtype = ""
        elif assignment.trunked_talkgroup_id is not None:
            classification = "named_system"
            subtype = "trunked_talkgroup"
        else:
            classification = "not_determined"
            subtype = ""
        Assignment.objects.filter(pk=assignment.pk).update(
            operating_classification=classification,
            technology_subtype=subtype,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("plans", "0003_collaboration_versions"),
        ("rf_analysis", "0008_subscriber_access_codes"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="operating_classification",
            field=models.CharField(
                choices=[
                    ("fixed_pair", "Fixed-frequency pair"),
                    ("transmit_only", "Broadcast/transmit-only"),
                    ("receive_only", "Receive-only"),
                    (
                        "named_system",
                        "Named system channel — frequencies intentionally omitted",
                    ),
                    ("dynamic_pool", "Dynamic/multi-channel pool"),
                    ("not_determined", "Not yet determined"),
                ],
                default="not_determined",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="assignment",
            name="subscriber_profile_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="plan_assignments",
                to="rf_analysis.subscriberprofileversion",
            ),
        ),
        migrations.AddField(
            model_name="assignment",
            name="technology_subtype",
            field=models.CharField(
                blank=True,
                choices=[
                    ("trunked_talkgroup", "Trunked talkgroup"),
                    ("lte_5g", "LTE/5G"),
                    ("scada", "SCADA"),
                    ("spread_spectrum", "Spread-spectrum"),
                    ("other", "Other system"),
                ],
                max_length=24,
            ),
        ),
        migrations.RunPython(
            classify_existing_assignments,
            migrations.RunPython.noop,
        ),
    ]
