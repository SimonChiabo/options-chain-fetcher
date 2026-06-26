"""
src/analyzer.py
Calculos de dominio financiero sobre option chains.
"""

from datetime import date
from typing import Any
import math
import pandas as pd


def calculate_max_pain(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Calcula el Max Pain strike: S que minimiza el valor total de opciones para compradores.

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


def calculate_iv_skew(
    expirations_data: dict[date, tuple[pd.DataFrame, pd.DataFrame]],
) -> pd.DataFrame:
    """
    Tabla de volatility skew por strike y vencimiento, usando IV de calls.

    Returns:
        DataFrame con strikes como filas y fechas de vencimiento como columnas.
    """
    if not expirations_data:
        return pd.DataFrame()

    all_strikes: set[float] = set()
    for calls_df, puts_df in expirations_data.values():
        if "strike" in calls_df.columns:
            all_strikes |= set(calls_df["strike"].tolist())
        if "strike" in puts_df.columns:
            all_strikes |= set(puts_df["strike"].tolist())

    sorted_strikes = sorted(all_strikes)
    table: dict[str, list] = {"strike": sorted_strikes}

    for exp in sorted(expirations_data):
        calls_df, _ = expirations_data[exp]
        col = exp.strftime("%Y-%m-%d")
        if "impliedVolatility" in calls_df.columns and "strike" in calls_df.columns:
            iv_map = dict(zip(calls_df["strike"], calls_df["impliedVolatility"]))
        else:
            iv_map = {}
        table[col] = [iv_map.get(s) for s in sorted_strikes]

    return pd.DataFrame(table)


def build_chain_metrics(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    underlying_price: float,
) -> dict[str, float]:
    """
    Ensambla las metricas chain-level que el motor de reglas puede referenciar.

    Returns:
        dict con pc_volume_ratio, pc_oi_ratio, max_pain_strike, underlying_price,
        distance_to_max_pain, distance_to_max_pain_pct.
    """
    pc = calculate_pc_ratio(calls_df, puts_df)
    max_pain = calculate_max_pain(calls_df, puts_df)
    mp_strike = float(max_pain["strike"])

    distance = abs(underlying_price - mp_strike)
    if underlying_price and underlying_price > 0:
        distance_pct = distance / underlying_price
    else:
        distance_pct = float("inf")

    # Denominador cero (sin volumen/OI) produce inf en calculate_pc_ratio. Para las
    # reglas lo tratamos como sin-senal (NaN) y asi el motor lo ignora en vez de
    # disparar una alerta espuria con valor inf (tipico pre-market / overnight).
    def _no_signal_if_inf(value: float) -> float:
        return value if math.isfinite(value) else float("nan")

    return {
        "pc_volume_ratio": _no_signal_if_inf(pc["volume_ratio"]),
        "pc_oi_ratio": _no_signal_if_inf(pc["oi_ratio"]),
        "max_pain_strike": mp_strike,
        "underlying_price": float(underlying_price),
        "distance_to_max_pain": round(distance, 4),
        "distance_to_max_pain_pct": distance_pct,
    }
