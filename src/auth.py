"""
src/auth.py
Maneja la autenticación OAuth2 con la Schwab API usando schwab-py.

Flujo:
  1. Primera vez → abre el navegador para que el usuario autorice
  2. Guarda el token en token.pickle (gitignoreado)
  3. Siguientes ejecuciones → reusa/refresca el token automáticamente
"""

import pickle
import pathlib
import schwab

import config

TOKEN_PATH = pathlib.Path("token.pickle")


def get_client() -> schwab.client.Client:
    """
    Retorna un cliente autenticado de Schwab.
    Si no hay token guardado, inicia el flujo OAuth interactivo.
    """
    config.validate_config()

    if TOKEN_PATH.exists():
        # Token existente → intenta reusar (schwab-py lo refresca si venció)
        client = schwab.auth.client_from_token_file(
            token_path=str(TOKEN_PATH),
            api_key=config.SCHWAB_CLIENT_ID,
            app_secret=config.SCHWAB_CLIENT_SECRET,
        )
    else:
        # Primera vez → flujo interactivo por navegador
        print("=" * 60)
        print("Primera autenticación con Schwab API.")
        print("Se abrirá el navegador. Iniciá sesión con tu cuenta Schwab.")
        print("=" * 60)
        client = schwab.auth.client_from_login_flow(
            api_key=config.SCHWAB_CLIENT_ID,
            app_secret=config.SCHWAB_CLIENT_SECRET,
            callback_url=config.SCHWAB_REDIRECT_URI,
            token_path=str(TOKEN_PATH),
        )
        print(f"✅ Token guardado en {TOKEN_PATH}")

    return client
