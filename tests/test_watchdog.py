from datetime import UTC, datetime, timedelta

from watchdog import evaluate

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def health(**overrides):
    base = {
        "last_poll_at": (NOW - timedelta(minutes=20)).isoformat(),
        "last_poll_status": "success",
        "quarantined_rows": 0,
    }
    return base | overrides


def test_healthy_pipeline_passes():
    v = evaluate(health(), NOW)
    assert v.ok and v.reasons == [] and v.minutes_since_poll == 20.0


def test_stale_pipeline_breaches_sla():
    v = evaluate(health(last_poll_at=(NOW - timedelta(minutes=200)).isoformat()), NOW)
    assert not v.ok and "SLA" in v.reasons[0]


def test_failed_last_run_is_reported_even_if_recent():
    v = evaluate(health(last_poll_status="failed"), NOW)
    assert not v.ok and any("failed" in r for r in v.reasons)


def test_quarantine_is_reported():
    v = evaluate(health(quarantined_rows=3), NOW)
    assert not v.ok and any("karantän" in r for r in v.reasons)


def test_missing_health_row_fails():
    assert not evaluate(None, NOW).ok
    assert not evaluate({}, NOW).ok


def test_naive_and_z_timestamps_are_treated_as_utc():
    assert evaluate(health(last_poll_at="2026-10-15T11:50:00Z"), NOW).minutes_since_poll == 10.0
    assert evaluate(health(last_poll_at=datetime(2026, 10, 15, 11, 50)), NOW).minutes_since_poll == 10.0


def test_custom_sla():
    assert not evaluate(health(), NOW, sla_minutes=10).ok
