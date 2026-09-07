import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class GeocoderResult:
    label: str
    latitude: float
    longitude: float
    provider: str


class DisabledGeocoder:
    name = "disabled"

    def search(self, query: str) -> list[GeocoderResult]:
        return []


class DeterministicTestGeocoder:
    """Synthetic provider used only by automated tests and local demonstrations."""

    name = "synthetic-test-provider"

    def search(self, query: str) -> list[GeocoderResult]:
        if query.strip().lower() != "synthetic eoc":
            return []
        return [
            GeocoderResult(
                label="Synthetic EOC (test fixture)",
                latitude=33.2145,
                longitude=-97.1331,
                provider=self.name,
            )
        ]


class GeocoderError(Exception):
    """Expected external geocoder failure safe for an operator-facing response."""


class CensusGeocoder:
    """U.S. Census public MAF/TIGER single-line address geocoder."""

    name = "us-census-maf-tiger"
    endpoint = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

    def search(self, query: str) -> list[GeocoderResult]:
        parameters = {
            "address": query,
            "benchmark": "Public_AR_Current",
            "format": "json",
        }
        url = f"{self.endpoint}?{urlencode(parameters)}"
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "ICT-Branch-Toolkit/0.2"},
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310
                payload = json.load(response)
            matches = payload["result"]["addressMatches"]
            return [
                GeocoderResult(
                    label=match["matchedAddress"],
                    latitude=float(match["coordinates"]["y"]),
                    longitude=float(match["coordinates"]["x"]),
                    provider=self.name,
                )
                for match in matches[:10]
            ]
        except (
            HTTPError,
            URLError,
            TimeoutError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise GeocoderError("The U.S. Census Geocoder is temporarily unavailable.") from exc


def configured_geocoder():
    provider_class = import_string(settings.ICT_GEOCODER_PROVIDER)
    return provider_class()
