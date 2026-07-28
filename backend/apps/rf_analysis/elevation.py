from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ElevationSource:
    provider: str
    dataset_product: str
    horizontal_crs: str
    vertical_crs: str
    target_vertical_crs: str
    resolution_m: str | None
    source_version: str
    license_terms_url: str
    permitted_use: str
    coverage: dict[str, Any]
    source_content_sha256: str
    offline: bool


@dataclass(frozen=True)
class ElevationBatch:
    source: ElevationSource
    acquisition_state: str
    samples: list[dict[str, Any]]
    transformation: dict[str, Any]
    warnings: list[str]
    retrieved_at: Any


class ElevationProvider(ABC):
    @property
    @abstractmethod
    def source(self) -> ElevationSource:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, points: list[dict[str, Any]]) -> ElevationBatch:
        raise NotImplementedError


class ElevationProviderError(Exception):
    """Expected, operator-retryable provider failure without sensitive detail."""


class DisabledElevationProvider(ElevationProvider):
    @property
    def source(self) -> ElevationSource:
        return ElevationSource(
            provider="disabled",
            dataset_product="No elevation source configured",
            horizontal_crs="EPSG:4326",
            vertical_crs="unknown",
            target_vertical_crs="unknown",
            resolution_m=None,
            source_version="",
            license_terms_url="",
            permitted_use="No source material is enabled.",
            coverage={},
            source_content_sha256="",
            offline=True,
        )

    def fetch(self, points: list[dict[str, Any]]) -> ElevationBatch:
        samples = [
            {
                **point,
                "elevation_m": None,
                "transformed_elevation_m": None,
                "state": "missing",
                "reason": "No elevation provider is configured.",
            }
            for point in points
        ]
        return ElevationBatch(
            source=self.source,
            acquisition_state="missing",
            samples=samples,
            transformation={
                "method": "none",
                "source_vertical_crs": "unknown",
                "target_vertical_crs": "unknown",
            },
            warnings=[
                "Elevation retrieval is disabled. Configure and approve a source or use the "
                "documented offline fallback."
            ],
            retrieved_at=timezone.now(),
        )


class SyntheticElevationProvider(ElevationProvider):
    """Deterministic, offline-only terrain for tests, training, and demonstrations."""

    @property
    def source(self) -> ElevationSource:
        mode = settings.ICT_SYNTHETIC_ELEVATION_MODE
        descriptor = {
            "provider": "synthetic-offline",
            "dataset_product": f"ICT Toolkit deterministic terrain fixture ({mode})",
            "source_version": "synthetic-terrain-v1",
            "mode": mode,
        }
        return ElevationSource(
            provider=descriptor["provider"],
            dataset_product=descriptor["dataset_product"],
            horizontal_crs="EPSG:4326",
            vertical_crs=("SYNTHETIC:LOCAL-OFFSET" if mode == "datum" else "SYNTHETIC:LOCAL"),
            target_vertical_crs="SYNTHETIC:LOCAL",
            resolution_m="30.000",
            source_version=descriptor["source_version"],
            license_terms_url=(
                "https://github.com/Texas-Communications-Unit/ict-branch-toolkit/blob/main/"
                "docs/operations/elevation-and-haat.md#offline-synthetic-fixture"
            ),
            permitted_use=(
                "Synthetic fixture data only; not terrain, not for operational decision support."
            ),
            coverage={"type": "synthetic", "extent": "global"},
            source_content_sha256=canonical_digest(descriptor),
            offline=True,
        )

    def fetch(self, points: list[dict[str, Any]]) -> ElevationBatch:
        mode = settings.ICT_SYNTHETIC_ELEVATION_MODE
        if mode == "failure":
            raise ElevationProviderError("Synthetic provider failure fixture.")
        samples = [self._sample(point, index, mode) for index, point in enumerate(points)]
        present = [sample for sample in samples if sample["state"] == "complete"]
        outside = [sample for sample in samples if sample["state"] == "out_of_coverage"]
        if not present:
            state = "out_of_coverage" if outside else "missing"
        elif len(present) != len(samples):
            state = "partial"
        else:
            state = "complete"
        offset = Decimal("10") if mode == "datum" else Decimal("0")
        warnings = [
            "Synthetic elevation fixture: results do not represent actual terrain and must not "
            "be used for operational decisions."
        ]
        if state != "complete":
            warnings.append(f"Synthetic fixture returned {state} elevation coverage.")
        return ElevationBatch(
            source=self.source,
            acquisition_state=state,
            samples=samples,
            transformation={
                "method": "constant_offset_fixture" if offset else "identity",
                "source_vertical_crs": "SYNTHETIC:LOCAL-OFFSET" if offset else "SYNTHETIC:LOCAL",
                "target_vertical_crs": "SYNTHETIC:LOCAL",
                "offset_m": format(offset, "f"),
                "grid_or_model": "synthetic-fixture",
            },
            warnings=warnings,
            retrieved_at=timezone.now(),
        )

    @staticmethod
    def _sample(point: dict[str, Any], index: int, mode: str) -> dict[str, Any]:
        if mode == "out_of_coverage":
            return {
                **point,
                "elevation_m": None,
                "transformed_elevation_m": None,
                "state": "out_of_coverage",
                "reason": "Synthetic out-of-coverage fixture.",
            }
        if mode == "missing" and point["role"] == "terrain" and index % 3 == 0:
            return {
                **point,
                "elevation_m": None,
                "transformed_elevation_m": None,
                "state": "missing",
                "reason": "Synthetic missing-data fixture.",
            }
        if (
            mode == "boundary"
            and point["role"] == "terrain"
            and Decimal(str(point["distance_m"])) > Decimal("9000")
        ):
            return {
                **point,
                "elevation_m": None,
                "transformed_elevation_m": None,
                "state": "out_of_coverage",
                "reason": "Synthetic coverage boundary.",
            }

        distance_km = Decimal(str(point["distance_m"])) / Decimal("1000")
        azimuth = Decimal(str(point["azimuth_deg"] or 0))
        if mode == "slope":
            transformed = Decimal("100") + distance_km
        elif mode == "rugged":
            wave = Decimal(str(round(25 * math.sin(math.radians(float(azimuth) * 3)), 6)))
            transformed = Decimal("100") + wave + (distance_km / Decimal("4"))
        else:
            transformed = Decimal("100")
        raw = transformed - Decimal("10") if mode == "datum" else transformed
        return {
            **point,
            "elevation_m": format(raw.quantize(Decimal("0.001")), "f"),
            "transformed_elevation_m": format(
                transformed.quantize(Decimal("0.001")),
                "f",
            ),
            "state": "complete",
            "reason": "",
        }


def configured_elevation_provider() -> ElevationProvider:
    provider_class = import_string(settings.ICT_ELEVATION_PROVIDER)
    provider = provider_class()
    if not isinstance(provider, ElevationProvider):
        raise TypeError("Configured elevation provider must implement ElevationProvider.")
    return provider


def source_is_approved(source: ElevationSource) -> bool:
    if source.provider == "disabled":
        return False
    if source.license_terms_url:
        terms_url = urlparse(source.license_terms_url)
        if terms_url.scheme not in {"http", "https"} or not terms_url.netloc:
            return False
    approval_fields = (
        "provider",
        "dataset_product",
        "horizontal_crs",
        "vertical_crs",
        "target_vertical_crs",
        "resolution_m",
        "source_version",
        "license_terms_url",
        "permitted_use",
        "coverage",
        "source_content_sha256",
        "offline",
    )
    for approval in settings.ICT_APPROVED_ELEVATION_SOURCES:
        if not isinstance(approval, dict):
            continue
        if all(approval.get(field) == getattr(source, field) for field in approval_fields):
            return True
    return False


def provider_status() -> dict[str, Any]:
    provider = configured_elevation_provider()
    source = provider.source
    approved = source_is_approved(source)
    return {
        **asdict(source),
        "configured": source.provider != "disabled",
        "approved": approved,
        "available": source.provider != "disabled" and approved,
        "warning": (
            ""
            if approved
            else (
                "No elevation provider is configured."
                if source.provider == "disabled"
                else "The configured elevation source is not in the server approval allowlist."
            )
        ),
    }
