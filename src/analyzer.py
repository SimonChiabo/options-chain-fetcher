"""
src/analyzer.py
Calculos de dominio financiero sobre option chains.
"""

from datetime import date
from typing import Any
import pandas as pd


def calculate_max_pain(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Calcula el Max Pain strike.

    Para cada strike candidato S:
      call_value = sum(K < S): (S - K) * call_OI[K]
      put_value  = sum(K > S): (K - S) * put_OI[K]
    Max Pain = S que minimiza (call_value + put_value).

    Returns:
        {"strike": float, "pain_by_strike": dict[float, float]}
    """
    call_oi: dict[float, float] = {}
    put_oi:  dict[float, float] = {}

    if not calls_df.empty and "strike" in calls_df.columns:
        call_oi = dict(zip(calls_df["strike"].astype(float), calls_df["openInterest"]))
    if not puts_df.empty and "strike" in puts_df.columns:
        put_oi  = dict(zip(puts_df["strike"].astype(float),  puts_df["openInterest"]))

    all_strikes = sorted(set(call_oi) | set(put_oi))
    if not all_strikes:
        return {"strike": 0.0, "pain_by_strike": {}}

    pain: dict[float, float] = {}
    for s in all_strikes:
        call_pain = sum((s - k) * oi for k, oi in call_oi.items() if k < s)
        put_pain  = sum((k - s) * oi for k, oi in put_oi.items()  if k > s)
        pain[s] = call_pain + put_pain

    max_pain_strike = min(pain, key=pain.__getitem__)
    return {"strike": max_pain_strike, "pain_by_strike": pain}


def calculate_pc_ratio(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
) -> dict[str, float]:
    """
    Calcula el Put/Call Ratio por volumen y por Open Interest.

    > 1.0 => sentimiento bearish, < 1.0 => sentimiento bullish.

    Returns:
        {"volume_ratio": float, "oi_ratio": float}
    """
    call_vol = float(calls_df["volume"].sum())
    put_vol  = float(puts_df["volume"].sum())
    call_oi  = float(calls_df["openInterest"].sum())
    put_oi   = float(puts_df["openInterest"].sum())

    return {
        "volume_ratio": round(put_vol / call_vol, 4) if call_vol > 0 else float("inf"),
        "oi_ratio":     round(put_oi  / call_oi,  4) if call_oi  > 0 else float("inf"),
    }
