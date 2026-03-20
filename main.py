"""
main.py
Entry point del proyecto. Acepta parametros por CLI.

Uso:
    python main.py --symbol SPY --expiration 2025-06-20
    python main.py --symbol QQQ --expiration 2025-03-21 --strikes 20
"""

import argparse
from datetime import date, datetime

from src.fetcher  import fetch_option_chain
from src.parser   import parse_option_chain
from src.exporter import export_to_excel


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
    args = parse_args()

    print(f"\n[*] Descargando option chain: {args.symbol} | Vencimiento: {args.expiration}")

    raw = fetch_option_chain(
        symbol=args.symbol,
        expiration=args.expiration,
        contract_type=args.type,
        strike_count=args.strikes,
    )

    calls_df, puts_df = parse_option_chain(raw, args.expiration)

    print(f"    -> {len(calls_df)} calls | {len(puts_df)} puts encontradas")

    filepath = export_to_excel(calls_df, puts_df, args.symbol, args.expiration)

    print(f"\n[OK] Listo. Abri el archivo: {filepath}\n")


if __name__ == "__main__":
    main()
