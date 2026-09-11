import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0001_initial"),
        ("incidents", "0003_auxcomm_and_incm_roles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ICS205BForm",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("prepared_at", models.DateTimeField(blank=True, null=True)),
                ("prepared_by_name", models.CharField(blank=True, max_length=160)),
                ("prepared_by_position", models.CharField(blank=True, max_length=160)),
                ("prepared_by_phone", models.CharField(blank=True, max_length=80)),
                ("prepared_by_signature", models.CharField(blank=True, max_length=200)),
                ("incident_location", models.CharField(blank=True, max_length=240)),
                ("state", models.CharField(blank=True, max_length=80)),
                ("county", models.CharField(blank=True, max_length=120)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_ics205b_forms",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "incident",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ics205b_forms",
                        to="incidents.incident",
                    ),
                ),
                (
                    "operational_period",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ics205b_forms",
                        to="incidents.operationalperiod",
                    ),
                ),
            ],
            options={"ordering": ["incident", "operational_period__starts_at", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="ics205bform",
            constraint=models.UniqueConstraint(
                fields=("incident", "operational_period"), name="unique_ics205b_incident_period"
            ),
        ),
        migrations.CreateModel(
            name="ICS205BAssignment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("position", models.PositiveIntegerField()),
                ("assignment", models.CharField(blank=True, max_length=200)),
                ("it_resource_type", models.CharField(blank=True, max_length=200)),
                ("resource_name", models.CharField(blank=True, max_length=240)),
                ("usage_description", models.TextField(blank=True)),
                ("platform", models.CharField(blank=True, max_length=200)),
                ("developer", models.CharField(blank=True, max_length=200)),
                ("login_install", models.TextField(blank=True)),
                ("equipment_location", models.TextField(blank=True)),
                ("poc_information", models.TextField(blank=True)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "form",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="extensions.ics205bform",
                    ),
                ),
            ],
            options={"ordering": ["position", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="ics205bassignment",
            constraint=models.UniqueConstraint(
                fields=("form", "position"), name="unique_ics205b_form_position"
            ),
        ),
    ]
