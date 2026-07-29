from datetime import UTC, datetime, timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_operating_intent_migration_classifies_existing_assignments():
    migrate_from = [
        ("plans", "0003_collaboration_versions"),
        ("resources", "0002_alter_conventionalchannel_bandwidth_hz"),
    ]
    migrate_to = [
        ("plans", "0004_assignment_operating_intent"),
        ("resources", "0004_alter_resourcesource_source_type"),
    ]
    executor = MigrationExecutor(connection)
    leaf_nodes = executor.loader.graph.leaf_nodes()

    try:
        executor.migrate(migrate_from)
        old_apps = executor.loader.project_state(migrate_from).apps
        User = old_apps.get_model("auth", "User")
        Incident = old_apps.get_model("incidents", "Incident")
        OperationalPeriod = old_apps.get_model("incidents", "OperationalPeriod")
        Plan = old_apps.get_model("plans", "ICS205Plan")
        Revision = old_apps.get_model("plans", "PlanRevision")
        Assignment = old_apps.get_model("plans", "Assignment")
        ResourceSource = old_apps.get_model("resources", "ResourceSource")
        ResourceRelease = old_apps.get_model("resources", "ResourceRelease")
        TrunkedTalkgroup = old_apps.get_model("resources", "TrunkedTalkgroup")

        owner = User.objects.create(username="migration-test-owner")
        incident = Incident.objects.create(
            name="Synthetic migration exercise",
            incident_number="SYN-MIGRATION",
            created_by=owner,
        )
        starts_at = datetime(2026, 7, 29, 8, tzinfo=UTC)
        period = OperationalPeriod.objects.create(
            incident=incident,
            name="Synthetic period",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=12),
            created_by=owner,
        )
        plan = Plan.objects.create(
            incident=incident,
            operational_period=period,
            title="Synthetic migration ICS-205",
            created_by=owner,
        )
        revision = Revision.objects.create(plan=plan, number=1, created_by=owner)
        source = ResourceSource.objects.create(
            slug="synthetic-migration",
            name="Synthetic migration source",
            source_type="synthetic",
        )
        release = ResourceRelease.objects.create(
            source=source,
            version="synthetic-v1",
            effective_status="effective",
            content_sha256="a" * 64,
            imported_by=owner,
        )
        talkgroup = TrunkedTalkgroup.objects.create(
            release=release,
            identifier="SYN-TG",
            name="SYN TALKGROUP",
            system_name="Synthetic system",
            talkgroup_id=1001,
        )

        rows = [
            ("SYN FIXED", 155_000_000, 155_000_000, None),
            ("SYN TRANSMIT", None, 155_100_000, None),
            ("SYN RECEIVE", 155_200_000, None, None),
            ("SYN TALKGROUP", None, None, talkgroup),
            ("SYN UNDETERMINED", None, None, None),
        ]
        for position, (name, rx_frequency_hz, tx_frequency_hz, row_talkgroup) in enumerate(
            rows,
            1,
        ):
            Assignment.objects.create(
                revision=revision,
                position=position,
                function="Synthetic migration",
                channel_name=name,
                resource_snapshot={"type": "synthetic"},
                rx_frequency_hz=rx_frequency_hz,
                tx_frequency_hz=tx_frequency_hz,
                trunked_talkgroup=row_talkgroup,
            )

        executor = MigrationExecutor(connection)
        executor.migrate(migrate_to)
        migrated_apps = executor.loader.project_state(migrate_to).apps
        MigratedAssignment = migrated_apps.get_model("plans", "Assignment")
        classifications = {
            row.channel_name: (row.operating_classification, row.technology_subtype)
            for row in MigratedAssignment.objects.order_by("position")
        }
        assert classifications == {
            "SYN FIXED": ("fixed_pair", ""),
            "SYN TRANSMIT": ("transmit_only", ""),
            "SYN RECEIVE": ("receive_only", ""),
            "SYN TALKGROUP": ("named_system", "trunked_talkgroup"),
            "SYN UNDETERMINED": ("not_determined", ""),
        }
    finally:
        MigrationExecutor(connection).migrate(leaf_nodes)
