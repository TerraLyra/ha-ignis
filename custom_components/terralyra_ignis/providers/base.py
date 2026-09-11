"""Interface implemented by active-fire data providers."""
from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from ..models import ProviderSnapshot

DIAGNOSTIC_CODES = frozenset({
    "goes_catalogue_failed", "goes_download_failed", "goes_decode_failed",
    "goes_dependency_unavailable", "goes_temporary_file_failed",
    "goes_identity_mismatch", "goes_decoder_result_invalid",
    "provider_unexpected_import_error", "provider_unexpected_runtime_error",
    "provider_unexpected_type_error", "provider_unexpected_value_error",
    "provider_unexpected_os_error", "provider_unexpected_error",
})


def safe_diagnostic_code(value: object) -> str | None:
    """Never expose exception text, native paths or arbitrary provider values."""
    return value if isinstance(value, str) and value in DIAGNOSTIC_CODES else None


def unexpected_diagnostic_code(error: Exception) -> str:
    """Classify an unnormalized exception without exporting names or messages."""
    for error_type, code in (
        (ImportError, "provider_unexpected_import_error"),
        (RuntimeError, "provider_unexpected_runtime_error"),
        (TypeError, "provider_unexpected_type_error"),
        (ValueError, "provider_unexpected_value_error"),
        (OSError, "provider_unexpected_os_error"),
    ):
        if isinstance(error, error_type):
            return code
    return "provider_unexpected_error"


class ActiveFireProviderError(Exception):
    """Base error raised by a normalized active-fire provider."""

    failure_type = "unknown"

    def __init__(
        self, message: str = "", *, retry_after: timedelta | None = None,
        diagnostic_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.diagnostic_code = safe_diagnostic_code(diagnostic_code)


class ProviderAuthenticationError(ActiveFireProviderError):
    """Provider credentials are invalid or expired."""

    failure_type = "authentication"


class ProviderNoDataError(ActiveFireProviderError):
    """No recent provider product is currently available."""

    failure_type = "no_product"


class ProviderUnavailableError(ActiveFireProviderError):
    """The provider could not return a safe, valid product."""

    failure_type = "service_outage"


class ProviderRateLimitError(ProviderUnavailableError):
    """The provider temporarily rejected requests due to rate limiting."""

    failure_type = "rate_limit"


class ProviderTimeoutError(ProviderUnavailableError):
    """The provider request exceeded its bounded timeout."""

    failure_type = "timeout"


class ProviderInvalidResponseError(ProviderUnavailableError):
    """The provider returned data that failed safe validation."""

    failure_type = "invalid_response"


class ActiveFireProvider(Protocol):
    """Return provider data in the common active-fire model."""

    async def async_fetch_latest(self) -> ProviderSnapshot:
        """Fetch and normalize the latest provider product."""
        ...
