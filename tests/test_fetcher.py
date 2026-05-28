"""
tests/test_fetcher.py
Tests para src/fetcher.py. Usan mocks para evitar llamadas reales a la API.
"""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.fetcher import fetch_option_chain


EXPIRATION = date(2025, 6, 20)


def _mock_client(json_data: dict, status_ok: bool = True) -> MagicMock:
    """Crea un cliente mock que devuelve json_data como respuesta de la API."""
    mock_response = MagicMock()
    mock_response.ok = status_ok
    mock_response.status_code = 200 if status_ok else 400
    mock_response.text = ""
    mock_response.json.return_value = json_data

    mock_client = MagicMock()
    mock_client.get_option_chain.return_value = mock_response
    return mock_client


def test_fetch_raises_on_empty_option_maps():
    """Debe lanzar RuntimeError si la API devuelve callExpDateMap y putExpDateMap vacios."""
    client = _mock_client({
        "status": "SUCCESS",
        "callExpDateMap": {},
        "putExpDateMap":  {},
    })

    with pytest.raises(RuntimeError, match="No se encontraron opciones"):
        fetch_option_chain(
            symbol="XYZINVALID",
            expiration=EXPIRATION,
            client=client,
        )


def test_fetch_raises_on_failed_status():
    """Debe lanzar RuntimeError si la API devuelve status FAILED."""
    client = _mock_client({
        "status": "FAILED",
        "callExpDateMap": {},
        "putExpDateMap":  {},
    })

    with pytest.raises(RuntimeError, match="FAILED"):
        fetch_option_chain(
            symbol="SPY",
            expiration=EXPIRATION,
            client=client,
        )


def test_fetch_raises_on_http_error():
    """Debe lanzar RuntimeError si el HTTP response no es ok."""
    client = _mock_client({}, status_ok=False)
    client.get_option_chain.return_value.status_code = 401
    client.get_option_chain.return_value.text = "Unauthorized"

    with pytest.raises(RuntimeError, match="401"):
        fetch_option_chain(
            symbol="SPY",
            expiration=EXPIRATION,
            client=client,
        )


def test_fetch_raises_on_invalid_contract_type():
    """Debe lanzar ValueError si contract_type no es ALL, CALL o PUT."""
    client = _mock_client({})

    with pytest.raises(ValueError, match="contract_type invalido"):
        fetch_option_chain(
            symbol="SPY",
            expiration=EXPIRATION,
            contract_type="CALLS",   # error tipico del usuario
            client=client,
        )


def test_fetch_returns_data_when_valid():
    """Debe retornar el dict de la API cuando hay contratos disponibles."""
    valid_data = {
        "status": "SUCCESS",
        "callExpDateMap": {"2025-06-20:30": {"500.0": [{"bid": 1.0}]}},
        "putExpDateMap":  {"2025-06-20:30": {"500.0": [{"bid": 0.8}]}},
    }
    client = _mock_client(valid_data)

    result = fetch_option_chain(symbol="SPY", expiration=EXPIRATION, client=client)

    assert result == valid_data


# -- Tests de parametros pasados al cliente ----------------------------

VALID_RESPONSE = {
    "status": "SUCCESS",
    "callExpDateMap": {"2025-06-20:30": {"500.0": [{"bid": 1.0}]}},
    "putExpDateMap":  {"2025-06-20:30": {"500.0": [{"bid": 0.8}]}},
}


def _mock_client_with_response(data=None):
    """Crea un mock client con response configurable."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = data or VALID_RESPONSE
    client = MagicMock()
    client.get_option_chain.return_value = mock_response
    return client


def test_strike_count_is_passed_to_api_when_specified():
    """Cuando se indica strike_count, debe llegar como kwarg al cliente."""
    client = _mock_client_with_response()

    fetch_option_chain(
        symbol="SPY",
        expiration=EXPIRATION,
        strike_count=10,
        client=client,
    )

    _, kwargs = client.get_option_chain.call_args
    assert "strike_count" in kwargs, "strike_count no se paso al cliente de la API"
    assert kwargs["strike_count"] == 10


def test_strike_count_is_omitted_when_none():
    """Cuando strike_count es None, NO debe aparecer en los kwargs."""
    client = _mock_client_with_response()

    fetch_option_chain(
        symbol="SPY",
        expiration=EXPIRATION,
        strike_count=None,
        client=client,
    )

    _, kwargs = client.get_option_chain.call_args
    assert "strike_count" not in kwargs, "strike_count=None no debe pasarse a la API"


def test_symbol_is_uppercased_before_api_call():
    """El simbolo debe llegar en uppercase al cliente independientemente del input."""
    client = _mock_client_with_response()

    fetch_option_chain(symbol="spy", expiration=EXPIRATION, client=client)

    _, kwargs = client.get_option_chain.call_args
    assert kwargs["symbol"] == "SPY"


# -- Tests para fetch_multiple_expirations --------------------------------

from src.fetcher import fetch_multiple_expirations


VALID_MULTI = {
    "status": "SUCCESS",
    "callExpDateMap": {"2025-06-20:30": {"500.0": [{"bid": 1.0}]}},
    "putExpDateMap":  {"2025-06-20:30": {"500.0": [{"bid": 0.8}]}},
}


def test_fetch_multiple_returns_dict_keyed_by_date():
    exp1 = date(2025, 6, 20)
    exp2 = date(2025, 7, 18)
    client = _mock_client_with_response(VALID_MULTI)
    results = fetch_multiple_expirations("SPY", [exp1, exp2], client=client)
    assert set(results.keys()) == {exp1, exp2}


def test_fetch_multiple_calls_api_once_per_expiration():
    exp1 = date(2025, 6, 20)
    exp2 = date(2025, 7, 18)
    client = _mock_client_with_response(VALID_MULTI)
    fetch_multiple_expirations("SPY", [exp1, exp2], client=client)
    assert client.get_option_chain.call_count == 2


def test_fetch_multiple_single_expiration_works():
    exp = date(2025, 6, 20)
    client = _mock_client_with_response(VALID_MULTI)
    results = fetch_multiple_expirations("SPY", [exp], client=client)
    assert exp in results
    assert results[exp] == VALID_MULTI
