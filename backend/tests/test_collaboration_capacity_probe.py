import pytest

from apps.collaboration.management.commands.probe_collaboration_capacity import (
    RequestMeasurement,
    _measurement_is_unexpected,
)


@pytest.mark.parametrize(
    ("scenario", "status", "expected_outcome", "is_unexpected"),
    [
        ("incident_read", 200, True, False),
        ("presence", 201, True, False),
        ("incident_read", 500, True, True),
        ("incident_read", 0, True, True),
        ("same_field_conflict", 200, True, False),
        ("same_field_conflict", 409, True, False),
        ("same_field_conflict", 500, True, True),
        ("same_field_conflict", 409, False, True),
        ("revocation", 403, True, False),
        ("revocation", 404, True, False),
        ("revocation", 200, False, True),
    ],
)
def test_measurement_is_unexpected(
    scenario,
    status,
    expected_outcome,
    is_unexpected,
):
    measurement = RequestMeasurement(
        scenario=scenario,
        status=status,
        elapsed_ms=1.0,
        expected=expected_outcome,
    )

    assert _measurement_is_unexpected(measurement) is is_unexpected


def test_expected_same_field_conflicts_do_not_inflate_error_rate():
    measurements = [
        RequestMeasurement("same_field_conflict", 200, 1.0, True),
        *[RequestMeasurement("same_field_conflict", 409, 1.0, True) for _ in range(4)],
    ]

    failures = [item for item in measurements if _measurement_is_unexpected(item)]

    assert failures == []
