"""Tests para src/analyzer.py. No requieren credenciales de Schwab."""

import pandas as pd
import pytest
from datetime import date
from src.analyzer import calculate_max_pain, calculate_pc_ratio, calculate_iv_skew


def _make_df(strikes, oi, vol=None):
    return pd.DataFrame({
        "strike": [float(s) for s in strikes],
        "openInterest": oi,
        "volume": vol if vol is not None else [100] * len(strikes),
    })


class TestMaxPain:
    def test_max_pain_strike_is_minimum_buyer_value(self):
        # At S=100: call_pain=0, put_pain=(105-100)*100+(110-100)*50=1000 => total=1000
        # At S=105: call_pain=(105-100)*100=500, put_pain=(110-105)*50=250 => total=750  <- min
        # At S=110: call_pain=(110-100)*100+(110-105)*50=1250, put_pain=0 => total=1250
        calls = _make_df([100, 105, 110], [100, 50, 200])
        puts  = _make_df([100, 105, 110], [300, 100, 50])
        result = calculate_max_pain(calls, puts)
        assert result["strike"] == 105.0

    def test_max_pain_returns_pain_by_strike_dict(self):
        calls = _make_df([100, 105, 110], [100, 50, 200])
        puts  = _make_df([100, 105, 110], [300, 100, 50])
        result = calculate_max_pain(calls, puts)
        assert isinstance(result["pain_by_strike"], dict)
        assert 105.0 in result["pain_by_strike"]
        assert abs(result["pain_by_strike"][105.0] - 750) < 0.01

    def test_max_pain_empty_data(self):
        empty = pd.DataFrame({"strike": [], "openInterest": [], "volume": []})
        result = calculate_max_pain(empty, empty)
        assert result["strike"] == 0.0
        assert result["pain_by_strike"] == {}

    def test_max_pain_single_strike(self):
        calls = _make_df([100], [500])
        puts  = _make_df([100], [500])
        result = calculate_max_pain(calls, puts)
        assert result["strike"] == 100.0


class TestPCRatio:
    def test_volume_ratio(self):
        calls = _make_df([100, 105], [1000, 2000], [100, 200])
        puts  = _make_df([100, 105], [500, 1500],  [150, 150])
        result = calculate_pc_ratio(calls, puts)
        # put_vol=300, call_vol=300 => 1.0
        assert result["volume_ratio"] == 1.0

    def test_oi_ratio(self):
        calls = _make_df([100, 105], [1000, 2000], [100, 200])
        puts  = _make_df([100, 105], [500, 1500],  [150, 150])
        result = calculate_pc_ratio(calls, puts)
        # put_oi=2000, call_oi=3000 => 0.6667
        assert abs(result["oi_ratio"] - round(2000 / 3000, 4)) < 0.0001

    def test_zero_call_volume_returns_inf(self):
        calls = _make_df([100], [100], [0])
        puts  = _make_df([100], [100], [50])
        result = calculate_pc_ratio(calls, puts)
        assert result["volume_ratio"] == float("inf")

    def test_zero_call_oi_returns_inf(self):
        calls = pd.DataFrame({"strike": [100.0], "openInterest": [0], "volume": [100]})
        puts  = _make_df([100], [200], [50])
        result = calculate_pc_ratio(calls, puts)
        assert result["oi_ratio"] == float("inf")


class TestIVSkew:
    def _calls(self, strikes, ivs):
        return pd.DataFrame({"strike": [float(s) for s in strikes], "impliedVolatility": ivs})

    def _puts(self, strikes, ivs):
        return pd.DataFrame({"strike": [float(s) for s in strikes], "impliedVolatility": ivs})

    def test_iv_skew_returns_dataframe(self):
        exp = date(2025, 6, 20)
        data = {exp: (self._calls([100, 105], [0.20, 0.18]), self._puts([100, 105], [0.22, 0.21]))}
        skew = calculate_iv_skew(data)
        assert isinstance(skew, pd.DataFrame)

    def test_iv_skew_has_strike_column(self):
        exp = date(2025, 6, 20)
        data = {exp: (self._calls([100], [0.20]), self._puts([100], [0.22]))}
        skew = calculate_iv_skew(data)
        assert "strike" in skew.columns

    def test_iv_skew_has_expiration_column(self):
        exp = date(2025, 6, 20)
        data = {exp: (self._calls([100], [0.20]), self._puts([100], [0.22]))}
        skew = calculate_iv_skew(data)
        assert "2025-06-20" in skew.columns

    def test_iv_skew_multiple_expirations(self):
        exp1 = date(2025, 6, 20)
        exp2 = date(2025, 7, 18)
        data = {
            exp1: (self._calls([100], [0.20]), self._puts([100], [0.22])),
            exp2: (self._calls([100], [0.25]), self._puts([100], [0.26])),
        }
        skew = calculate_iv_skew(data)
        assert set(skew.columns) == {"strike", "2025-06-20", "2025-07-18"}

    def test_iv_skew_call_iv_values(self):
        exp = date(2025, 6, 20)
        data = {exp: (self._calls([100.0], [0.20]), self._puts([100.0], [0.22]))}
        skew = calculate_iv_skew(data)
        row = skew[skew["strike"] == 100.0].iloc[0]
        assert abs(row["2025-06-20"] - 0.20) < 0.001

    def test_iv_skew_empty_data(self):
        skew = calculate_iv_skew({})
        assert skew.empty
