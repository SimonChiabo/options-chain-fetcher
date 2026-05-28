"""
main.py
Entry point del proyecto. Acepta parametros por CLI.

Uso:
    python main.py --symbol SPY --expiration 2025-06-20
    python main.py --symbol QQQ --expiration 2025-03-21 --strikes 20
"""

import argparse
import re
import sys
from datetime import datetime

import config
from config       import ConfigError
from src.auth     import get_client
from src.fetcher  import fetch_option_chain
from src.parser   import parse_option_chain
from src.exporter import export_to_excel
from src.analyzer import calculate_max_pain, calculate_pc_ratio


def _validate_symbol(symbol: str) -> str:
    """Solo letras, numeros y punto. Maximo 10 caracteres."""
    if not re.fullmatch(r"[A-Za-z0-9.]{1,10}", symbol):
        raise ValueError(
            f"Simbolo invalido: '{symbol}'. "
            "Solo letras, numeros y punto. Maximo 10 caracteres."
        )
    return symbol.upper()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga option chains desde Schwab API y exporta a Excel."
    )
    parser.add_argument(
        "--symbol", "-s",
        required=True,
        type=str,
        help="Ticker del subyacente (ej: SPY, QQQ, AAPL)",
    )
    parser.add_argument(
        "--expiration", "-e",
        required=True,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Fecha de vencimiento en formato YYYY-MM-DD",
    )
    parser.add_argument(
        "--strikes", "-k",
        required=False,
        type=int,
        default=None,
        help="Cantidad de strikes a cada lado del ATM (default: todos)",
    )
    parser.add_argument(
        "--type", "-t",
        required=False,
        choices=["ALL", "CALL", "PUT"],
        default="ALL",
        help="Tipo de contrato: ALL, CALL o PUT (default: ALL)",
    )
    return parser.parse_args()


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        config.validate_config()
        args = parse_args()
        args.symbol = _validate_symbol(args.symbol)

        print(f"\n[*] Descargando option chain: {args.symbol} | Vencimiento: {args.expiration}")

        client = get_client()

        raw = fetch_option_chain(
            symbol=args.symbol,
            expiration=args.expiration,
            contract_type=args.type,
            strike_count=args.strikes,
            client=client,
        )

        calls_df, puts_df = parse_option_chain(raw, args.expiration)

        max_pain = calculate_max_pain(calls_df, puts_df)
        pc_ratio = calculate_pc_ratio(calls_df, puts_df)
        analysis = {"max_pain": max_pain, "pc_ratio": pc_ratio}

        print(f"    -> {len(calls_df)} calls | {len(puts_df)} puts encontradas")
        print(f"    -> Max Pain: ${max_pain['strike']:.2f}")
        print(f"    -> P/C Ratio  Vol: {pc_ratio['volume_ratio']:.2f}  |  OI: {pc_ratio['oi_ratio']:.2f}")

        filepath = export_to_excel(calls_df, puts_df, args.symbol, args.expiration, analysis=analysis)

        print(f"\n[OK] Listo. Abri el archivo: {filepath}\n")

    except (ValueError, ConfigError) as e:
        print(f"\n[ERROR] {e}")
        raise SystemExit(1)
    except RuntimeError as e:
        print(f"\n[ERROR] API: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
