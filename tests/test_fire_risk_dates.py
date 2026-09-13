"""Date availability must be established, never inferred from 404 alone."""
from datetime import UTC, datetime, timedelta
import pytest
from custom_components.terralyra_ignis.products.fire_risk import (
    FireRiskClient, FireRiskDateUnavailableError, FireRiskHTTPError,
    FireRiskError, _risk_dates, safe_fire_risk_reason,
)

def catalogue(start, end):
    return f'<WMT_MS_Capabilities><Capability><Layer><Name>Risk</Name><Extent name="time">{start}T12:00:00Z/{end}T12:00:00Z/P1D</Extent></Layer></Capability></WMT_MS_Capabilities>'.encode()

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["missing", "advertised", "malformed", "unavailable"])
async def test_today_404_checks_catalogue(mode):
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    class Client(FireRiskClient):
        def __init__(self):
            self.requests = []
        async def _async_get(self, params, limit):
            self.requests.append(params)
            if params["REQUEST"] == "GetCapabilities":
                if mode == "unavailable":
                    raise FireRiskHTTPError("private payload", 503)
                if mode == "malformed":
                    return b"<invalid"
                return catalogue(yesterday, today if mode == "advertised" else yesterday)
            raise FireRiskHTTPError("<xml>private payload</xml>",404)
    client = Client()
    expected = FireRiskDateUnavailableError if mode == "missing" else FireRiskHTTPError
    with pytest.raises(expected) as caught:
        await client.async_forecast(47,19,100)
    assert len(client.requests) == 2
    assert "private" not in safe_fire_risk_reason(caught.value)
    if mode == "missing":
        assert caught.value.requested == today
        assert caught.value.latest == yesterday

@pytest.mark.parametrize("payload", [b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>', b"<x", catalogue("2000-01-01","2026-09-13"), catalogue("2026-09-13","2026-09-11")])
def test_reject_unsafe_or_unbounded_dates(payload):
    with pytest.raises(FireRiskError):
        _risk_dates(payload)

def test_dates_are_risk_layer_specific():
    assert not _risk_dates(catalogue("2026-09-11","2026-09-13").replace(b">Risk<",b">Other<"))
    assert len(_risk_dates(catalogue("2026-09-11","2026-09-13"))) == 3

def test_standard_adaguc_doctype_does_not_fetch_external_dtd():
    header = b'''<?xml version='1.0' encoding="ISO-8859-1" standalone="no" ?>
<!DOCTYPE WMT_MS_Capabilities SYSTEM "http://schemas.opengis.net/wms/1.1.1/WMS_MS_Capabilities.dtd"
 [ <!ELEMENT VendorSpecificCapabilities EMPTY> ]>'''
    assert len(_risk_dates(header + catalogue("2026-08-31", "2026-09-11"))) == 12

@pytest.mark.asyncio
async def test_date_failure_reaches_coordinator_without_map_request(hass, monkeypatch):
    from unittest.mock import Mock
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from custom_components.terralyra_ignis.fire_risk_coordinator import FireRiskCoordinator
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    class Client(FireRiskClient):
        def __init__(self):
            pass
        async def async_forecast(self, *args):
            raise FireRiskDateUnavailableError(today, yesterday)
        async def async_map(self, *args):
            raise AssertionError("No old map may be substituted")
    issue = Mock()
    monkeypatch.setattr("custom_components.terralyra_ignis.fire_risk_coordinator.async_set_fire_risk_outage_issue", issue)
    coordinator = FireRiskCoordinator(hass, Mock(entry_id="test", options={}), Client())
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert issue.call_args.kwargs["requested_date"] == today.isoformat()
    assert issue.call_args.kwargs["latest_date"] == yesterday.isoformat()

@pytest.mark.parametrize("failures", [3, 40, 1000, 10**100])
def test_forecast_retry_saturates(failures):
    from custom_components.terralyra_ignis.fire_risk_coordinator import _retry_interval
    assert _retry_interval(failures) == timedelta(hours=1)
