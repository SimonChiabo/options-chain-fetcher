"""Tests para src/auth.py -- flujos de autenticacion OAuth."""

import pathlib
from unittest.mock import MagicMock, patch

import pytest

import src.auth as auth_module


@pytest.fixture(autouse=True)
def patch_config(monkeypatch):
    """Inyecta credenciales validas para todos los tests de auth."""
    monkeypatch.setattr("config.SCHWAB_CLIENT_ID",     "fake_id")
    monkeypatch.setattr("config.SCHWAB_CLIENT_SECRET", "fake_secret")
    monkeypatch.setattr("config.SCHWAB_REDIRECT_URI",  "https://127.0.0.1:8182")


def test_corrupted_token_triggers_reauth_and_deletes_file(tmp_path, monkeypatch):
    """
    Si token existe pero es invalido, get_client() debe:
      1. Capturar la excepcion
      2. Borrar el archivo corrupto
      3. Iniciar el flujo OAuth interactivo como fallback
    """
    fake_token = tmp_path / "token.pickle"
    fake_token.write_text("esto no es un token valido")
    monkeypatch.setattr(auth_module, "TOKEN_PATH", fake_token)

    mock_client = MagicMock()

    with (
        patch("schwab.auth.client_from_token_file", side_effect=ValueError("token malformado")),
        patch("schwab.auth.client_from_login_flow", return_value=mock_client) as mock_login,
    ):
        result = auth_module.get_client()

    assert not fake_token.exists(), "El token corrupto debe eliminarse antes del reauth"
    mock_login.assert_called_once()
    assert result is mock_client


def test_valid_token_returns_client_without_login_flow(tmp_path, monkeypatch):
    """Si el token es valido, NO debe iniciar el flujo interactivo."""
    fake_token = tmp_path / "token.pickle"
    fake_token.write_text("placeholder")
    monkeypatch.setattr(auth_module, "TOKEN_PATH", fake_token)

    mock_client = MagicMock()

    with (
        patch("schwab.auth.client_from_token_file", return_value=mock_client),
        patch("schwab.auth.client_from_login_flow") as mock_login,
    ):
        result = auth_module.get_client()

    mock_login.assert_not_called()
    assert result is mock_client
