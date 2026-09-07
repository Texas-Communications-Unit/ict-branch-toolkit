import io
import json
from unittest.mock import patch

from apps.rf_analysis.elevation import USGS3DEPElevationProvider
from apps.rf_analysis.terrain import USGS3DEPTerrainProfileProvider
from apps.rf_analysis.usgs_3dep import _fetch_one
from apps.sites.geocoders import CensusGeocoder, GeocoderError


class JsonResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def json_response(payload):
    return JsonResponse(json.dumps(payload).encode())


def test_usgs_point_response_retains_provenance():
    payload = {
        "value": "199.884017944",
        "rasterId": 5578,
        "resolution": 0.00009259259341472414,
        "attributes": {"AcquisitionDate": "11/6/2019"},
    }
    with patch("apps.rf_analysis.usgs_3dep.urlopen", return_value=json_response(payload)):
        result = _fetch_one({"latitude": "33.2145", "longitude": "-97.1331"})
    assert result["elevation_m"] == "199.884"
    assert result["raster_id"] == 5578
    assert result["acquisition_date"] == "11/6/2019"


def test_usgs_elevation_provider_maps_real_samples():
    returned = [
        {
            "role": "site",
            "latitude": "33",
            "longitude": "-97",
            "distance_m": 0,
            "azimuth_deg": None,
            "elevation_m": "200.000",
            "resolution_degrees": "0.0001",
            "raster_id": 1,
            "acquisition_date": "1/1/2025",
        }
    ]
    with patch("apps.rf_analysis.elevation.fetch_points", return_value=returned):
        batch = USGS3DEPElevationProvider().fetch([{"role": "site"}])
    assert batch.acquisition_state == "complete"
    assert batch.samples[0]["transformed_elevation_m"] == "200.000"
    assert batch.samples[0]["source_raster_id"] == 1


def test_usgs_terrain_provider_maps_real_samples():
    returned = [
        {
            "distance_m": 0,
            "latitude": "33",
            "longitude": "-97",
            "elevation_m": "200.000",
            "resolution_degrees": "0.0001",
            "raster_id": 1,
            "acquisition_date": "1/1/2025",
        }
    ]
    with patch("apps.rf_analysis.terrain.fetch_points", return_value=returned):
        batch = USGS3DEPTerrainProfileProvider().fetch([{"distance_m": 0}])
    assert batch.acquisition_state == "complete"
    assert batch.samples[0]["terrain_elevation_m"] == "200.000"


def test_census_geocoder_maps_address_matches():
    payload = {
        "result": {
            "addressMatches": [
                {
                    "matchedAddress": "1 MAIN ST, DENTON, TX, 76201",
                    "coordinates": {"x": -97.1331, "y": 33.2145},
                }
            ]
        }
    }
    with patch("apps.sites.geocoders.urlopen", return_value=json_response(payload)):
        result = CensusGeocoder().search("1 Main St, Denton, TX 76201")
    assert result[0].provider == "us-census-maf-tiger"
    assert result[0].latitude == 33.2145


def test_census_geocoder_returns_bounded_failure():
    with patch("apps.sites.geocoders.urlopen", side_effect=ValueError("private detail")):
        try:
            CensusGeocoder().search("1 Main St")
        except GeocoderError as exc:
            assert str(exc) == "The U.S. Census Geocoder is temporarily unavailable."
        else:
            raise AssertionError("Expected GeocoderError")
