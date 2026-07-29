import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("deconfliction", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DeconflictionFindingDisposition",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("finding_key", models.CharField(max_length=64)),
                ("rule_id", models.CharField(max_length=16)),
                (
                    "disposition",
                    models.CharField(
                        choices=[
                            ("reviewed_no_change", "Reviewed — no plan change"),
                            ("plan_change_required", "Plan change required"),
                            (
                                "special_accommodation_required",
                                "Special accommodation required",
                            ),
                            ("source_review_required", "Source review required"),
                        ],
                        max_length=40,
                    ),
                ),
                ("explanation", models.CharField(max_length=1000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "analysis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="finding_dispositions",
                        to="deconfliction.deconflictionanalysis",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="deconfliction_finding_dispositions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="deconflictionfindingdisposition",
            index=models.Index(
                fields=["analysis", "finding_key", "created_at"],
                name="deconf_finding_review_idx",
            ),
        ),
    ]
