"""
tests/test_parser.py
Tests del parser usando datos mock (no requieren credenciales Schwab).
Ejecutar con: pytest tests/
"""

from datetime import date
import pandas as pd
import pytest

from src.parser import parse_option_chain


# ── Fixture: respuesta mock de la API ─────────────────────
MOCK_EXPIRATION = date(2025, 6, 20)
DATE_KEY = f"{MOCK_EXPIRATION.strftime('%Y-%m-%d')}:30"


def _make_contract(strike: float, bid: float, ask: float, is_itm: bool) -> dict:
    return {
        "bid": bid,
        "ask": ask,
        "last": (bid + ask) / 2,
        "volume": 1000,
        "openInterest": 5000,
        "delta": 0.5,
        "gamma": 0.02,
        "theta": -0.05,
        "vega": 0.1,
        "impliedVolatility": 0.2,
        "inTheMoney": is_itm,
        "expirationDate": MOCK_EXPIRATION.strftime("%Y-%m-%d"),
    }


MOCK_RAW = {
    "callExpDateMap": {
        DATE_KEY: {
            "580.0": [_make_contract(580.0, 10.1, 10.3, False)],
            "575.0": [_make_contract(575.0, 12.0, 12.2, True)],
            "585.0": [_make_contract(585.0,  8.5,  8.7, False)],
        }
    },
    "putExpDateMap": {
        DATE_KEY: {
            "580.0": [_make_contract(580.0,  9.8, 10.0, True)],
            "575.0": [_make_contract(575.0,  7.5,  7.7, False)],
        }
    },
}


# ── Tests ──────────────────────────────────────────────────

def test_parse_returns_two_dataframes():
    calls, puts = parse_option_chain(MOCK_RAW, MOCK_EXPIRATION)
    assert isinstance(calls, pd.DataFrame)
    assert isinstance(puts, pd.DataFrame)


def test_calls_count():
    calls, _ = parse_option_chain(MOCK_RAW, MOCK_EXPIRATION)
    assert len(calls) == 3


def test_puts_count():
    _, puts = parse_option_chain(MOCK_RAW, MOCK_EXPIRATION)
    assert len(puts) == 2


def test_calls_sorted_by_strike():
    calls, _ = parse_option_chain(MOCK_RAW, MOCK_EXPIRATION)
    assert list(calls["strike"]) == sorted(calls["strike"])


def test_spread_column_present():
    calls, puts = parse_option_chain(MOCK_RAW, MOCK_EXPIRATION)
    assert "spread" in calls.columns
    assert "spread" in puts.columns


def test_spread_calculation():
    calls, _ = parse_option_chain(MOCK_RAW, MOCK_EXPIRATION)
    # strike 575: bid=12.0 ask=12.2 → spread=0.2
    row = calls[calls["strike"] == 575.0].iloc[0]
    assert abs(row["spread"] - 0.2) < 0.001


def test_empty_response():
    calls, puts = parse_option_chain({}, MOCK_EXPIRATION)
    assert calls.empty
    assert puts.empty


def test_wrong_expiration_returns_empty():
    wrong_date = date(2030, 1, 1)
    calls, puts = parse_option_chain(MOCK_RAW, wrong_date)
    assert calls.empty
    assert puts.empty
