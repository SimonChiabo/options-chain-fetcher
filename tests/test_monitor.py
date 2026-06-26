"""Tests para monitor.run_cycle. fetch mockeado, sin red."""

from datetime import date, datetime

import pandas as pd
import pytest

import monitor
from src.rules import Rule
from src.alert_state import AlertState


class _RecordNotifier:
    def __init__(self):
        self.sent = []

    def send(self, alert):
        self.sent.append(alert)


def _fake_raw():
    return {
        "underlyingPrice": 100.0,
        "callExpDateMap": {
            "2026-07-17:21": {
                "100.0": [{
                    "bid": 1.0, "ask": 1.2, "last": 1.1, "volume": 100,
                    "openInterest": 500, "delta": 0.5, "gamma": 0.02,
                    "theta": -0.05, "vega": 0.1, "impliedVolatility": 40.0,
                    "inTheMoney": True, "expirationDate": "2026-07-17",
                }],
            }
        },
        "putExpDateMap": {},
    }


def test_run_cycle_fires_alert(monkeypatch):
    monkeypatch.setattr(monitor, "fetch_option_chain", lambda **kw: _fake_raw())
    rule = Rule(name="high_iv", scope="contract", field="iv", operator="gt", value=0.30)
    notifier = _RecordNotifier()
    state = AlertState(min_interval=300)

    out = monitor.run_cycle(
        client=None, symbol="SPY", expiration=date(2026, 7, 17),
        rules=[rule], state=state, notifier=notifier,
        contract_type="ALL", strike_count=None, iv_scale="percent",
        now=datetime(2026, 6, 26, 10, 0),
    )
    assert len(out) == 1
    assert len(notifier.sent) == 1


def test_run_cycle_survives_api_error(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("api down")

    monkeypatch.setattr(monitor, "fetch_option_chain", _boom)
    out = monitor.run_cycle(
        client=None, symbol="SPY", expiration=date(2026, 7, 17),
        rules=[], state=AlertState(), notifier=_RecordNotifier(),
        contract_type="ALL", strike_count=None, iv_scale="percent",
    )
    assert out == []


def test_is_market_hours_weekend_false():
    # 2026-06-27 is a Saturday.
    assert monitor.is_market_hours(datetime(2026, 6, 27, 12, 0)) is False
