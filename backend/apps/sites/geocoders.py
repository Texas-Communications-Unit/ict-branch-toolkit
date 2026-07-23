from dataclasses import dataclass

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


def configured_geocoder():
    provider_class = import_string(settings.ICT_GEOCODER_PROVIDER)
    return provider_class()
