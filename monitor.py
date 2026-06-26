"""
monitor.py
Monitor continuo de cadenas de opciones. Hace polling, evalua reglas YAML y
dispara alertas a los canales configurados.

Uso:
    python monitor.py --symbol SPY --expiration 2026-07-17 --rules rules.yaml
"""

import argparse
import logging
import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Optional

from rich.console import Console

import config
from config import ConfigError
from src.auth import get_client
from src.fetcher import fetch_option_chain
from src.parser import parse_option_chain, extract_underlying_price
from src.normalizer import normalize_chain
from src.analyzer import build_chain_metrics
from src.rules import load_rules, evaluate_rules, Rule, Alert
from src.alert_state import AlertState
from src.notifier import build_notifier_from_config

log = logging.getLogger(__name__)
console = Console()

_MARKET_TZ = ZoneInfo("America/New_York")


def is_market_hours(now: Optional[datetime] = None) -> bool:
    """True si now cae en horario regular del mercado US (Lun-Vie 09:30-16:00 ET)."""
    now = now or datetime.now(_MARKET_TZ)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 16 * 60


def run_cycle(
    client,
    symbol: str,
    expiration: date,
    rules: list[Rule],
    state: AlertState,
    notifier,
    contract_type: str,
    strike_count: Optional[int],
    iv_scale: str,
    now: Optional[datetime] = None,
) -> list[Alert]:
    """Un ciclo: fetch -> normalize -> evaluar -> filtrar cooldown -> notificar."""
    now = now or datetime.now()
    try:
        raw = fetch_option_chain(
            symbol=symbol, expiration=expiration, contract_type=contract_type,
            strike_count=strike_count, client=client,
        )
    except (RuntimeError, ValueError) as exc:
        log.debug("Ciclo fallo para %s: %s", symbol, exc)
        console.print(f"[yellow][WARN][/yellow] Fallo el ciclo para {symbol}; se reintenta.")
        return []

    calls_df, puts_df = parse_option_chain(raw, expiration)
    underlying = extract_underlying_price(raw)
    calls_n, puts_n = normalize_chain(calls_df, puts_df, underlying, iv_scale)
    metrics = build_chain_metrics(calls_n, puts_n, underlying)
    alerts = evaluate_rules(rules, calls_n, puts_n, metrics, symbol, now=now)
    to_notify = state.update(alerts, now=now)

    for alert in to_notify:
        notifier.send(alert)
        console.print(f"[bold red][ALERTA][/bold red] {alert.message}")

    return to_notify


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor continuo de alertas de opciones.")
    parser.add_argument("--symbol", "-s", required=True, type=str)
    parser.add_argument(
        "--expiration", "-e", required=True,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
    )
    parser.add_argument("--rules", default="rules.yaml", type=str)
    parser.add_argument("--interval", type=int, default=config.REFRESH_INTERVAL)
    parser.add_argument("--type", "-t", choices=["ALL", "CALL", "PUT"], default="ALL")
    parser.add_argument("--strikes", "-k", type=int, default=None)
    parser.add_argument("--market-hours-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        config.validate_config()
        config.validate_alert_config()
        args = parse_args()

        rules = load_rules(args.rules)
        notifier = build_notifier_from_config()
        state = AlertState(min_interval=config.ALERT_MIN_INTERVAL)
        client = get_client()

        console.print(
            f"[bold cyan][*][/bold cyan] Monitoreando {args.symbol} "
            f"venc {args.expiration} cada {args.interval}s "
            f"({len(rules)} reglas)"
        )

        while True:
            if args.market_hours_only and not is_market_hours():
                console.print("[dim]Fuera de horario de mercado; se omite el ciclo.[/dim]")
            else:
                run_cycle(
                    client=client, symbol=args.symbol, expiration=args.expiration,
                    rules=rules, state=state, notifier=notifier,
                    contract_type=args.type, strike_count=args.strikes,
                    iv_scale=config.IV_INPUT_SCALE,
                )
            time.sleep(args.interval)

    except KeyboardInterrupt:
        console.print("\n[bold green][OK][/bold green] Monitor detenido.")
    except (ValueError, ConfigError) as exc:
        console.print(f"\n[bold red][ERROR][/bold red] {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
