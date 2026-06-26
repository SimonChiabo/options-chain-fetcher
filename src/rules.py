"""
src/rules.py
Motor de reglas declarativo. Carga reglas desde YAML y las evalua contra
una cadena normalizada + metricas chain-level. Sin eval ni expresiones libres.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import math
import pandas as pd
import yaml

from config import ConfigError

CONTRACT_FIELDS = {
    "strike", "bid", "ask", "mid", "spread", "spread_pct", "last",
    "volume", "openInterest", "delta", "gamma", "theta", "vega",
    "iv", "moneyness", "inTheMoney",
}
CHAIN_FIELDS = {
    "pc_volume_ratio", "pc_oi_ratio", "max_pain_strike", "underlying_price",
    "distance_to_max_pain", "distance_to_max_pain_pct",
}
_RANGE_OPERATORS = {"between", "outside"}
_SCALAR_OPERATORS = {"gt", "lt", "gte", "lte", "eq"}
OPERATORS = _SCALAR_OPERATORS | _RANGE_OPERATORS


@dataclass(frozen=True)
class Rule:
    name: str
    scope: str
    field: str
    operator: str
    value: Any
    type: Optional[str] = None
    strike_min: Optional[float] = None
    strike_max: Optional[float] = None
    message: str = ""


@dataclass(frozen=True)
class Alert:
    rule_name: str
    symbol: str
    scope: str
    subject: str
    field: str
    value: float
    threshold: Any
    timestamp: datetime
    message: str


def _apply(operator: str, x: Any, value: Any) -> bool:
    if x is None:
        return False
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return False
    if math.isnan(xf):
        return False

    if operator == "gt":
        return xf > value
    if operator == "lt":
        return xf < value
    if operator == "gte":
        return xf >= value
    if operator == "lte":
        return xf <= value
    if operator == "eq":
        return xf == value
    if operator == "between":
        return value[0] <= xf <= value[1]
    if operator == "outside":
        return xf < value[0] or xf > value[1]
    return False


def _validate(rule: Rule) -> None:
    if rule.scope not in ("contract", "chain"):
        raise ConfigError(f"Regla '{rule.name}': scope invalido '{rule.scope}'")
    if rule.operator not in OPERATORS:
        raise ConfigError(f"Regla '{rule.name}': operador invalido '{rule.operator}'")
    valid_fields = CONTRACT_FIELDS if rule.scope == "contract" else CHAIN_FIELDS
    if rule.field not in valid_fields:
        raise ConfigError(f"Regla '{rule.name}': campo invalido '{rule.field}' para scope {rule.scope}")
    if rule.operator in _RANGE_OPERATORS:
        if not isinstance(rule.value, (list, tuple)) or len(rule.value) != 2:
            raise ConfigError(f"Regla '{rule.name}': '{rule.operator}' requiere value [min, max]")
    if rule.scope == "contract" and rule.type not in (None, "ALL", "CALL", "PUT"):
        raise ConfigError(f"Regla '{rule.name}': type invalido '{rule.type}'")


def load_rules(path: str) -> list[Rule]:
    """Carga y valida reglas desde un archivo YAML."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    raw_rules = data.get("rules", [])
    rules: list[Rule] = []
    for entry in raw_rules:
        strike = entry.get("strike")
        rule = Rule(
            name=entry.get("name", "unnamed"),
            scope=entry.get("scope", "contract"),
            field=entry.get("field", ""),
            operator=entry.get("operator", ""),
            value=entry.get("value"),
            type=entry.get("type"),
            strike_min=float(strike) if strike is not None else entry.get("strike_min"),
            strike_max=float(strike) if strike is not None else entry.get("strike_max"),
            message=entry.get("message", ""),
        )
        _validate(rule)
        rules.append(rule)
    return rules


def _default_message(rule: Rule, subject: str, x: float) -> str:
    if rule.message:
        return rule.message
    return f"{rule.name}: {subject} {rule.field}={x} {rule.operator} {rule.value}"


def _eval_contract(rule: Rule, df: pd.DataFrame, side: str, symbol: str, now: datetime) -> list[Alert]:
    if df.empty or rule.field not in df.columns:
        return []

    work = df
    if "no_quote" in work.columns:
        work = work[~work["no_quote"].astype(bool)]
    if rule.strike_min is not None and "strike" in work.columns:
        work = work[work["strike"] >= rule.strike_min]
    if rule.strike_max is not None and "strike" in work.columns:
        work = work[work["strike"] <= rule.strike_max]

    alerts: list[Alert] = []
    for _, row in work.iterrows():
        x = row[rule.field]
        if not _apply(rule.operator, x, rule.value):
            continue
        strike = row.get("strike", "?")
        subject = f"{symbol} {strike:g}{side}" if isinstance(strike, (int, float)) else f"{symbol} {strike}{side}"
        alerts.append(Alert(
            rule_name=rule.name, symbol=symbol, scope="contract", subject=subject,
            field=rule.field, value=float(x), threshold=rule.value, timestamp=now,
            message=_default_message(rule, subject, float(x)),
        ))
    return alerts


def evaluate_rules(
    rules: list[Rule],
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    chain_metrics: dict[str, float],
    symbol: str,
    now: Optional[datetime] = None,
) -> list[Alert]:
    """Evalua todas las reglas y devuelve la lista de Alert activas este ciclo."""
    now = now or datetime.now()
    alerts: list[Alert] = []

    for rule in rules:
        if rule.scope == "chain":
            x = chain_metrics.get(rule.field)
            if _apply(rule.operator, x, rule.value):
                alerts.append(Alert(
                    rule_name=rule.name, symbol=symbol, scope="chain", subject="chain",
                    field=rule.field, value=float(x), threshold=rule.value, timestamp=now,
                    message=_default_message(rule, "chain", float(x)),
                ))
            continue

        if rule.type in (None, "CALL", "ALL"):
            alerts.extend(_eval_contract(rule, calls_df, "C", symbol, now))
        if rule.type in (None, "PUT", "ALL"):
            alerts.extend(_eval_contract(rule, puts_df, "P", symbol, now))

    return alerts
