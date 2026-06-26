"""
tests/test_parser.py
Tests del parser usando datos mock (no requieren credenciales Schwab).
Ejecutar con: pytest tests/
"""

from datetime import date
import pandas as pd
import pytest

from src.parser import parse_option_chain


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


@pytest.fixture
def mock_raw():
    """Respuesta mock de la API. Fixture para aislar cada test."""
    return {
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


# -- Tests ----------------------------------------------------------

def test_parse_returns_two_dataframes(mock_raw):
    calls, puts = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert isinstance(calls, pd.DataFrame)
    assert isinstance(puts, pd.DataFrame)


def test_calls_count(mock_raw):
    calls, _ = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert len(calls) == 3


def test_puts_count(mock_raw):
    _, puts = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert len(puts) == 2


def test_calls_sorted_by_strike(mock_raw):
    calls, _ = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert list(calls["strike"]) == [575.0, 580.0, 585.0]


def test_spread_column_present(mock_raw):
    calls, puts = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert "spread" in calls.columns
    assert "spread" in puts.columns


def test_spread_calculation(mock_raw):
    calls, _ = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    # strike 575: bid=12.0 ask=12.2 -> spread=0.2
    row = calls[calls["strike"] == 575.0].iloc[0]
    assert abs(row["spread"] - 0.2) < 0.001


def test_spread_position_after_ask(mock_raw):
    """spread debe aparecer inmediatamente despues de ask en el DataFrame."""
    calls, _ = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    cols = list(calls.columns)
    assert cols.index("spread") == cols.index("ask") + 1


def test_empty_response():
    calls, puts = parse_option_chain({}, MOCK_EXPIRATION)
    assert calls.empty
    assert puts.empty


def test_wrong_expiration_returns_empty(mock_raw):
    wrong_date = date(2030, 1, 1)
    calls, puts = parse_option_chain(mock_raw, wrong_date)
    assert calls.empty
    assert puts.empty


def test_calls_have_breakeven_column(mock_raw):
    calls, _ = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert "breakeven" in calls.columns


def test_puts_have_breakeven_column(mock_raw):
    _, puts = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert "breakeven" in puts.columns


def test_call_breakeven_value(mock_raw):
    # strike=575, bid=12.0, ask=12.2, midpoint=12.1 => breakeven=587.1
    calls, _ = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    row = calls[calls["strike"] == 575.0].iloc[0]
    assert abs(row["breakeven"] - 587.1) < 0.01


def test_put_breakeven_value(mock_raw):
    # strike=575, bid=7.5, ask=7.7, midpoint=7.6 => breakeven=567.4
    _, puts = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    row = puts[puts["strike"] == 575.0].iloc[0]
    assert abs(row["breakeven"] - 567.4) < 0.01


def test_breakeven_empty_dataframe():
    calls, puts = parse_option_chain({}, MOCK_EXPIRATION)
    # No debe lanzar excepcion con DataFrames vacios
    assert calls.empty
    assert puts.empty


from src.parser import extract_underlying_price


def test_extract_underlying_price_present():
    raw = {"underlyingPrice": 581.25, "callExpDateMap": {}}
    assert extract_underlying_price(raw) == 581.25


def test_extract_underlying_price_missing_defaults_zero():
    assert extract_underlying_price({}) == 0.0
