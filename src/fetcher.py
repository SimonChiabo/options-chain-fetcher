"""
src/fetcher.py
Obtiene la cadena de opciones desde la Schwab API.

Documentación del endpoint:
  GET /marketdata/v1/chains
  Parámetros clave: symbol, contractType, toDate, fromDate
"""

from datetime import date
from typing import Optional
import schwab

from src.auth import get_client


def fetch_option_chain(
    symbol: str,
    expiration: date,
    contract_type: str = "ALL",
    strike_count: Optional[int] = None,
) -> dict:
    """
    Descarga la option chain completa para un subyacente y vencimiento.

    Args:
        symbol:        Ticker del subyacente (ej: "SPY", "QQQ", "AAPL")
        expiration:    Fecha de vencimiento como objeto date
        contract_type: "CALL", "PUT" o "ALL" (default)
        strike_count:  Cantidad de strikes a cada lado del ATM.
                       None = todos los strikes disponibles.

    Returns:
        dict con la respuesta cruda de la API (ver parser.py para transformar)

    Raises:
        RuntimeError: Si la API devuelve un error o no hay datos.
    """
    client = get_client()

    kwargs = dict(
        symbol=symbol.upper(),
        contract_type=getattr(
            schwab.client.Client.Options.ContractType, contract_type
        ),
        from_date=expiration,
        to_date=expiration,
    )

    if strike_count is not None:
        kwargs["strike_count"] = strike_count

    response = client.get_option_chain(**kwargs)

    if not response.ok:
        raise RuntimeError(
            f"Error al obtener option chain para {symbol}: "
            f"{response.status_code} - {response.text}"
        )

    data = response.json()

    if data.get("status") == "FAILED":
        raise RuntimeError(f"Schwab API devolvió status FAILED para {symbol}")

    return data
