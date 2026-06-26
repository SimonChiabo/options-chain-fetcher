"""
main.py
Entry point del proyecto. Acepta parametros por CLI.

Uso:
    python main.py --symbol SPY --expiration 2025-06-20
    python main.py --symbol QQQ --expiration 2025-03-21 --strikes 20
    python main.py --demo
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

import config
from config       import ConfigError
from src.auth     import get_client
from src.fetcher  import fetch_option_chain
from src.fetcher  import fetch_multiple_expirations
from src.parser   import parse_option_chain
from src.exporter import export_to_excel
from src.exporter import export_multiple_to_excel
from src.analyzer import calculate_max_pain, calculate_pc_ratio
from src.analyzer import calculate_iv_skew

console = Console()

_SAMPLE_PATH = Path(__file__).parent / "examples" / "sample_chain.json"


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
        required=False,
        default=None,
        type=str,
        help="Ticker del subyacente (ej: SPY, QQQ, AAPL)",
    )
    parser.add_argument(
        "--expiration", "-e",
        required=False,
        default=None,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Fecha de vencimiento en formato YYYY-MM-DD",
    )
    parser.add_argument(
        "--expirations", "-E",
        required=False,
        default=None,
        type=lambda s: [datetime.strptime(d.strip(), "%Y-%m-%d").date() for d in s.split(",")],
        help="Multiples vencimientos separados por coma: 2025-06-20,2025-07-18",
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
    parser.add_argument(
        "--demo",
        action="store_true",
        default=False,
        help="Modo demo: ejecuta el pipeline con datos de muestra incluidos, sin credenciales.",
    )
    args = parser.parse_args()
    if not args.demo and args.symbol is None:
        parser.error("--symbol / -s es requerido (o usa --demo para modo sin credenciales)")
    return args


def run_demo() -> None:
    """
    Ejecuta el pipeline completo contra el sample chain incluido en el repo.
    No requiere credenciales, red ni OAuth.
    """
    console.print(
        "\n[bold yellow][DEMO][/bold yellow] Modo demo activo. "
        "Datos de muestra incluidos: SPY 2025-06-20. Sin credenciales reales."
    )

    with open(_SAMPLE_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    symbol = "SPY"
    expiration = date(2025, 6, 20)

    calls_df, puts_df = parse_option_chain(raw, expiration)
    max_pain = calculate_max_pain(calls_df, puts_df)
    pc_ratio = calculate_pc_ratio(calls_df, puts_df)
    analysis = {"max_pain": max_pain, "pc_ratio": pc_ratio}

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Metrica",  style="cyan",       min_width=22)
    table.add_column("Valor",    style="bold green")
    table.add_row("Calls encontradas",   str(len(calls_df)))
    table.add_row("Puts encontradas",    str(len(puts_df)))
    table.add_row("Max Pain Strike",     f"${max_pain['strike']:.2f}")
    table.add_row("P/C Ratio (Volumen)", f"{pc_ratio['volume_ratio']:.2f}")
    table.add_row("P/C Ratio (OI)",      f"{pc_ratio['oi_ratio']:.2f}")
    console.print(table)

    filepath = export_to_excel(calls_df, puts_df, symbol, expiration, analysis=analysis)
    console.print(
        f"\n[bold green][DEMO OK][/bold green] Archivo demo: [underline]{filepath}[/underline]\n"
        "[dim]Nota: estos datos son de muestra, no cotizaciones reales.[/dim]\n"
    )


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()

    if args.demo:
        run_demo()
        return

    try:
        config.validate_config()
        args.symbol = _validate_symbol(args.symbol)

        console.print(
            f"\n[bold cyan][*][/bold cyan] Descargando option chain: "
            f"[bold]{args.symbol}[/bold] | Vencimiento: {args.expiration}"
        )

        client = get_client()

        if args.expirations:
            # -- Flujo multi-vencimiento ---------------------------------
            expirations = args.expirations
            console.print(f"    [dim]Vencimientos: {', '.join(str(e) for e in expirations)}[/dim]")

            raw_dict = fetch_multiple_expirations(
                symbol=args.symbol,
                expirations=expirations,
                contract_type=args.type,
                strike_count=args.strikes,
                client=client,
            )
            parsed = {exp: parse_option_chain(raw, exp) for exp, raw in raw_dict.items()}
            skew_df = calculate_iv_skew(parsed)

            total_calls = sum(len(calls) for calls, _ in parsed.values())
            total_puts  = sum(len(puts)  for _, puts  in parsed.values())

            table = Table(show_header=True, header_style="bold magenta", box=None)
            table.add_column("Metrica", style="cyan", min_width=22)
            table.add_column("Valor",   style="bold green")
            table.add_row("Total Calls",        str(total_calls))
            table.add_row("Total Puts",         str(total_puts))
            table.add_row("Vencimientos",       str(len(expirations)))
            table.add_row("Strikes en IV Skew", str(len(skew_df)))
            console.print(table)

            filepath = export_multiple_to_excel(parsed, skew_df, args.symbol)

        else:
            # -- Flujo single vencimiento (comportamiento original) -------
            if args.expiration is None:
                console.print("[bold red][ERROR][/bold red] Se requiere --expiration o --expirations")
                raise SystemExit(1)

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

            table = Table(show_header=True, header_style="bold magenta", box=None)
            table.add_column("Metrica", style="cyan", min_width=22)
            table.add_column("Valor",   style="bold green")
            table.add_row("Calls encontradas",   str(len(calls_df)))
            table.add_row("Puts encontradas",    str(len(puts_df)))
            table.add_row("Max Pain Strike",     f"${max_pain['strike']:.2f}")
            table.add_row("P/C Ratio (Volumen)", f"{pc_ratio['volume_ratio']:.2f}")
            table.add_row("P/C Ratio (OI)",      f"{pc_ratio['oi_ratio']:.2f}")
            console.print(table)

            filepath = export_to_excel(calls_df, puts_df, args.symbol, args.expiration, analysis=analysis)

        console.print(f"\n[bold green][OK][/bold green] Abri el archivo: [underline]{filepath}[/underline]\n")

    except (ValueError, ConfigError) as e:
        console.print(f"\n[bold red][ERROR][/bold red] {e}")
        raise SystemExit(1)
    except RuntimeError as e:
        console.print(f"\n[bold red][ERROR][/bold red] API: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
