"""
src/fetcher.py
Obtiene la cadena de opciones desde la Schwab API.

Documentacion del endpoint:
  GET /marketdata/v1/chains
  Parametros clave: symbol, contractType, toDate, fromDate
"""

import logging
from datetime import date
from typing import Any, Optional
import schwab

from src.auth import get_client

log = logging.getLogger(__name__)


def fetch_option_chain(
    symbol: str,
    expiration: date,
    contract_type: str = "ALL",
    strike_count: Optional[int] = None,
    client: Optional[schwab.client.Client] = None,
) -> dict[str, Any]:
    """
    Descarga la option chain completa para un subyacente y vencimiento.

    Args:
        symbol:        Ticker del subyacente (ej: "SPY", "QQQ", "AAPL")
        expiration:    Fecha de vencimiento como objeto date
        contract_type: "CALL", "PUT" o "ALL" (default)
        strike_count:  Cantidad de strikes a cada lado del ATM.
                       None = todos los strikes disponibles.
        client:        Cliente autenticado de Schwab. Si es None, se crea
                       uno nuevo llamando a get_client(). Pasar el cliente
                       explicitamente evita re-autenticar en llamadas multiples.

    Returns:
        dict con la respuesta cruda de la API (ver parser.py para transformar)

    Raises:
        ValueError:   Si contract_type no es "ALL", "CALL" o "PUT".
        RuntimeError: Si la API devuelve un error, status FAILED, o no hay
                      contratos para el simbolo/vencimiento solicitado.
    """
    if client is None:
        client = get_client()

    valid_types = {"ALL", "CALL", "PUT"}
    if contract_type not in valid_types:
        raise ValueError(
            f"contract_type invalido: '{contract_type}'. "
            f"Valores validos: {valid_types}"
        )

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
        log.debug("Schwab API error response: %s", response.text)
        raise RuntimeError(
            f"Error al obtener option chain para {symbol}: HTTP {response.status_code}"
        )

    data = response.json()

    if data.get("status") == "FAILED":
        raise RuntimeError(f"Schwab API devolvio status FAILED para {symbol}")

    call_map = data.get("callExpDateMap", {})
    put_map  = data.get("putExpDateMap",  {})
    if not call_map and not put_map:
        raise RuntimeError(
            f"No se encontraron opciones para '{symbol}' con vencimiento {expiration}. "
            "Verifica que el simbolo y la fecha sean validos."
        )

    return data


def fetch_multiple_expirations(
    symbol: str,
    expirations: list[date],
    contract_type: str = "ALL",
    strike_count: Optional[int] = None,
    client: Optional[schwab.client.Client] = None,
) -> dict[date, dict[str, Any]]:
    """
    Descarga la option chain para multiples vencimientos reusando el mismo cliente.

    Returns:
        {expiration: raw_data} con la misma estructura que fetch_option_chain().
    """
    if client is None:
        client = get_client()

    return {
        exp: fetch_option_chain(symbol, exp, contract_type, strike_count, client)
        for exp in expirations
    }
