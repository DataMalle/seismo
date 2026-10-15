from datetime import UTC, datetime, timedelta

from watchdog import evaluate

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def health(**overrides):
    base = {
        "last_poll_at": (NOW - timedelta(minutes=20)).isoformat(),
        "last_success_at": (NOW - timedelta(minutes=20)).isoformat(),
        "last_poll_status": "success",
        "quarantined_rows": 0,
    }
    return base | overrides


def test_healthy_pipeline_passes():
    v = evaluate(health(), NOW)
    assert v.ok and v.reasons == [] and v.minutes_since_success == 20.0


def test_stale_pipeline_breaches_sla():
    v = evaluate(health(last_success_at=(NOW - timedelta(minutes=200)).isoformat()), NOW)
    assert not v.ok and "SLA" in v.reasons[0]


def test_single_failed_attempt_does_not_alert_while_a_recent_success_exists():
    """Ett kort USGS-avbrott (502) får inte öppna ett issue som stänger sig själv nästa timme."""
    v = evaluate(health(last_poll_status="failed"), NOW)
    assert v.ok and v.last_poll_status == "failed"


def test_repeated_failures_alert_once_the_sla_is_breached_and_mention_the_failure():
    stale = (NOW - timedelta(minutes=170)).isoformat()
    v = evaluate(health(last_success_at=stale, last_poll_status="failed"), NOW)
    assert not v.ok and any("failed" in r for r in v.reasons)


def test_quarantine_is_reported():
    v = evaluate(health(quarantined_rows=3), NOW)
    assert not v.ok and any("karantän" in r for r in v.reasons)


def test_missing_health_row_fails():
    assert not evaluate(None, NOW).ok
    assert not evaluate({}, NOW).ok


def test_falls_back_to_last_poll_at_for_older_health_tables():
    v = evaluate({"last_poll_at": (NOW - timedelta(minutes=10)).isoformat(), "last_poll_status": "success"}, NOW)
    assert v.ok and v.minutes_since_success == 10.0


def test_naive_and_z_timestamps_are_treated_as_utc():
    assert evaluate(health(last_success_at="2026-10-15T11:50:00Z"), NOW).minutes_since_success == 10.0
    assert evaluate(health(last_success_at=datetime(2026, 10, 15, 11, 50)), NOW).minutes_since_success == 10.0


def test_custom_sla():
    assert not evaluate(health(), NOW, sla_minutes=10).ok
