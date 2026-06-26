"""Tests para src/alert_state.py. Deterministas via reloj inyectado."""

from datetime import datetime, timedelta

from src.alert_state import AlertState
from src.rules import Alert


def _alert(name: str, subject: str, ts: datetime) -> Alert:
    return Alert(
        rule_name=name, symbol="SPY", scope="contract", subject=subject,
        field="iv", value=0.4, threshold=0.3, timestamp=ts, message="x",
    )


def test_first_occurrence_notifies():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    out = state.update([_alert("r", "SPY 100C", t0)], now=t0)
    assert len(out) == 1


def test_still_active_within_interval_is_suppressed():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    state.update([_alert("r", "SPY 100C", t0)], now=t0)
    out = state.update([_alert("r", "SPY 100C", t0)], now=t0 + timedelta(seconds=60))
    assert out == []


def test_still_active_after_interval_re_notifies():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    state.update([_alert("r", "SPY 100C", t0)], now=t0)
    out = state.update([_alert("r", "SPY 100C", t0)], now=t0 + timedelta(seconds=301))
    assert len(out) == 1


def test_cleared_then_reactivated_after_interval_is_fresh_edge():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    state.update([_alert("r", "SPY 100C", t0)], now=t0)
    # cleared for a full interval
    state.update([], now=t0 + timedelta(seconds=301))
    out = state.update([_alert("r", "SPY 100C", t0)], now=t0 + timedelta(seconds=400))
    assert len(out) == 1


def test_distinct_subjects_tracked_independently():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    out = state.update(
        [_alert("r", "SPY 100C", t0), _alert("r", "SPY 105C", t0)], now=t0
    )
    assert len(out) == 2
