"""Tests para src/normalizer.py. Sin red ni credenciales."""

import math
import numpy as np
import pandas as pd
import pytest

from src.normalizer import normalize_chain


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestCanonicalize:
    def test_volatility_alias_becomes_iv(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "volatility": 20.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert "iv" in out.columns
        assert "volatility" not in out.columns

    def test_implied_volatility_alias_becomes_iv(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "impliedVolatility": 20.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert "iv" in out.columns

    def test_total_volume_alias_becomes_volume(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "totalVolume": 500}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert "volume" in out.columns
        assert out.iloc[0]["volume"] == 500


class TestSentinels:
    def test_minus_999_greek_becomes_nan(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "delta": -999.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert math.isnan(out.iloc[0]["delta"])

    def test_inf_iv_becomes_nan(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "iv": np.inf}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert math.isnan(out.iloc[0]["iv"])


class TestDerived:
    def test_no_quote_flag(self):
        calls = _df([{"strike": 100.0, "bid": 0.0, "ask": 0.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert bool(out.iloc[0]["no_quote"]) is True

    def test_quoted_is_not_no_quote(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert bool(out.iloc[0]["no_quote"]) is False

    def test_mid_computed(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert abs(out.iloc[0]["mid"] - 1.1) < 1e-9

    def test_mid_nan_when_no_quote(self):
        calls = _df([{"strike": 100.0, "bid": 0.0, "ask": 0.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert math.isnan(out.iloc[0]["mid"])

    def test_spread_pct_computed(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        # spread=0.2, mid=1.1 -> 0.1818...
        assert abs(out.iloc[0]["spread_pct"] - (0.2 / 1.1)) < 1e-6

    def test_moneyness_computed(self):
        calls = _df([{"strike": 110.0, "bid": 1.0, "ask": 1.2}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert abs(out.iloc[0]["moneyness"] - 1.1) < 1e-9


class TestIVScale:
    def test_percent_scale_divides_by_100(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "iv": 25.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0, iv_scale="percent")
        assert abs(out.iloc[0]["iv"] - 0.25) < 1e-9

    def test_decimal_scale_passthrough(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "iv": 0.25}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0, iv_scale="decimal")
        assert abs(out.iloc[0]["iv"] - 0.25) < 1e-9


def test_empty_dataframe_is_safe():
    out, _ = normalize_chain(pd.DataFrame(), pd.DataFrame(), underlying_price=100.0)
    assert out.empty
