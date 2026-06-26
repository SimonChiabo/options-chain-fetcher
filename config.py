"""
config.py
Configuracion central. Lee variables del .env y expone
constantes usadas en todo el proyecto.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# -- Schwab API ----------------------------------------------
SCHWAB_CLIENT_ID     = os.getenv("SCHWAB_CLIENT_ID", "")
SCHWAB_CLIENT_SECRET = os.getenv("SCHWAB_CLIENT_SECRET", "")
SCHWAB_REDIRECT_URI  = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8182")  # puerto obligatorio

# -- Salida ---------------------------------------------------
OUTPUT_DIR           = os.getenv("OUTPUT_DIR", "output")
REFRESH_INTERVAL     = int(os.getenv("REFRESH_INTERVAL", "60"))

# -- Normalizacion / alertas ----------------------------------
IV_INPUT_SCALE       = os.getenv("IV_INPUT_SCALE", "percent")  # "percent" | "decimal"
ALERT_MIN_INTERVAL   = int(os.getenv("ALERT_MIN_INTERVAL", "300"))  # segundos
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "")
ALERTS_DESKTOP       = os.getenv("ALERTS_DESKTOP", "true").lower() == "true"
ALERTS_TELEGRAM      = os.getenv("ALERTS_TELEGRAM", "false").lower() == "true"

# -- Columnas que se exportan al Excel ------------------------
CALLS_COLUMNS = [
    "strike",
    "bid",
    "ask",
    "spread",
    "last",
    "volume",
    "openInterest",
    "delta",
    "gamma",
    "theta",
    "vega",
    "impliedVolatility",
    "inTheMoney",
    "expirationDate",
]

PUTS_COLUMNS = list(CALLS_COLUMNS)  # copia independiente

NUMERIC_COLUMNS = [
    "strike", "bid", "ask", "last", "volume", "openInterest",
    "delta", "gamma", "theta", "vega", "impliedVolatility",
]


class ConfigError(Exception):
    """Credenciales o variables de entorno faltantes."""


def validate_config() -> None:
    """Lanza un error claro si faltan credenciales."""
    missing = []
    if not SCHWAB_CLIENT_ID:
        missing.append("SCHWAB_CLIENT_ID")
    if not SCHWAB_CLIENT_SECRET:
        missing.append("SCHWAB_CLIENT_SECRET")
    if missing:
        raise ConfigError(
            f"Faltan variables de entorno: {', '.join(missing)}\n"
            "Copia .env.example a .env y completa tus credenciales."
        )


def validate_alert_config() -> None:
    """Si Telegram esta habilitado, exige sus credenciales."""
    if ALERTS_TELEGRAM:
        missing = []
        if not TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not TELEGRAM_CHAT_ID:
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            raise ConfigError(
                f"Telegram habilitado pero faltan: {', '.join(missing)}"
            )
