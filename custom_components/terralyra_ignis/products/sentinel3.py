"""Bounded client for public Sentinel-3 SLSTR FRP WFS features."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .http import parse_retry_after

WFS_URL = "https://view.eumetsat.int/geoserver/wfs"
PUBLIC_SOURCE_URL = "https://view.eumetsat.int/"
LAYERS = {
    "S3A": "copernicus:sentinel3a_slstr_level2_frp",
    "S3B": "copernicus:sentinel3b_slstr_level2_frp",
}
QUERY_WINDOW = timedelta(hours=24)
TIMEOUT = ClientTimeout(total=40, connect=8, sock_read=30)
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_FEATURES = 10_000
MAX_AREAS = 10
MAX_BBOX_SPAN_DEGREES = 20.0
USER_AGENT = "ha-ignis (https://github.com/TerraLyra/ha-ignis)"
_ALLOWED_CHANNELS = frozenset({"S7", "F1"})
_FEATURE_ID_PREFIXES = {
    "S3A": "Sentinel3A_SLSTR_L2P_FRP_",
    "S3B": "Sentinel3B_SLSTR_L2P_FRP_",
}


class Sentinel3Error(Exception):
    """A Sentinel-3 request or response was invalid."""


class Sentinel3RateLimitError(Sentinel3Error):
    """EUMETView asked the client to reduce its request rate."""

    def __init__(self, message: str, retry_after: timedelta | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class Sentinel3TemporaryServiceError(Sentinel3Error):
    """EUMETView returned a temporary server-side error."""

    def __init__(self, message: str, retry_after: timedelta | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class Sentinel3TimeoutError(Sentinel3Error):
    """The bounded EUMETView request timed out."""


class Sentinel3InvalidResponseError(Sentinel3Error):
    """EUMETView returned data that failed safe validation."""


@dataclass(frozen=True, slots=True)
class Sentinel3Detection:
    """One validated SLSTR Level 2 FRP feature."""

    feature_id: str
    satellite: str
    acquired: datetime
    product_time: datetime
    latitude: float
    longitude: float
    frp_mw: float
    frp_uncertainty_mw: float
    confidence: float
    used_channel: str
    across_size_km: float
    along_size_km: float


@dataclass(frozen=True, slots=True)
class Sentinel3Response:
    """One complete, bounded WFS response."""

    service_timestamp: datetime
    detections: tuple[Sentinel3Detection, ...]


class Sentinel3Client:
    """Fetch recent SLSTR fire points from a fixed public WFS host."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def async_area(
        self,
        *,
        satellite: str,
        bounds: tuple[tuple[float, float, float, float], ...],
        now: datetime | None = None,
    ) -> Sentinel3Response:
        """Return at most one day of detections in bounded monitored areas."""
        if satellite not in LAYERS:
            raise Sentinel3Error("Unsupported Sentinel-3 satellite")
        _validate_bounds(bounds)
        current = _as_utc(now or datetime.now(UTC))
        start = current - QUERY_WINDOW
        spatial = " OR ".join(
            f"BBOX(geom,{_format(west)},{_format(south)},"
            f"{_format(east)},{_format(north)},'EPSG:4326')"
            for west, south, east, north in bounds
        )
        cql_filter = (
            f"({spatial}) AND time DURING {_format_time(start)}/{_format_time(current)}"
        )
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": LAYERS[satellite],
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "CQL_FILTER": cql_filter,
            "count": str(MAX_FEATURES + 1),
        }
        payload = await self._async_get(params)
        return parse_sentinel3_geojson(
            payload,
            satellite=satellite,
            window_start=start,
            window_end=current,
        )

    async def _async_get(self, params: dict[str, str]) -> bytes:
        try:
            async with self._session.get(
                WFS_URL,
                params=params,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                allow_redirects=False,
                timeout=TIMEOUT,
            ) as response:
                retry_after = parse_retry_after(
                    getattr(response, "headers", {}).get("Retry-After")
                )
                if response.status == 429:
                    raise Sentinel3RateLimitError(
                        "EUMETView rate limited the request", retry_after
                    )
                if 500 <= response.status <= 599:
                    raise Sentinel3TemporaryServiceError(
                        f"EUMETView is temporarily unavailable ({response.status})",
                        retry_after,
                    )
                if response.status != 200:
                    raise Sentinel3InvalidResponseError(
                        f"EUMETView returned an error ({response.status})"
                    )
                content_type = (
                    getattr(response, "headers", {})
                    .get("Content-Type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if content_type not in {"application/json", "application/geo+json"}:
                    raise Sentinel3InvalidResponseError(
                        "EUMETView response is not GeoJSON"
                    )
                if (
                    response.content_length is not None
                    and response.content_length > MAX_RESPONSE_BYTES
                ):
                    raise Sentinel3InvalidResponseError(
                        "EUMETView response exceeds the safety limit"
                    )
                data = bytearray()
                async for chunk in response.content.iter_chunked(16 * 1024):
                    data.extend(chunk)
                    if len(data) > MAX_RESPONSE_BYTES:
                        raise Sentinel3InvalidResponseError(
                            "EUMETView response exceeds the safety limit"
                        )
                return bytes(data)
        except Sentinel3Error:
            raise
        except TimeoutError as err:
            raise Sentinel3TimeoutError("EUMETView request timed out") from err
        except ClientError as err:
            raise Sentinel3Error("EUMETView is unavailable") from err


def parse_sentinel3_geojson(
    payload: bytes,
    *,
    satellite: str,
    window_start: datetime,
    window_end: datetime,
) -> Sentinel3Response:
    """Parse one bounded EUMETView GeoJSON feature collection."""
    if satellite not in LAYERS:
        raise Sentinel3Error("Unsupported Sentinel-3 satellite")
    if len(payload) > MAX_RESPONSE_BYTES:
        raise Sentinel3InvalidResponseError(
            "EUMETView response exceeds the safety limit"
        )
    start = _as_utc(window_start)
    end = _as_utc(window_end)
    if start >= end or end - start > QUERY_WINDOW:
        raise Sentinel3Error("Sentinel-3 query window is invalid")
    try:
        document = json.loads(payload)
        if (
            not isinstance(document, dict)
            or document.get("type") != "FeatureCollection"
        ):
            raise ValueError
        service_timestamp = _parse_timestamp(document["timeStamp"])
        features = document["features"]
        if not isinstance(features, list) or len(features) > MAX_FEATURES:
            raise ValueError
        number_matched = _integer(document.get("numberMatched", len(features)))
        number_returned = _integer(document.get("numberReturned", len(features)))
        if (
            number_matched > MAX_FEATURES
            or number_returned != len(features)
            or number_matched < number_returned
        ):
            raise ValueError
        detections = tuple(
            _parse_feature(
                feature,
                satellite=satellite,
                window_start=start,
                window_end=end,
            )
            for feature in features
        )
    except Sentinel3Error:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as err:
        raise Sentinel3InvalidResponseError(
            "EUMETView GeoJSON has an unexpected shape"
        ) from err
    return Sentinel3Response(service_timestamp, detections)


def _parse_feature(
    feature: Any,
    *,
    satellite: str,
    window_start: datetime,
    window_end: datetime,
) -> Sentinel3Detection:
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise ValueError
    feature_id = _token(feature["id"], 256)
    if not feature_id.startswith(_FEATURE_ID_PREFIXES[satellite]):
        raise ValueError
    geometry = feature["geometry"]
    properties = feature["properties"]
    if (
        not isinstance(geometry, dict)
        or geometry.get("type") != "Point"
        or not isinstance(properties, dict)
    ):
        raise ValueError
    coordinates = geometry["coordinates"]
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        raise ValueError
    longitude = _number(properties["Lon"])
    latitude = _number(properties["Lat"])
    _validate_coordinate(latitude, longitude)
    if (
        abs(_number(coordinates[0]) - longitude) > 0.0001
        or abs(_number(coordinates[1]) - latitude) > 0.0001
    ):
        raise ValueError
    if _token(properties["Satellite"], 8) != satellite:
        raise ValueError
    acquired = _parse_timestamp(properties["Datetime"])
    product_time = _parse_timestamp(properties["time"])
    tolerance = timedelta(minutes=5)
    if not window_start - tolerance <= product_time <= window_end + tolerance:
        raise ValueError
    if abs(acquired - product_time) > timedelta(hours=2):
        raise ValueError
    frp_mw = _number(properties["FRP"])
    uncertainty = _number(properties["FRPerr"])
    confidence_percent = _number(properties["Confidence"])
    across = _number(properties["AcrossSize"])
    along = _number(properties["AlongSize"])
    if (
        not 0 <= frp_mw <= 1_000_000
        or not 0 <= uncertainty <= 1_000_000
        or not 0 <= confidence_percent <= 100
        or not 0 < across <= 100
        or not 0 < along <= 100
    ):
        raise ValueError
    used_channel = _token(properties["UsedChannel"], 8)
    if used_channel not in _ALLOWED_CHANNELS:
        raise ValueError
    return Sentinel3Detection(
        feature_id,
        satellite,
        acquired,
        product_time,
        latitude,
        longitude,
        frp_mw,
        uncertainty,
        confidence_percent / 100.0,
        used_channel,
        across,
        along,
    )


def _validate_bounds(
    bounds: tuple[tuple[float, float, float, float], ...],
) -> None:
    if not bounds or len(bounds) > MAX_AREAS:
        raise Sentinel3Error("Sentinel-3 monitoring-area count is out of range")
    for west, south, east, north in bounds:
        try:
            _validate_coordinate(south, west)
            _validate_coordinate(north, east)
        except ValueError as err:
            raise Sentinel3Error("Sentinel-3 bounding box is invalid") from err
        if (
            west >= east
            or south >= north
            or east - west > MAX_BBOX_SPAN_DEGREES
            or north - south > MAX_BBOX_SPAN_DEGREES
        ):
            raise Sentinel3Error("Sentinel-3 bounding box is invalid")


def _validate_coordinate(latitude: float, longitude: float) -> None:
    if not all(math.isfinite(value) for value in (latitude, longitude)):
        raise ValueError
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise TypeError
    number = float(value)
    if not math.isfinite(number):
        raise ValueError
    return number


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError
    number = int(value)
    if number < 0 or number != value:
        raise ValueError
    return number


def _token(value: Any, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError
    token = value.strip()
    if not token or len(token) > maximum or not token.isprintable():
        raise ValueError
    return token


def _parse_timestamp(value: Any) -> datetime:
    token = _token(value, 64)
    parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    if parsed.utcoffset() is None:
        raise ValueError
    return parsed.astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise Sentinel3Error("Sentinel-3 timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _format(value: float) -> str:
    return f"{value:.5f}".rstrip("0").rstrip(".")


def _format_time(value: datetime) -> str:
    return _as_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")
