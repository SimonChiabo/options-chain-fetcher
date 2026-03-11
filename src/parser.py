"""
src/parser.py
Transforma la respuesta cruda de la Schwab API en DataFrames
estructurados y listos para exportar a Excel.

La API devuelve el siguiente esquema:
  {
    "callExpDateMap": {
      "2025-06-20:30": {           ← "fecha:días al vencimiento"
        "580.0": [ { ...datos... } ],  ← strike: [lista con 1 elemento]
        "585.0": [ { ...datos... } ],
        ...
      }
    },
    "putExpDateMap": { ... }       ← misma estructura para puts
  }
"""

from datetime import date
import pandas as pd

import config


def _extract_legs(exp_date_map: dict, expiration: date) -> list[dict]:
    """
    Extrae todos los strikes de un expDateMap para una fecha específica.
    Busca la key que empiece con la fecha en formato YYYY-MM-DD.
    """
    target = expiration.strftime("%Y-%m-%d")
    rows = []

    for date_key, strikes in exp_date_map.items():
        if not date_key.startswith(target):
            continue
        for strike_price, contracts in strikes.items():
            for contract in contracts:
                contract["strike"] = float(strike_price)
                rows.append(contract)

    return rows


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

    return calls_df, puts_df


def _to_dataframe(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    """Convierte lista de dicts a DataFrame con columnas seleccionadas."""
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)

    # Mantener solo las columnas que existen
    available = [c for c in columns if c in df.columns]
    df = df[available].copy()

    # Tipos
    numeric_cols = [
        "strike", "bid", "ask", "last", "volume", "openInterest",
        "delta", "gamma", "theta", "vega", "impliedVolatility",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Ordenar por strike ascendente
    if "strike" in df.columns:
        df = df.sort_values("strike").reset_index(drop=True)

    # Columna spread para comodidad del analista
    if "bid" in df.columns and "ask" in df.columns:
        df.insert(3, "spread", (df["ask"] - df["bid"]).round(4))

    return df
