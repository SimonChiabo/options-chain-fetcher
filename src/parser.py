"""
src/parser.py
Transforma la respuesta cruda de la Schwab API en DataFrames
estructurados y listos para exportar a Excel.
"""

from datetime import date
import pandas as pd

import config


def extract_underlying_price(raw: dict) -> float:
    """Precio del subyacente desde la respuesta cruda. 0.0 si falta."""
    try:
        return float(raw.get("underlyingPrice", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _extract_legs(exp_date_map: dict, expiration: date) -> list[dict]:
    target = expiration.strftime("%Y-%m-%d")
    rows = []
    for date_key, strikes in exp_date_map.items():
        if not date_key.startswith(target):
            continue
        for strike_price, contracts in strikes.items():
            for contract in contracts:
                row = {**contract, "strike": float(strike_price)}
                rows.append(row)
    return rows


def _add_breakeven(df: pd.DataFrame, option_type: str) -> None:
    """Agrega columna breakeven al DataFrame in-place. No lanza si faltan columnas."""
    if df.empty or "bid" not in df.columns or "ask" not in df.columns or "strike" not in df.columns:
        return
    midpoint = ((df["bid"] + df["ask"]) / 2).round(4)
    if option_type == "CALL":
        df["breakeven"] = (df["strike"] + midpoint).round(4)
    else:
        df["breakeven"] = (df["strike"] - midpoint).round(4)


def parse_option_chain(raw: dict, expiration: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Parsea la respuesta cruda de la API.

    Args:
        raw:        Dict devuelto por fetcher.fetch_option_chain()
        expiration: Fecha de vencimiento usada en la consulta

    Returns:
        Tupla (calls_df, puts_df) con columnas estandarizadas.
    """
    calls_raw = _extract_legs(raw.get("callExpDateMap", {}), expiration)
    puts_raw  = _extract_legs(raw.get("putExpDateMap",  {}), expiration)

    calls_df = _to_dataframe(calls_raw, config.CALLS_COLUMNS)
    puts_df  = _to_dataframe(puts_raw,  config.PUTS_COLUMNS)

    _add_breakeven(calls_df, option_type="CALL")
    _add_breakeven(puts_df,  option_type="PUT")

    return calls_df, puts_df


def _to_dataframe(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    """Convierte lista de dicts a DataFrame con columnas seleccionadas."""
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)

    available = [c for c in columns if c in df.columns]
    df = df[available].copy()

    for col in config.NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "strike" in df.columns:
        df = df.sort_values("strike").reset_index(drop=True)

    if "bid" in df.columns and "ask" in df.columns and "spread" not in df.columns:
        ask_pos = df.columns.get_loc("ask")
        df.insert(ask_pos + 1, "spread", (df["ask"] - df["bid"]).round(4))

    return df
