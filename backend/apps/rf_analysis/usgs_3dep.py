from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

EPQS_URL = "https://epqs.nationalmap.gov/v1/json"
EPQS_TIMEOUT_SECONDS = 15
EPQS_WORKERS = 8


class USGS3DEPError(Exception):
    """Bounded public-service failure without leaking request details."""


def _fetch_one(point: dict[str, Any]) -> dict[str, Any]:
    query = urlencode(
        {
            "x": point["longitude"],
            "y": point["latitude"],
            "units": "Meters",
            "wkid": 4326,
            "includeDate": "true",
        }
    )
    request = Request(
        f"{EPQS_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "ICT-Branch-Toolkit/0.2"},
    )
    try:
        with urlopen(request, timeout=EPQS_TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = json.load(response)
        elevation = Decimal(str(payload["value"]))
        if not elevation.is_finite() or elevation <= Decimal("-1000000"):
            raise ValueError
        resolution_degrees = Decimal(str(payload["resolution"]))
        if not resolution_degrees.is_finite() or resolution_degrees <= 0:
            raise ValueError
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
    ) as exc:
        raise USGS3DEPError("USGS 3DEP did not return a usable elevation sample.") from exc

    return {
        **point,
        "elevation_m": format(elevation.quantize(Decimal("0.001")), "f"),
        "resolution_degrees": format(resolution_degrees, "f"),
        "raster_id": payload.get("rasterId"),
        "acquisition_date": payload.get("attributes", {}).get("AcquisitionDate", ""),
    }


def fetch_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not points:
        return []
    results: list[dict[str, Any] | None] = [None] * len(points)
    with ThreadPoolExecutor(max_workers=min(EPQS_WORKERS, len(points))) as executor:
        futures = {executor.submit(_fetch_one, point): index for index, point in enumerate(points)}
        for future in as_completed(futures):
            index = futures[future]
            results[index] = future.result()
    return [result for result in results if result is not None]
