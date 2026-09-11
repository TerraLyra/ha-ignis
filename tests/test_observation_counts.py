"""Replay observations independently of provider publication cadence."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json

from custom_components.terralyra_ignis.models import FireDetection
from custom_components.terralyra_ignis.observation_counts import update_counts, summarize_counts
from custom_components.terralyra_ignis.activity import update_activity_history, summarize_activity

NOW = datetime(2026, 9, 11, 12, tzinfo=UTC)


def detection(**changes):
    return replace(FireDetection(
        provider="test", satellite="S3A", product="FRP", timestamp=NOW,
        latitude=38.6, longitude=-121.3, frp_mw=20, confidence=0.9,
        source_detection_id="pixel",
    ), **changes)


def test_repeated_observation_restart_and_expiry():
    state = {}
    for minute in (0, 10, 20, 30, 40, 50):
        now = NOW + timedelta(minutes=minute)
        state = update_counts(state, [detection()], now=now)
        state = json.loads(json.dumps(state))
        assert summarize_counts(state, now=now)["counts"][1] == 1
    assert summarize_counts(state, now=NOW+timedelta(hours=1))["counts"][1] == 0


def test_old_and_future_acquisitions_not_counted_as_current():
    state = update_counts({}, [detection(timestamp=NOW-timedelta(hours=12)),
                               detection(timestamp=NOW+timedelta(minutes=1))], now=NOW)
    assert summarize_counts(state, now=NOW)["counts"] == {1: 0, 3: 0, 6: 0}


def test_late_backfill_uses_acquisition_window_and_preserves_independent_samples():
    state = update_counts({}, [detection(timestamp=NOW-timedelta(hours=2)),
                               detection(), detection(satellite="S3B"),
                               detection(timestamp=NOW-timedelta(minutes=10))], now=NOW)
    assert summarize_counts(state, now=NOW)["counts"] == {1: 3, 3: 4, 6: 4}
    assert len(state["records"]) == 4


def test_fallback_identity_ignores_frp_revisions_but_preserves_pixels():
    first = detection(source_detection_id=None)
    state = update_counts({}, [first, replace(first, frp_mw=25),
                               replace(first, latitude=38.7)], now=NOW)
    assert len(state["records"]) == 2


def test_legacy_counts_are_not_converted_and_collection_is_explicit():
    state = update_counts({"detections": 9999}, [detection()], now=NOW)
    summary = summarize_counts(state, now=NOW)
    assert summary["counts"][1] == 1
    assert not any(summary["window_collection_complete"].values())
    later = summarize_counts(state, now=NOW+timedelta(hours=6))
    assert all(later["window_collection_complete"].values())


def test_capacity_limit_remains_visible_after_restart(monkeypatch):
    monkeypatch.setattr("custom_components.terralyra_ignis.observation_counts.MAX_RECORDS", 2)
    state = update_counts({}, [detection(source_detection_id=str(i)) for i in range(3)], now=NOW)
    assert len(state["records"]) == 2
    restored = update_counts(json.loads(json.dumps(state)), [], now=NOW+timedelta(minutes=1))
    assert summarize_counts(restored, now=NOW)["retention_limited"]


def test_clock_does_not_regress():
    state = update_counts({}, [detection()], now=NOW)
    state = update_counts(state, [], now=NOW-timedelta(hours=1))
    assert state["updated_at"] == NOW.isoformat()


def test_activity_summary_excludes_future_records():
    history = update_activity_history([], timestamp=NOW+timedelta(hours=2),
                                      detections=500, total_frp_mw=40, new_incidents=5)
    summary = summarize_activity(history, now=NOW)
    assert summary.detections_1h == 0
    assert summary.new_incidents_24h == 0
    assert summary.frp_change_1h is None
