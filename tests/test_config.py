"""Tests para config.py -- validacion de credenciales."""

import pytest

import config
from config import ConfigError, validate_config


def test_validate_config_raises_when_both_missing(monkeypatch):
    """Debe lanzar ConfigError si CLIENT_ID y CLIENT_SECRET estan vacios."""
    monkeypatch.setattr(config, "SCHWAB_CLIENT_ID",     "")
    monkeypatch.setattr(config, "SCHWAB_CLIENT_SECRET", "")

    with pytest.raises(ConfigError, match="SCHWAB_CLIENT_ID"):
        validate_config()


def test_validate_config_raises_when_only_secret_missing(monkeypatch):
    """Debe lanzar ConfigError si falta solo CLIENT_SECRET."""
    monkeypatch.setattr(config, "SCHWAB_CLIENT_ID",     "alguna_id")
    monkeypatch.setattr(config, "SCHWAB_CLIENT_SECRET", "")

    with pytest.raises(ConfigError, match="SCHWAB_CLIENT_SECRET"):
        validate_config()


def test_validate_config_raises_configerror_not_environment_error(monkeypatch):
    """La excepcion debe ser ConfigError, no EnvironmentError generico."""
    monkeypatch.setattr(config, "SCHWAB_CLIENT_ID",     "")
    monkeypatch.setattr(config, "SCHWAB_CLIENT_SECRET", "")

    with pytest.raises(ConfigError):
        validate_config()

    # Regresion: garantizar que NO es EnvironmentError
    try:
        validate_config()
    except ConfigError:
        pass
    except EnvironmentError as e:
        pytest.fail(f"validate_config() lanzo EnvironmentError en vez de ConfigError: {e}")


def test_validate_config_passes_when_both_present(monkeypatch):
    """No debe lanzar nada si ambas credenciales estan presentes."""
    monkeypatch.setattr(config, "SCHWAB_CLIENT_ID",     "real_id")
    monkeypatch.setattr(config, "SCHWAB_CLIENT_SECRET", "real_secret")

    validate_config()  # no debe lanzar
