"""EUMETSAT Sentinel-3 SLSTR active-fire provider adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..models import FireDetection, ProviderSnapshot, ProviderStatus
from ..products.sentinel3 import (
    PUBLIC_SOURCE_URL,
    Sentinel3Client,
    Sentinel3Error,
    Sentinel3InvalidResponseError,
    Sentinel3RateLimitError,
    Sentinel3TemporaryServiceError,
    Sentinel3TimeoutError,
)
from .base import (
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

PROVIDERS = {
    "S3A": "eumetsat_sentinel3a",
    "S3B": "eumetsat_sentinel3b",
}
PRODUCT = "SLSTR Level 2 NRT Fire Radiative Power"
SATELLITES = ("S3A", "S3B")
MIN_REFRESH_INTERVAL = timedelta(minutes=15)
DELAYED_AFTER = timedelta(hours=6)


class Sentinel3ActiveFireProvider:
    """Normalize one public Sentinel-3 WFS layer for monitored areas."""

    def __init__(
        self,
        client: Sentinel3Client,
        *,
        satellite: str,
        bounds: tuple[tuple[float, float, float, float], ...],
    ) -> None:
        if satellite not in SATELLITES:
            raise ValueError("Unsupported Sentinel-3 satellite")
        self._client = client
        self._satellite = satellite
        self._bounds = bounds
        self._cached_snapshot: ProviderSnapshot | None = None
        self._cached_at: datetime | None = None

    async def async_fetch_latest(self) -> ProviderSnapshot:
        """Fetch and normalize recent Sentinel-3 fire observations."""
        now = datetime.now(UTC)
        if (
            self._cached_snapshot is not None
            and self._cached_at is not None
            and now - self._cached_at < MIN_REFRESH_INTERVAL
        ):
            return self._cached_snapshot
        try:
            response = await self._client.async_area(
                satellite=self._satellite,
                bounds=self._bounds,
                now=now,
            )
        except Sentinel3RateLimitError as err:
            raise ProviderRateLimitError(str(err), retry_after=err.retry_after) from err
        except Sentinel3TimeoutError as err:
            raise ProviderTimeoutError(str(err)) from err
        except Sentinel3TemporaryServiceError as err:
            raise ProviderUnavailableError(
                str(err), retry_after=err.retry_after
            ) from err
        except Sentinel3InvalidResponseError as err:
            raise ProviderInvalidResponseError(str(err)) from err
        except Sentinel3Error as err:
            raise ProviderUnavailableError(str(err)) from err

        detections = tuple(
            FireDetection(
                provider=PROVIDERS[self._satellite],
                satellite=item.satellite,
                product=PRODUCT,
                timestamp=item.acquired,
                latitude=item.latitude,
                longitude=item.longitude,
                frp_mw=item.frp_mw,
                frp_uncertainty_mw=item.frp_uncertainty_mw,
                confidence=item.confidence,
                classification=f"MWIR_{item.used_channel}",
                fire_area_km2=item.across_size_km * item.along_size_km,
                source_resolution_km=max(item.across_size_km, item.along_size_km),
                source_detection_id=item.feature_id,
            )
            for item in response.detections
        )
        product_time = max(
            (item.product_time for item in response.detections),
            default=response.service_timestamp,
        )
        snapshot = ProviderSnapshot(
            provider=PROVIDERS[self._satellite],
            satellite=self._satellite,
            product=PRODUCT,
            product_timestamp=product_time,
            received_timestamp=now,
            status=(
                ProviderStatus.DELAYED
                if now - product_time > DELAYED_AFTER
                else ProviderStatus.AVAILABLE
            ),
            source_url=PUBLIC_SOURCE_URL,
            filename=f"eumetview-{self._satellite.lower()}-slstr-frp.geojson",
            detections=detections,
        )
        self._cached_snapshot = snapshot
        self._cached_at = now
        return snapshot
