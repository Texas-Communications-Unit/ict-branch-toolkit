import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0001_initial"),
        ("plans", "0001_initial"),
        ("rf_analysis", "0005_calibrationset_fieldobservation_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Phase2ValidationBundle",
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
                ("validation_profile_id", models.CharField(max_length=80)),
                ("validation_profile_version", models.CharField(max_length=120)),
                ("app_version", models.CharField(max_length=80)),
                (
                    "job_state",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("complete", "Complete"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="queued",
                        max_length=12,
                    ),
                ),
                ("progress_step", models.CharField(default="queued", max_length=80)),
                (
                    "progress_percent",
                    models.PositiveSmallIntegerField(
                        default=0,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100),
                        ],
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("approved", "Approved")],
                        default="draft",
                        max_length=12,
                    ),
                ),
                ("input_snapshot", models.JSONField()),
                ("input_sha256", models.CharField(max_length=64)),
                ("result_snapshot", models.JSONField(blank=True, default=dict)),
                ("result_sha256", models.CharField(blank=True, max_length=64)),
                ("failure_code", models.CharField(blank=True, max_length=80)),
                ("failure_message", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approved_phase2_validation_bundles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "approved_revision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="phase2_validation_bundles",
                        to="plans.planrevision",
                    ),
                ),
                (
                    "calibration_set",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="phase2_validation_bundles",
                        to="rf_analysis.calibrationset",
                    ),
                ),
                (
                    "coverage_estimate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="phase2_validation_bundles",
                        to="rf_analysis.coverageestimate",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_phase2_validation_bundles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "directional_analysis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="phase2_validation_bundles",
                        to="rf_analysis.directionalcoverageanalysis",
                    ),
                ),
                (
                    "haat_calculation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="phase2_validation_bundles",
                        to="rf_analysis.haatcalculation",
                    ),
                ),
                (
                    "incident",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="phase2_validation_bundles",
                        to="incidents.incident",
                    ),
                ),
                (
                    "supersedes",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retries",
                        to="rf_analysis.phase2validationbundle",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="phase2validationbundle",
            index=models.Index(
                fields=["incident", "job_state"],
                name="rf_p2val_inc_state_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="phase2validationbundle",
            index=models.Index(
                fields=["incident", "status"],
                name="rf_p2val_inc_status_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="phase2validationbundle",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status="draft",
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                    )
                    | models.Q(
                        status="approved",
                        approved_by__isnull=False,
                        approved_at__isnull=False,
                    )
                ),
                name="rf_p2val_approval_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="phase2validationbundle",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        job_state="queued",
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        progress_percent=0,
                    )
                    | models.Q(
                        job_state="running",
                        started_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | models.Q(
                        job_state__in=["complete", "failed", "cancelled"],
                        completed_at__isnull=False,
                    )
                ),
                name="rf_p2val_job_state_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="phase2validationbundle",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(job_state="complete") & ~models.Q(result_sha256="")
                    | ~models.Q(job_state="complete")
                ),
                name="rf_p2val_complete_has_digest",
            ),
        ),
    ]
