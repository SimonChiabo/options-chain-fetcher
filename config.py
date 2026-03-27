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
REFRESH_INTERVAL     = int(os.getenv("REFRESH_INTERVAL", 60))

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

PUTS_COLUMNS = CALLS_COLUMNS  # misma estructura


def validate_config() -> None:
    """Lanza un error claro si faltan credenciales."""
    missing = []
    if not SCHWAB_CLIENT_ID:
        missing.append("SCHWAB_CLIENT_ID")
    if not SCHWAB_CLIENT_SECRET:
        missing.append("SCHWAB_CLIENT_SECRET")
    if missing:
        raise EnvironmentError(
            f"Faltan variables de entorno: {', '.join(missing)}\n"
            "Copia .env.example a .env y completa tus credenciales."
        )
