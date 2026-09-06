"""Tests for the bounded public Sentinel-3 SLSTR FRP provider."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.terralyra_ignis.models import ProviderStatus
from custom_components.terralyra_ignis.monitoring import MonitoredLocation
from custom_components.terralyra_ignis.products.sentinel3 import (
    MAX_FEATURES,
    Sentinel3Client,
    Sentinel3InvalidResponseError,
    Sentinel3Response,
    Sentinel3TemporaryServiceError,
    parse_sentinel3_geojson,
)
from custom_components.terralyra_ignis.providers.base import (
    ProviderUnavailableError,
)
from custom_components.terralyra_ignis.providers.factory import build_provider_pool
from custom_components.terralyra_ignis.providers.sentinel3 import (
    Sentinel3ActiveFireProvider,
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


def _feature(*, satellite: str = "S3A") -> dict:
    return {
        "type": "Feature",
        "id": f"Sentinel3{satellite[-1]}_SLSTR_L2P_FRP_2609071100_lod0.1",
        "geometry": {"type": "Point", "coordinates": [139.6503, 35.6762]},
        "properties": {
            "Lat": 35.6762,
            "Lon": 139.6503,
            "FRP": 12.5,
            "FRPerr": 1.25,
            "UsedChannel": "F1",
            "Confidence": 87.5,
            "BT": 320.0,
            "SZA": 42.0,
            "AcrossSize": 1.1,
            "AlongSize": 1.3,
            "Satellite": satellite,
            "Datetime": "2026-09-07T11:20:00",
            "time": "2026-09-07T11:00:00Z",
        },
    }


def _payload(*features: dict) -> bytes:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": list(features),
            "numberMatched": len(features),
            "numberReturned": len(features),
            "timeStamp": "2026-09-07T12:00:02Z",
        }
    ).encode()


def test_geojson_parser_preserves_science_fields() -> None:
    response = parse_sentinel3_geojson(
        _payload(_feature()),
        satellite="S3A",
        window_start=NOW - timedelta(hours=24),
        window_end=NOW,
    )

    assert response.service_timestamp == NOW + timedelta(seconds=2)
    assert len(response.detections) == 1
    detection = response.detections[0]
    assert detection.satellite == "S3A"
    assert detection.acquired == datetime(2026, 9, 7, 11, 20, tzinfo=UTC)
    assert detection.frp_mw == pytest.approx(12.5)
    assert detection.frp_uncertainty_mw == pytest.approx(1.25)
    assert detection.confidence == pytest.approx(0.875)
    assert detection.used_channel == "F1"


def test_empty_current_feature_collection_is_valid_zero_fire_result() -> None:
    response = parse_sentinel3_geojson(
        _payload(),
        satellite="S3B",
        window_start=NOW - timedelta(hours=24),
        window_end=NOW,
    )

    assert response.detections == ()
    assert response.service_timestamp == NOW + timedelta(seconds=2)


@pytest.mark.parametrize(
    "change",
    [
        {"Satellite": "S3B"},
        {"Confidence": 101},
        {"UsedChannel": "SWIR"},
        {"Lon": 181},
        {"FRP": -1},
    ],
)
def test_geojson_parser_rejects_invalid_feature_identity(change: dict) -> None:
    feature = _feature()
    feature["properties"].update(change)

    with pytest.raises(Sentinel3InvalidResponseError):
        parse_sentinel3_geojson(
            _payload(feature),
            satellite="S3A",
            window_start=NOW - timedelta(hours=24),
            window_end=NOW,
        )


def test_geojson_parser_rejects_truncated_result_set() -> None:
    document = json.loads(_payload(_feature()))
    document["numberMatched"] = MAX_FEATURES + 1

    with pytest.raises(Sentinel3InvalidResponseError):
        parse_sentinel3_geojson(
            json.dumps(document).encode(),
            satellite="S3A",
            window_start=NOW - timedelta(hours=24),
            window_end=NOW,
        )


class _Content:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def iter_chunked(self, _size: int):
        yield self._payload


class _Response:
    status = 200
    content_length = None

    def __init__(self, payload: bytes) -> None:
        self.headers = {"Content-Type": "application/json"}
        self.content = _Content(payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _Session:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.kwargs = None

    def get(self, _url: str, **kwargs):
        self.kwargs = kwargs
        return _Response(self.payload)


@pytest.mark.asyncio
async def test_client_builds_one_bounded_multi_area_query() -> None:
    session = _Session(_payload())
    client = Sentinel3Client(session)

    await client.async_area(
        satellite="S3B",
        bounds=((138.0, 34.0, 142.0, 37.0), (-122.0, 37.0, -120.0, 39.0)),
        now=NOW,
    )

    params = session.kwargs["params"]
    assert params["typeNames"] == "copernicus:sentinel3b_slstr_level2_frp"
    assert "BBOX(geom,138,34,142,37,'EPSG:4326')" in params["CQL_FILTER"]
    assert "BBOX(geom,-122,37,-120,39,'EPSG:4326')" in params["CQL_FILTER"]
    assert (
        "time DURING 2026-09-06T12:00:00Z/2026-09-07T12:00:00Z" in params["CQL_FILTER"]
    )
    assert params["count"] == str(MAX_FEATURES + 1)
    assert session.kwargs["allow_redirects"] is False


class _Client:
    async def async_area(self, **kwargs) -> Sentinel3Response:
        return parse_sentinel3_geojson(
            _payload(_feature(satellite=kwargs["satellite"])),
            satellite=kwargs["satellite"],
            window_start=NOW - timedelta(hours=24),
            window_end=NOW,
        )


def test_geojson_parser_rejects_feature_id_from_other_layer() -> None:
    feature = _feature()
    feature["id"] = "Sentinel3B_SLSTR_L2P_FRP_2609071100_lod0.1"

    with pytest.raises(Sentinel3InvalidResponseError):
        parse_sentinel3_geojson(
            _payload(feature),
            satellite="S3A",
            window_start=NOW - timedelta(hours=24),
            window_end=NOW,
        )


@pytest.mark.asyncio
async def test_provider_normalizes_sentinel3_detection(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.terralyra_ignis.providers.sentinel3.datetime",
        type("Clock", (), {"now": staticmethod(lambda _tz: NOW)}),
    )
    provider = Sentinel3ActiveFireProvider(
        _Client(), satellite="S3A", bounds=((138.0, 34.0, 142.0, 37.0),)
    )

    snapshot = await provider.async_fetch_latest()

    assert snapshot.provider == "eumetsat_sentinel3a"
    assert snapshot.satellite == "S3A"
    assert snapshot.status is ProviderStatus.AVAILABLE
    detection = snapshot.detections[0]
    assert detection.provider == "eumetsat_sentinel3a"
    assert detection.classification == "MWIR_F1"
    assert detection.fire_area_km2 == pytest.approx(1.43)
    assert detection.source_resolution_km == pytest.approx(1.3)


@pytest.mark.asyncio
async def test_provider_isolates_temporary_service_failure() -> None:
    class FailingClient:
        async def async_area(self, **_kwargs):
            raise Sentinel3TemporaryServiceError("temporary")

    provider = Sentinel3ActiveFireProvider(
        FailingClient(), satellite="S3B", bounds=((138.0, 34.0, 142.0, 37.0),)
    )

    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_latest()


def test_factory_queries_only_locations_inside_conservative_coverage() -> None:
    def location(location_id: str, latitude: float) -> MonitoredLocation:
        return MonitoredLocation(
            id=location_id,
            name=location_id,
            latitude=latitude,
            longitude=0.0,
            radius_km=50.0,
            enabled=True,
            source="manual",
        )

    pool, plans = build_provider_pool(
        object(),
        lambda *_args: None,
        locations=(location("tokyo-latitude", 35.67), location("arctic", 89.0)),
        username=None,
        password=None,
        firms_enabled=False,
        firms_map_key=None,
    )

    sentinel_bindings = tuple(
        item
        for item in pool.bindings
        if item.provider_id.startswith("eumetsat_sentinel3")
    )
    assert len(sentinel_bindings) == 2
    assert all(item.location_ids == ("tokyo-latitude",) for item in sentinel_bindings)
    assert plans[0].covered is True
    assert plans[1].covered is False
