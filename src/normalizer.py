"""
src/normalizer.py
Capa de normalizacion: limpia la salida del parser y deriva metricas
por-contrato listas para el motor de reglas. Funcion pura, sin red.
"""

import numpy as np
import pandas as pd

import config

# Unico lugar a corregir cuando llegue la primera respuesta real de Schwab.
_FIELD_ALIASES = {
    "impliedVolatility": "iv",
    "volatility": "iv",
    "totalVolume": "volume",
}

_SENTINEL = -999.0
_SENTINEL_COLUMNS = ["delta", "gamma", "theta", "vega", "iv"]


def _canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    rename = {src: dst for src, dst in _FIELD_ALIASES.items()
              if src in df.columns and dst not in df.columns}
    return df.rename(columns=rename)


def _strip_sentinels(df: pd.DataFrame) -> None:
    for col in _SENTINEL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].replace(_SENTINEL, np.nan)
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)


def _normalize_one(df: pd.DataFrame, underlying_price: float, iv_scale: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    df = _canonicalize(df).copy()
    _strip_sentinels(df)

    bid = df["bid"] if "bid" in df.columns else pd.Series(np.nan, index=df.index)
    ask = df["ask"] if "ask" in df.columns else pd.Series(np.nan, index=df.index)

    df["no_quote"] = ~((bid > 0) | (ask > 0))

    mid = (bid + ask) / 2
    mid = mid.where(~df["no_quote"], np.nan)
    df["mid"] = mid.round(4)

    if "spread" not in df.columns:
        df["spread"] = (ask - bid).round(4)
    df["spread_pct"] = (df["spread"] / mid).round(6)

    if underlying_price and underlying_price > 0 and "strike" in df.columns:
        df["moneyness"] = (df["strike"] / underlying_price).round(6)
    else:
        df["moneyness"] = np.nan

    if "iv" in df.columns and iv_scale == "percent":
        df["iv"] = df["iv"] / 100.0

    return df


def normalize_chain(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    underlying_price: float,
    iv_scale: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Normaliza ambos lados de la cadena.

    Args:
        calls_df, puts_df: DataFrames del parser.
        underlying_price:  Precio del subyacente (para moneyness).
        iv_scale:          "percent" o "decimal". None usa config.IV_INPUT_SCALE.

    Returns:
        (calls_norm, puts_norm) con columnas iv, no_quote, mid, spread_pct, moneyness.
    """
    scale = iv_scale or config.IV_INPUT_SCALE
    calls = _normalize_one(calls_df, underlying_price, scale)
    puts = _normalize_one(puts_df, underlying_price, scale)
    return calls, puts
