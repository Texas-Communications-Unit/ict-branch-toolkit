from __future__ import annotations

import math
from dataclasses import asdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .elevation import (
    DisabledElevationProvider,
    ElevationProviderError,
    canonical_digest,
    configured_elevation_provider,
    source_is_approved,
)
from .models import ElevationSnapshot, HAATCalculation

METHOD = "general_radial_average_terrain"
METHOD_VERSION = "haat-radial-average-v1-provisional"
EARTH_RADIUS_M = 6_371_008.8
MAX_TERRAIN_SAMPLES = 10_000


def validate_parameters(
    *,
    radial_count: int,
    start_azimuth_deg: Decimal,
    sampling_interval_m: int,
    inner_distance_m: int,
    outer_distance_m: int,
    rounding_m: Decimal,
) -> None:
    errors = {}
    if not 4 <= radial_count <= 360:
        errors["radial_count"] = "Use 4 through 360 radials."
    if not Decimal("0") <= start_azimuth_deg < Decimal("360"):
        errors["start_azimuth_deg"] = "Use an azimuth from 0 through 359.999 degrees."
    if not 10 <= sampling_interval_m <= 100_000:
        errors["sampling_interval_m"] = "Use a sampling interval from 10 through 100000 meters."
    if not 1 <= inner_distance_m < outer_distance_m <= 100_000:
        errors["outer_distance_m"] = (
            "Inner and outer distances must be positive, with outer greater than inner and no "
            "more than 100000 meters."
        )
    if sampling_interval_m > outer_distance_m - inner_distance_m:
        errors["sampling_interval_m"] = (
            "The sampling interval cannot exceed the distance between the inner and outer limits."
        )
    if not Decimal("0.001") <= rounding_m <= Decimal("100"):
        errors["rounding_m"] = "Use a rounding increment from 0.001 through 100 meters."
    if sampling_interval_m > 0 and outer_distance_m > inner_distance_m:
        span = outer_distance_m - inner_distance_m
        distance_count = (span // sampling_interval_m) + 1
        if span % sampling_interval_m:
            distance_count += 1
        if radial_count * distance_count > MAX_TERRAIN_SAMPLES:
            errors["radial_count"] = (
                f"The requested grid exceeds the {MAX_TERRAIN_SAMPLES}-sample safety limit. "
                "Reduce radials or increase the sampling interval."
            )
    if errors:
        raise ValidationError(errors)


def _destination(latitude: Decimal, longitude: Decimal, azimuth: Decimal, distance_m: int):
    angular_distance = distance_m / EARTH_RADIUS_M
    bearing = math.radians(float(azimuth))
    lat1 = math.radians(float(latitude))
    lon1 = math.radians(float(longitude))
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    normalized_lon = (math.degrees(lon2) + 540) % 360 - 180
    return round(math.degrees(lat2), 8), round(normalized_lon, 8)


def build_query(
    site,
    *,
    radial_count: int,
    start_azimuth_deg: Decimal,
    sampling_interval_m: int,
    inner_distance_m: int,
    outer_distance_m: int,
) -> dict:
    azimuth_step = Decimal("360") / Decimal(radial_count)
    azimuths = [
        (start_azimuth_deg + (azimuth_step * index)) % Decimal("360")
        for index in range(radial_count)
    ]
    distances = list(range(inner_distance_m, outer_distance_m + 1, sampling_interval_m))
    if distances[-1] != outer_distance_m:
        distances.append(outer_distance_m)

    points = [
        {
            "key": "site",
            "role": "site",
            "latitude": float(site.latitude),
            "longitude": float(site.longitude),
            "azimuth_deg": None,
            "distance_m": 0,
        }
    ]
    for radial_index, azimuth in enumerate(azimuths, start=1):
        for distance_m in distances:
            latitude, longitude = _destination(
                site.latitude,
                site.longitude,
                azimuth,
                distance_m,
            )
            points.append(
                {
                    "key": f"r{radial_index:03d}-d{distance_m:06d}",
                    "role": "terrain",
                    "latitude": latitude,
                    "longitude": longitude,
                    "azimuth_deg": format(azimuth.quantize(Decimal("0.001")), "f"),
                    "distance_m": distance_m,
                }
            )
    return {
        "query_version": "elevation-radial-query-v1",
        "horizontal_crs": "EPSG:4326",
        "site": {
            "id": str(site.id),
            "latitude": format(site.latitude, "f"),
            "longitude": format(site.longitude, "f"),
        },
        "radial_count": radial_count,
        "start_azimuth_deg": format(start_azimuth_deg, "f"),
        "azimuth_step_deg": format(azimuth_step, "f"),
        "azimuths_deg": [format(azimuth.quantize(Decimal("0.001")), "f") for azimuth in azimuths],
        "sampling_interval_m": sampling_interval_m,
        "inner_distance_m": inner_distance_m,
        "outer_distance_m": outer_distance_m,
        "outer_endpoint_added": (outer_distance_m - inner_distance_m) % sampling_interval_m != 0,
        "distances_m": distances,
        "points": points,
    }


def _validate_batch(query: dict, batch) -> None:
    expected_keys = [point["key"] for point in query["points"]]
    actual_keys = [sample.get("key") for sample in batch.samples]
    if actual_keys != expected_keys:
        raise ValidationError(
            "The elevation provider returned a sample set that does not match the requested grid."
        )
    allowed_states = {"complete", "missing", "out_of_coverage"}
    invalid_states = {
        sample.get("state") for sample in batch.samples if sample.get("state") not in allowed_states
    }
    if invalid_states:
        raise ValidationError("The elevation provider returned an unsupported sample state.")
    if batch.acquisition_state not in {"complete", "partial", "missing", "out_of_coverage"}:
        raise ValidationError("The elevation provider returned an unsupported acquisition state.")
    states = [sample["state"] for sample in batch.samples]
    if all(state == "complete" for state in states):
        derived_state = "complete"
    elif all(state == "out_of_coverage" for state in states):
        derived_state = "out_of_coverage"
    elif not any(state == "complete" for state in states):
        derived_state = "missing"
    else:
        derived_state = "partial"
    if batch.acquisition_state != derived_state:
        raise ValidationError(
            "The elevation provider acquisition state does not match its sample states."
        )
    if not all(
        (
            batch.source.provider,
            batch.source.dataset_product,
            batch.source.horizontal_crs,
            batch.source.vertical_crs,
            batch.source.target_vertical_crs,
            batch.source.permitted_use,
        )
    ):
        raise ValidationError("The elevation provider returned incomplete source provenance.")
    if (
        batch.transformation.get("source_vertical_crs") != batch.source.vertical_crs
        or batch.transformation.get("target_vertical_crs") != batch.source.target_vertical_crs
        or not batch.transformation.get("method")
    ):
        raise ValidationError(
            "The elevation provider returned inconsistent vertical transformation provenance."
        )
    digest = batch.source.source_content_sha256
    if digest and (
        len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValidationError("The elevation provider returned an invalid source content digest.")
    if batch.source.license_terms_url:
        terms_url = urlparse(batch.source.license_terms_url)
        if terms_url.scheme not in {"http", "https"} or not terms_url.netloc:
            raise ValidationError(
                "The elevation provider returned an invalid license or terms reference."
            )
    for point, sample in zip(query["points"], batch.samples, strict=True):
        if any(
            sample.get(field) != point[field]
            for field in (
                "key",
                "role",
                "latitude",
                "longitude",
                "azimuth_deg",
                "distance_m",
            )
        ):
            raise ValidationError(
                "The elevation provider changed coordinates or sample-grid metadata."
            )
        if sample["state"] == "complete":
            for field in ("elevation_m", "transformed_elevation_m"):
                try:
                    elevation = Decimal(str(sample[field]))
                except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
                    raise ValidationError(
                        "The elevation provider returned a non-numeric elevation."
                    ) from exc
                if not elevation.is_finite() or not Decimal("-100000") <= elevation <= Decimal(
                    "100000"
                ):
                    raise ValidationError(
                        "The elevation provider returned an elevation outside defensive limits."
                    )
        elif any(
            sample.get(field) is not None for field in ("elevation_m", "transformed_elevation_m")
        ):
            raise ValidationError(
                "The elevation provider attached values to a non-complete sample."
            )


@transaction.atomic
def acquire_elevation_snapshot(site, query: dict, *, actor, force_refresh: bool):
    provider = configured_elevation_provider()
    cache_query = {
        "elevation_query": query,
        "selected_source": asdict(provider.source),
    }
    query_sha256 = canonical_digest(cache_query)
    now = timezone.now()
    if not force_refresh:
        cached = (
            ElevationSnapshot.objects.filter(
                incident=site.incident,
                site=site,
                query_sha256=query_sha256,
            )
            .filter(Q(stale_at__isnull=True) | Q(stale_at__gt=now))
            .order_by("-created_at")
            .first()
        )
        if cached:
            return cached, True

    if source_is_approved(provider.source):
        try:
            batch = provider.fetch(query["points"])
        except ElevationProviderError:
            disabled_batch = DisabledElevationProvider().fetch(query["points"])
            batch = type(disabled_batch)(
                source=provider.source,
                acquisition_state="missing",
                samples=disabled_batch.samples,
                transformation={
                    "method": "not_performed",
                    "source_vertical_crs": provider.source.vertical_crs,
                    "target_vertical_crs": provider.source.target_vertical_crs,
                },
                warnings=[
                    "The configured elevation provider could not complete retrieval. Review "
                    "provider availability and retry; no previous evidence was changed."
                ],
                retrieved_at=disabled_batch.retrieved_at,
            )
    else:
        disabled_batch = DisabledElevationProvider().fetch(query["points"])
        warning = (
            "The configured elevation source is not approved by server policy; no source "
            "retrieval was attempted."
            if provider.source.provider != "disabled"
            else disabled_batch.warnings[0]
        )
        batch = type(disabled_batch)(
            source=provider.source,
            acquisition_state="missing",
            samples=disabled_batch.samples,
            transformation={
                "method": "not_performed",
                "source_vertical_crs": provider.source.vertical_crs,
                "target_vertical_crs": provider.source.target_vertical_crs,
            },
            warnings=[warning],
            retrieved_at=disabled_batch.retrieved_at,
        )
    _validate_batch(query, batch)
    sample_sha256 = canonical_digest(batch.samples)
    stale_at = batch.retrieved_at + timedelta(seconds=settings.ICT_ELEVATION_CACHE_TTL_SECONDS)
    source = batch.source
    snapshot = ElevationSnapshot.objects.create(
        incident=site.incident,
        site=site,
        query_sha256=query_sha256,
        query_snapshot=cache_query,
        provider=source.provider,
        dataset_product=source.dataset_product,
        horizontal_crs=source.horizontal_crs,
        vertical_crs=source.vertical_crs,
        target_vertical_crs=source.target_vertical_crs,
        resolution_m=source.resolution_m,
        source_version=source.source_version,
        source_retrieved_at=batch.retrieved_at,
        license_terms_url=source.license_terms_url,
        permitted_use=source.permitted_use,
        coverage=source.coverage,
        source_content_sha256=source.source_content_sha256,
        acquisition_state=batch.acquisition_state,
        sample_snapshot=batch.samples,
        sample_sha256=sample_sha256,
        transformation=batch.transformation,
        warnings=batch.warnings,
        retrieved_at=batch.retrieved_at,
        stale_at=stale_at,
        created_by=actor,
    )
    return snapshot, False


def _round_increment(value: Decimal, increment: Decimal) -> Decimal:
    rounded = (value / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * increment
    return rounded.quantize(Decimal("0.001"))


@transaction.atomic
def create_haat_calculation(
    *,
    site,
    rf_input_snapshot,
    actor,
    radial_count: int,
    start_azimuth_deg: Decimal,
    sampling_interval_m: int,
    inner_distance_m: int,
    outer_distance_m: int,
    rounding_m: Decimal,
    force_refresh: bool = False,
    supersedes=None,
):
    profile_version = rf_input_snapshot.profile_version
    if site.incident_id != rf_input_snapshot.incident_id:
        raise ValidationError(
            "Site and RF analysis input snapshot must belong to the same incident."
        )
    if site.archived_at or rf_input_snapshot.archived_at:
        raise ValidationError("Archived sites and RF input snapshots cannot be analyzed.")
    if profile_version.antenna_center_agl_m is None:
        raise ValidationError(
            {
                "profile_version": (
                    "The selected profile version requires an explicit antenna-center AGL value."
                )
            }
        )
    validate_parameters(
        radial_count=radial_count,
        start_azimuth_deg=start_azimuth_deg,
        sampling_interval_m=sampling_interval_m,
        inner_distance_m=inner_distance_m,
        outer_distance_m=outer_distance_m,
        rounding_m=rounding_m,
    )
    query = build_query(
        site,
        radial_count=radial_count,
        start_azimuth_deg=start_azimuth_deg,
        sampling_interval_m=sampling_interval_m,
        inner_distance_m=inner_distance_m,
        outer_distance_m=outer_distance_m,
    )
    elevation_snapshot, cache_hit = acquire_elevation_snapshot(
        site,
        query,
        actor=actor,
        force_refresh=force_refresh,
    )
    samples = elevation_snapshot.sample_snapshot
    site_sample = samples[0]
    terrain_samples = samples[1:]
    valid_terrain = [
        Decimal(str(sample["transformed_elevation_m"]))
        for sample in terrain_samples
        if sample["state"] == "complete" and sample["transformed_elevation_m"] is not None
    ]
    exclusions = [
        {
            "key": sample["key"],
            "azimuth_deg": sample["azimuth_deg"],
            "distance_m": sample["distance_m"],
            "state": sample["state"],
            "reason": sample.get("reason", ""),
        }
        for sample in terrain_samples
        if sample["state"] != "complete" or sample["transformed_elevation_m"] is None
    ]
    warnings = list(elevation_snapshot.warnings)
    site_elevation = None
    antenna_amsl = None
    average_terrain = None
    haat = None
    if site_sample["state"] != "complete" or site_sample["transformed_elevation_m"] is None:
        state = HAATCalculation.CalculationState.UNAVAILABLE
        warnings.append("Site elevation is unavailable; HAAT was not calculated.")
    elif not valid_terrain:
        state = HAATCalculation.CalculationState.UNAVAILABLE
        warnings.append("No usable radial terrain samples are available; HAAT was not calculated.")
    else:
        site_elevation_raw = Decimal(str(site_sample["transformed_elevation_m"]))
        antenna_amsl_raw = site_elevation_raw + Decimal(profile_version.antenna_center_agl_m)
        average_terrain_raw = sum(valid_terrain, Decimal("0")) / Decimal(len(valid_terrain))
        haat_raw = antenna_amsl_raw - average_terrain_raw
        site_elevation = _round_increment(site_elevation_raw, rounding_m)
        antenna_amsl = _round_increment(antenna_amsl_raw, rounding_m)
        average_terrain = _round_increment(average_terrain_raw, rounding_m)
        haat = _round_increment(haat_raw, rounding_m)
        if exclusions or elevation_snapshot.acquisition_state != "complete":
            state = HAATCalculation.CalculationState.PARTIAL
            warnings.append(
                "HAAT used a partial terrain sample set. Review every exclusion before use."
            )
        else:
            state = HAATCalculation.CalculationState.COMPLETE

    algorithm_snapshot = {
        "method": METHOD,
        "method_version": METHOD_VERSION,
        "method_scope": (
            "General planning radial-average terrain method. It is not represented as the "
            "controlling method for any regulatory service."
        ),
        "earth_model": {
            "name": "mean-radius sphere",
            "radius_m": EARTH_RADIUS_M,
            "coordinate_reference_system": "EPSG:4326",
        },
        "radial_count": radial_count,
        "start_azimuth_deg": format(start_azimuth_deg, "f"),
        "azimuths_deg": query["azimuths_deg"],
        "sampling_interval_m": sampling_interval_m,
        "inner_distance_m": inner_distance_m,
        "outer_distance_m": outer_distance_m,
        "outer_endpoint_added": query["outer_endpoint_added"],
        "distances_m": query["distances_m"],
        "transformation": elevation_snapshot.transformation,
        "rounding_m": format(rounding_m, "f"),
        "rounding_stage": (
            "Calculate site elevation, antenna AMSL, average terrain, and HAAT from unrounded "
            "decimal inputs; round each reported output independently."
        ),
        "exclusion_rule": "Exclude samples whose provider state is not complete.",
        "partial_result_rule": (
            "Calculate from remaining samples when site elevation and at least one terrain "
            "sample are complete; mark the result partial."
        ),
    }
    profile_snapshot = rf_input_snapshot.input_snapshot
    result_snapshot = {
        "snapshot_version": "haat-result-v1",
        "incident_id": str(site.incident_id),
        "site": {
            "id": str(site.id),
            "name": site.name,
            "latitude": format(site.latitude, "f"),
            "longitude": format(site.longitude, "f"),
        },
        "profile_version": {
            "id": str(profile_version.id),
            "number": profile_version.number,
            "status_at_calculation": profile_version.status,
            "input_snapshot": profile_snapshot,
            "input_sha256": rf_input_snapshot.input_sha256,
        },
        "rf_input_snapshot": {
            "id": str(rf_input_snapshot.id),
            "label": rf_input_snapshot.label,
            "input_sha256": rf_input_snapshot.input_sha256,
            "approved_by_id": str(rf_input_snapshot.approved_by_id),
            "approved_at": rf_input_snapshot.approved_at.isoformat(),
        },
        "elevation_snapshot": {
            "id": str(elevation_snapshot.id),
            "query_sha256": elevation_snapshot.query_sha256,
            "sample_sha256": elevation_snapshot.sample_sha256,
            "provider": elevation_snapshot.provider,
            "dataset_product": elevation_snapshot.dataset_product,
            "source_version": elevation_snapshot.source_version,
            "acquisition_state": elevation_snapshot.acquisition_state,
        },
        "algorithm": algorithm_snapshot,
        "result": {
            "calculation_state": state,
            "antenna_agl_m": format(profile_version.antenna_center_agl_m, "f"),
            "site_elevation_m": format(site_elevation, "f") if site_elevation is not None else None,
            "antenna_amsl_m": format(antenna_amsl, "f") if antenna_amsl is not None else None,
            "average_terrain_m": (
                format(average_terrain, "f") if average_terrain is not None else None
            ),
            "haat_m": format(haat, "f") if haat is not None else None,
            "sample_count": len(valid_terrain),
            "excluded_sample_count": len(exclusions),
            "exclusions": exclusions,
            "warnings": warnings,
        },
    }
    calculation = HAATCalculation.objects.create(
        incident=site.incident,
        site=site,
        profile_version=profile_version,
        rf_input_snapshot=rf_input_snapshot,
        elevation_snapshot=elevation_snapshot,
        supersedes=supersedes,
        calculation_state=state,
        method=METHOD,
        method_version=METHOD_VERSION,
        radial_count=radial_count,
        start_azimuth_deg=start_azimuth_deg,
        sampling_interval_m=sampling_interval_m,
        inner_distance_m=inner_distance_m,
        outer_distance_m=outer_distance_m,
        rounding_m=rounding_m,
        antenna_agl_m=profile_version.antenna_center_agl_m,
        site_elevation_m=site_elevation,
        antenna_amsl_m=antenna_amsl,
        average_terrain_m=average_terrain,
        haat_m=haat,
        sample_count=len(valid_terrain),
        excluded_sample_count=len(exclusions),
        algorithm_snapshot=algorithm_snapshot,
        exclusions=exclusions,
        warnings=warnings,
        result_snapshot=result_snapshot,
        result_sha256=canonical_digest(result_snapshot),
        created_by=actor,
    )
    return calculation, cache_hit


@transaction.atomic
def approve_haat_calculation(calculation, *, actor):
    calculation = HAATCalculation.objects.select_for_update().get(pk=calculation.pk)
    if calculation.status == HAATCalculation.Status.APPROVED:
        raise ValidationError("This HAAT calculation is already approved.")
    if calculation.calculation_state != HAATCalculation.CalculationState.COMPLETE:
        raise ValidationError(
            "Only a complete HAAT calculation can be approved. Retry after resolving source "
            "coverage or missing-data warnings."
        )
    approved_at = timezone.now()
    HAATCalculation.objects.filter(
        pk=calculation.pk,
        status=HAATCalculation.Status.DRAFT,
    ).update(
        status=HAATCalculation.Status.APPROVED,
        approved_by=actor,
        approved_at=approved_at,
    )
    calculation.refresh_from_db()
    return calculation


def retry_haat_calculation(calculation, *, actor):
    return create_haat_calculation(
        site=calculation.site,
        rf_input_snapshot=calculation.rf_input_snapshot,
        actor=actor,
        radial_count=calculation.radial_count,
        start_azimuth_deg=calculation.start_azimuth_deg,
        sampling_interval_m=calculation.sampling_interval_m,
        inner_distance_m=calculation.inner_distance_m,
        outer_distance_m=calculation.outer_distance_m,
        rounding_m=calculation.rounding_m,
        force_refresh=True,
        supersedes=calculation,
    )
