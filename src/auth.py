"""
src/auth.py
Maneja la autenticacion OAuth2 con la Schwab API usando schwab-py.

Flujo:
  1. Primera vez -> abre el navegador para que el usuario autorice
  2. Guarda el token en token.pickle (gitignoreado)
  3. Siguientes ejecuciones -> reusa/refresca el token automaticamente
"""

import pathlib

import schwab

import config

TOKEN_PATH = pathlib.Path(__file__).parent.parent / "token.pickle"


def get_client() -> schwab.client.Client:
    """
    Retorna un cliente autenticado de Schwab.
    Si no hay token guardado, inicia el flujo OAuth interactivo via navegador.

    Raises:
        ConfigError: Si faltan SCHWAB_CLIENT_ID o SCHWAB_CLIENT_SECRET.
        Exception: Si el flujo OAuth falla (red no disponible, credenciales incorrectas).
    """
    config.validate_config()

    if TOKEN_PATH.exists():
        try:
            return schwab.auth.client_from_token_file(
                token_path=str(TOKEN_PATH),
                api_key=config.SCHWAB_CLIENT_ID,
                app_secret=config.SCHWAB_CLIENT_SECRET,
            )
        except Exception as e:
            print(f"[WARN] Token invalido o expirado ({e}). Iniciando nuevo flujo OAuth.")
            TOKEN_PATH.unlink(missing_ok=True)

    # Primera vez, o tras borrar token corrupto -> flujo interactivo por navegador
    print("=" * 60)
    print("Autenticacion con Schwab API.")
    print("Se abrira el navegador. Inicia sesion con tu cuenta Schwab.")
    print("=" * 60)

    client = schwab.auth.client_from_login_flow(
        api_key=config.SCHWAB_CLIENT_ID,
        app_secret=config.SCHWAB_CLIENT_SECRET,
        callback_url=config.SCHWAB_REDIRECT_URI,
        token_path=str(TOKEN_PATH),
    )
    print(f"[OK] Token guardado en: {TOKEN_PATH}")
    return client
