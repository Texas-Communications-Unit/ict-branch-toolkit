"""Run an explicitly invoked, synthetic-only shared-test capacity probe."""

from __future__ import annotations

import json
import os
import statistics
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import (
    LocalContingencyAccount,
    Role,
    UserRoleAssignment,
)
from apps.audit.services import verify_audit_chain
from apps.incidents.models import Incident, IncidentMembership, OperationalPeriod
from apps.plans.models import Assignment, ICS205Plan, PlanRevision


@dataclass
class RequestMeasurement:
    scenario: str
    status: int
    elapsed_ms: float
    expected: bool


def _host_health() -> dict:
    result: dict[str, float | int | None] = {
        "load_1m": None,
        "load_5m": None,
        "memory_available_percent": None,
        "swap_free_percent": None,
    }
    try:
        load_1m, load_5m, _ = os.getloadavg()
        result["load_1m"] = round(load_1m, 3)
        result["load_5m"] = round(load_5m, 3)
    except (AttributeError, OSError):
        pass
    try:
        values = {}
        with open("/proc/meminfo", encoding="ascii") as source:
            for line in source:
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0])
        result["memory_available_percent"] = round(
            100 * values["MemAvailable"] / values["MemTotal"],
            2,
        )
        if values.get("SwapTotal", 0):
            result["swap_free_percent"] = round(
                100 * values["SwapFree"] / values["SwapTotal"],
                2,
            )
    except (OSError, KeyError, ValueError):
        pass
    return result


def _cpu_sample() -> tuple[int, int] | None:
    """Return Linux aggregate CPU total and idle ticks for a short utilization sample."""

    try:
        with open("/proc/stat", encoding="ascii") as source:
            fields = source.readline().split()
        if not fields or fields[0] != "cpu":
            return None
        ticks = [int(value) for value in fields[1:]]
        total = sum(ticks)
        idle = ticks[3] + (ticks[4] if len(ticks) > 4 else 0)
        return total, idle
    except (OSError, ValueError, IndexError):
        return None


def _cpu_busy_percent(
    before: tuple[int, int] | None,
    after: tuple[int, int] | None,
) -> float | None:
    if before is None or after is None:
        return None
    total_delta = after[0] - before[0]
    idle_delta = after[1] - before[1]
    if total_delta <= 0:
        return None
    return round(100 * (total_delta - idle_delta) / total_delta, 2)


def _database_health() -> dict:
    if connection.vendor != "postgresql":
        result = {"vendor": connection.vendor}
        database_name = connection.settings_dict.get("NAME")
        if database_name and database_name != ":memory:":
            try:
                result["database_size_bytes"] = os.path.getsize(database_name)
            except (OSError, TypeError):
                pass
        return result
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                count(*) FILTER (WHERE state = 'active'),
                count(*) FILTER (WHERE wait_event_type = 'Lock'),
                pg_database_size(current_database())
            FROM pg_stat_activity
            WHERE datname = current_database()
            """
        )
        active, lock_waits, database_size_bytes = cursor.fetchone()
    return {
        "vendor": "postgresql",
        "active_connections": active,
        "lock_waits": lock_waits,
        "database_size_bytes": database_size_bytes,
    }


class Command(BaseCommand):
    help = (
        "Characterize shared-test collaboration capacity with retained synthetic fixtures. "
        "This is not a production capacity certification."
    )

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="http://127.0.0.1:8000")
        parser.add_argument("--host-header", default="backend")
        parser.add_argument("--levels", default="5,10,25,50,100")
        parser.add_argument("--request-timeout", type=float, default=10.0)
        parser.add_argument("--max-error-rate", type=float, default=0.02)
        parser.add_argument("--maximum-cpu-percent", type=float, default=90.0)
        parser.add_argument("--minimum-memory-available-percent", type=float, default=10.0)

    def handle(self, *args, **options):
        levels = [int(item) for item in options["levels"].split(",") if item.strip()]
        if not levels or levels != sorted(set(levels)) or levels[-1] > 100 or levels[0] < 1:
            raise CommandError("Levels must be unique ascending integers from 1 through 100.")
        run_id = timezone.now().strftime("%Y%m%d%H%M%S%f")
        database_baseline = _database_health()
        database_baseline_size = database_baseline.get("database_size_bytes")
        fixtures = self._prepare_fixtures(run_id, max(levels))
        self.stdout.write(
            json.dumps(
                {
                    "event": "capacity_probe_started",
                    "run_id": run_id,
                    "levels": levels,
                    "synthetic_only": True,
                    "production_capacity_claim": False,
                },
                sort_keys=True,
            )
        )
        completed = []
        try:
            for level in levels:
                cpu_before = _cpu_sample()
                measurements = self._run_level(fixtures[:level], options)
                cpu_after = _cpu_sample()
                health = {
                    "host": _host_health(),
                    "database": _database_health(),
                }
                health["host"]["cpu_busy_percent"] = _cpu_busy_percent(
                    cpu_before,
                    cpu_after,
                )
                database_size = health["database"].get("database_size_bytes")
                if isinstance(database_baseline_size, int) and isinstance(database_size, int):
                    health["database"]["growth_bytes_since_start"] = (
                        database_size - database_baseline_size
                    )
                failures = [
                    item
                    for item in measurements
                    if not item.expected
                    or (item.scenario != "revocation" and not 200 <= item.status < 300)
                ]
                error_rate = len(failures) / max(1, len(measurements))
                latencies = sorted(item.elapsed_ms for item in measurements)
                summary = {
                    "event": "capacity_level_completed",
                    "run_id": run_id,
                    "concurrent_users": level,
                    "same_incident_maximum": min(level, 25),
                    "requests": len(measurements),
                    "unexpected_error_rate": round(error_rate, 5),
                    "latency_ms": {
                        "p50": round(statistics.median(latencies), 2),
                        "p95": round(
                            latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
                            2,
                        ),
                        "maximum": round(max(latencies), 2),
                    },
                    "health": health,
                    "scenarios": self._scenario_summary(measurements),
                }
                summary["integrity"] = self._verify_integrity(fixtures[:level])
                self.stdout.write(json.dumps(summary, sort_keys=True))
                completed.append(level)
                if self._must_stop(summary, options):
                    self.stdout.write(
                        json.dumps(
                            {
                                "event": "capacity_probe_stopped_safely",
                                "run_id": run_id,
                                "last_completed_level": level,
                                "reason": "Configured health or error guard reached.",
                            },
                            sort_keys=True,
                        )
                    )
                    break
        finally:
            Token.objects.filter(user_id__in=[item["user"].id for item in fixtures]).delete()
        self.stdout.write(
            json.dumps(
                {
                    "event": "capacity_probe_finished",
                    "run_id": run_id,
                    "completed_levels": completed,
                    "highest_characterized_level": max(completed, default=0),
                    "fixtures_retained_hidden": True,
                    "tokens_revoked": True,
                    "production_capacity_claim": False,
                },
                sort_keys=True,
            )
        )

    @transaction.atomic
    def _prepare_fixtures(self, run_id: str, user_count: int) -> list[dict]:
        user_model = get_user_model()
        owner, _ = user_model.objects.get_or_create(
            username="synthetic_capacity_probe_owner",
            defaults={"first_name": "Synthetic capacity probe owner", "is_active": True},
        )
        owner.is_active = True
        owner.set_unusable_password()
        owner.save(update_fields=["is_active", "password"])
        UserRoleAssignment.objects.update_or_create(
            user=owner,
            defaults={"role": Role.ADMINISTRATOR, "assigned_by": owner},
        )
        LocalContingencyAccount.objects.update_or_create(
            user=owner,
            defaults={
                "reason": "Hidden synthetic collaboration capacity fixture.",
                "must_change_password": False,
                "is_synthetic_hidden": True,
                "created_by": owner,
            },
        )
        plans = []
        now = timezone.now()
        for index in range((user_count + 24) // 25):
            incident = Incident.objects.create(
                name=f"Synthetic collaboration capacity {run_id}-{index + 1}",
                incident_number=f"SYN-CAP-{run_id}-{index + 1}",
                created_by=owner,
            )
            period = OperationalPeriod.objects.create(
                incident=incident,
                name="Synthetic capacity period",
                starts_at=now,
                ends_at=now + timedelta(hours=12),
                created_by=owner,
            )
            plan = ICS205Plan.objects.create(
                incident=incident,
                operational_period=period,
                title="Synthetic capacity ICS 205",
                created_by=owner,
            )
            revision = PlanRevision.objects.create(
                plan=plan,
                number=1,
                created_by=owner,
            )
            plans.append((incident, revision))

        fixtures = []
        for index in range(user_count):
            incident, revision = plans[index // 25]
            username = f"synthetic_capacity_{run_id}_{index + 1:03d}"
            user = user_model.objects.create(
                username=username,
                first_name=f"Synthetic capacity user {index + 1}",
            )
            user.is_active = True
            user.set_unusable_password()
            user.save(update_fields=["is_active", "password"])
            UserRoleAssignment.objects.update_or_create(
                user=user,
                defaults={"role": Role.CONTRIBUTOR, "assigned_by": owner},
            )
            LocalContingencyAccount.objects.update_or_create(
                user=user,
                defaults={
                    "reason": "Hidden synthetic collaboration capacity fixture.",
                    "must_change_password": False,
                    "is_synthetic_hidden": True,
                    "created_by": owner,
                    "disabled_at": None,
                    "disabled_by": None,
                    "disabled_reason": "",
                },
            )
            IncidentMembership.objects.update_or_create(
                incident=incident,
                user=user,
                defaults={
                    "role": Role.CONTRIBUTOR,
                    "is_active": True,
                    "assigned_by": owner,
                },
            )
            assignment = Assignment.objects.create(
                revision=revision,
                position=(index % 25) + 1,
                function="Synthetic capacity",
                channel_name=f"SYN-{index + 1:03d}",
                assignment="Synthetic only",
                operating_classification=Assignment.OperatingClassification.FIXED_PAIR,
                rx_frequency_hz=150_000_000 + index,
                tx_frequency_hz=150_000_000 + index,
                resource_snapshot={
                    "type": "synthetic",
                    "source": "collaboration_capacity_probe",
                },
                contact_name=f"RESTRICTED-PROBE-{run_id}-{index + 1}",
            )
            Token.objects.filter(user=user).delete()
            token = Token.objects.create(user=user)
            fixtures.append(
                {
                    "user": user,
                    "token": token.key,
                    "incident": incident,
                    "revision": revision,
                    "assignment": assignment,
                }
            )
        return fixtures

    def _request(self, fixture, options, scenario, method, path, payload=None, expected=True):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {
            "Authorization": f"Token {fixture['token']}",
            "Content-Type": "application/json",
            "Host": options["host_header"],
            "X-Forwarded-Proto": "https",
        }
        request = urllib.request.Request(
            f"{options['base_url'].rstrip('/')}{path}",
            data=body,
            method=method,
            headers=headers,
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=options["request_timeout"]) as response:
                status_code = response.status
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            response_body = exc.read()
        except (OSError, TimeoutError):
            status_code = 0
            response_body = b""
        elapsed_ms = (time.perf_counter() - started) * 1000
        return RequestMeasurement(scenario, status_code, elapsed_ms, expected), response_body

    def _run_level(self, fixtures, options) -> list[RequestMeasurement]:
        measurements = []
        with ThreadPoolExecutor(max_workers=len(fixtures)) as pool:
            futures = []
            for fixture in fixtures:
                assignment = Assignment.objects.get(pk=fixture["assignment"].pk)
                futures.extend(
                    [
                        (
                            pool.submit(
                                self._request,
                                fixture,
                                options,
                                "presence",
                                "POST",
                                "/api/collaboration/presence/",
                                {
                                    "revision": str(fixture["revision"].id),
                                    "device_id": str(uuid.uuid4()),
                                    "section": "ics205.assignments",
                                    "mode": "editing",
                                    "object_id": str(assignment.id),
                                    "field_name": "remarks",
                                },
                            ),
                            fixture,
                        ),
                        (
                            pool.submit(
                                self._request,
                                fixture,
                                options,
                                "independent_save",
                                "POST",
                                "/api/collaboration/mutations/",
                                {
                                    "client_mutation_id": str(uuid.uuid4()),
                                    "device_id": str(uuid.uuid4()),
                                    "revision": str(fixture["revision"].id),
                                    "operation": "assignment.update",
                                    "object_id": str(assignment.id),
                                    "section": "ics205.assignments",
                                    "base_version": assignment.collaboration_version,
                                    "changes": {
                                        "remarks": (
                                            f"Synthetic capacity level {len(fixtures)} "
                                            f"user {fixture['user'].id}"
                                        )
                                    },
                                },
                            ),
                            fixture,
                        ),
                        (
                            pool.submit(
                                self._request,
                                fixture,
                                options,
                                "incident_read",
                                "GET",
                                "/api/ics205-plans/",
                            ),
                            fixture,
                        ),
                    ]
                )
            for future, fixture in futures:
                measurement, body = future.result()
                if measurement.scenario == "incident_read":
                    try:
                        response = json.loads(body)
                        incident_ids = {item["incident"] for item in response.get("results", [])}
                    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                        incident_ids = set()
                    if b"RESTRICTED-PROBE-" in body:
                        measurement.status = 598
                    elif incident_ids != {str(fixture["incident"].id)}:
                        measurement.status = 596
                measurements.append(measurement)

        same_incident = fixtures[: min(len(fixtures), 10)]
        shared = same_incident[0]["assignment"]
        shared.refresh_from_db()
        with ThreadPoolExecutor(max_workers=len(same_incident)) as pool:
            futures = [
                pool.submit(
                    self._request,
                    fixture,
                    options,
                    "same_field_conflict",
                    "POST",
                    "/api/collaboration/mutations/",
                    {
                        "client_mutation_id": str(uuid.uuid4()),
                        "device_id": str(uuid.uuid4()),
                        "revision": str(fixture["revision"].id),
                        "operation": "assignment.update",
                        "object_id": str(shared.id),
                        "section": "ics205.assignments",
                        "base_version": shared.collaboration_version,
                        "changes": {"remarks": f"Contender {fixture['user'].id}"},
                    },
                    False,
                )
                for fixture in same_incident
            ]
            dispositions = []
            conflict_results = []
            for future in futures:
                measurement, body = future.result()
                try:
                    dispositions.append(json.loads(body).get("disposition"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    dispositions.append(None)
                conflict_results.append(measurement)
            valid_conflict_outcome = (
                dispositions.count("saved") == 1
                and dispositions.count("conflict") == len(dispositions) - 1
            )
            for measurement in conflict_results:
                measurement.expected = valid_conflict_outcome
                if not valid_conflict_outcome:
                    measurement.status = 597
                measurements.append(measurement)

        revoked = fixtures[-1]
        membership = IncidentMembership.objects.get(
            incident=revoked["incident"],
            user=revoked["user"],
        )
        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
        measurement, _ = self._request(
            revoked,
            options,
            "revocation",
            "POST",
            "/api/collaboration/presence/",
            {
                "revision": str(revoked["revision"].id),
                "device_id": str(uuid.uuid4()),
                "section": "ics205",
                "mode": "viewing",
            },
            expected=False,
        )
        measurement.expected = measurement.status in {403, 404}
        measurements.append(measurement)
        membership.is_active = True
        membership.save(update_fields=["is_active", "updated_at"])

        Token.objects.filter(user=revoked["user"]).delete()
        replacement = Token.objects.create(user=revoked["user"])
        revoked["token"] = replacement.key
        measurement, _ = self._request(
            revoked,
            options,
            "reconnect",
            "GET",
            "/api/ics205-plans/",
        )
        measurements.append(measurement)
        measurement, _ = self._request(
            revoked,
            options,
            "recovery_health",
            "GET",
            "/api/health/",
        )
        measurements.append(measurement)
        return measurements

    def _scenario_summary(self, measurements) -> dict:
        summary = {}
        for scenario in sorted({item.scenario for item in measurements}):
            items = [item for item in measurements if item.scenario == scenario]
            latencies = sorted(item.elapsed_ms for item in items)
            summary[scenario] = {
                "requests": len(items),
                "statuses": sorted({item.status for item in items}),
                "expected_outcome": all(item.expected for item in items),
                "p95_ms": round(
                    latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
                    2,
                ),
            }
        return summary

    def _verify_integrity(self, fixtures):
        if any(
            item["assignment"].revision.plan.incident_id != item["incident"].id for item in fixtures
        ):
            raise CommandError("Cross-incident fixture integrity failed.")
        shared_assignment_id = fixtures[0]["assignment"].id
        for fixture in fixtures:
            assignment = Assignment.objects.get(pk=fixture["assignment"].id)
            if assignment.id == shared_assignment_id:
                if not assignment.remarks.startswith("Contender "):
                    raise CommandError("Same-field conflict did not retain the winning value.")
                continue
            expected = f"Synthetic capacity level {len(fixtures)} user {fixture['user'].id}"
            if assignment.remarks != expected:
                raise CommandError(
                    f"Independent save integrity failed for assignment {assignment.id}."
                )
        valid, broken_at = verify_audit_chain()
        if not valid:
            raise CommandError(f"Audit chain failed at {broken_at}.")
        return {
            "audit_chain_valid": True,
            "cross_incident_isolation_valid": True,
            "independent_saves_valid": True,
            "same_field_conflict_valid": True,
            "restricted_field_leakage_detected": False,
        }

    def _must_stop(self, summary, options) -> bool:
        if summary["unexpected_error_rate"] > options["max_error_rate"]:
            return True
        host = summary["health"]["host"]
        memory = host.get("memory_available_percent")
        if memory is not None and memory < options["minimum_memory_available_percent"]:
            return True
        swap = host.get("swap_free_percent")
        if swap is not None and swap < 10:
            return True
        load_5m = host.get("load_5m")
        if load_5m is not None and load_5m > max(2, (os.cpu_count() or 1) * 1.5):
            return True
        cpu_busy = host.get("cpu_busy_percent")
        if cpu_busy is not None and cpu_busy > options["maximum_cpu_percent"]:
            return True
        if summary["health"]["database"].get("lock_waits", 0) > 0:
            return True
        return False
