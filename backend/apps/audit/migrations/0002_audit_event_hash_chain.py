import hashlib
import json

from django.db import migrations, models

GENESIS_HASH = "0" * 64


def _record_hash(*, previous_hash, sequence, actor_id, action, target_type, target_id, details):
    canonical = json.dumps(
        {
            "previous_hash": previous_hash,
            "sequence": sequence,
            "actor_id": actor_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": details,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def backfill_chain(apps, schema_editor):
    AuditEvent = apps.get_model("audit", "AuditEvent")
    previous_hash = GENESIS_HASH
    events = AuditEvent.objects.order_by("occurred_at", "id")
    for sequence, event in enumerate(events):
        event.sequence = sequence
        event.previous_hash = previous_hash
        event.record_hash = _record_hash(
            previous_hash=previous_hash,
            sequence=sequence,
            actor_id=event.actor_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            details=event.details,
        )
        event.save(update_fields=["sequence", "previous_hash", "record_hash"])
        previous_hash = event.record_hash


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="sequence",
            field=models.BigIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="previous_hash",
            field=models.CharField(default=GENESIS_HASH, editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="record_hash",
            field=models.CharField(default="", editable=False, max_length=64),
        ),
        migrations.RunPython(backfill_chain, noop_reverse),
        migrations.AlterField(
            model_name="auditevent",
            name="sequence",
            field=models.BigIntegerField(editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="record_hash",
            field=models.CharField(editable=False, max_length=64),
        ),
        migrations.AddConstraint(
            model_name="auditevent",
            constraint=models.CheckConstraint(
                check=models.Q(sequence__gte=0), name="audit_event_sequence_not_negative"
            ),
        ),
    ]
