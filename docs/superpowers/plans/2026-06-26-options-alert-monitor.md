# Options Alert Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a continuous monitor that polls option chains, evaluates user-defined YAML rules, and fires market-signal alerts to Windows toast + Telegram.

**Architecture:** New `monitor.py` entry point reuses the existing fetcher/parser/analyzer and adds four focused layers: a pure `normalizer` (cleans data, derives metrics), a `rules` engine (YAML -> Alert objects), an `alert_state` cooldown gate (edge-triggered), and a pluggable `notifier`. Each layer is a single-responsibility module tested in isolation with no network.

**Tech Stack:** Python 3, pandas, PyYAML (new), requests (Telegram), windows-toasts (new, lazy import), pytest. Follows CLAUDE.md: type hints everywhere, no emojis/tildes in source, `ConfigError` for config validation, never log token/response.text, conventional commits.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/normalizer.py` (create) | Canonicalize field names, strip sentinels, flag no-quote, derive `mid`/`spread_pct`/`moneyness`, normalize IV scale |
| `src/parser.py` (modify) | Add `extract_underlying_price(raw)` helper |
| `src/analyzer.py` (modify) | Add `build_chain_metrics()` assembling chain-level metric dict |
| `src/rules.py` (create) | `Rule`/`Alert` dataclasses, `load_rules()`, `evaluate_rules()`, operators |
| `src/alert_state.py` (create) | `AlertState` edge-triggered cooldown gate |
| `src/notifier.py` (create) | `Notifier` protocol, `TelegramNotifier`, `DesktopNotifier`, `CompositeNotifier`, factory |
| `config.py` (modify) | Telegram creds, IV scale, min-interval, channel flags, conditional validation |
| `monitor.py` (create) | CLI + polling loop + `run_cycle()` + market-hours helper |
| `requirements.txt` (modify) | Add `PyYAML`, `windows-toasts` |
| `rules.example.yaml` (create) | Sample rules file for the user |
| `tests/test_normalizer.py` etc. (create) | One test module per new source module |

---

## Task 1: Normalizer

**Files:**
- Create: `src/normalizer.py`
- Modify: `config.py` (add `IV_INPUT_SCALE`)
- Test: `tests/test_normalizer.py`

- [ ] **Step 1: Add IV scale config constant**

In `config.py`, after the `REFRESH_INTERVAL` line (line 19), add:

```python
# -- Normalizacion / alertas ----------------------------------
IV_INPUT_SCALE       = os.getenv("IV_INPUT_SCALE", "percent")  # "percent" | "decimal"
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_normalizer.py`:

```python
"""Tests para src/normalizer.py. Sin red ni credenciales."""

import math
import numpy as np
import pandas as pd
import pytest

from src.normalizer import normalize_chain


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestCanonicalize:
    def test_volatility_alias_becomes_iv(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "volatility": 20.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert "iv" in out.columns
        assert "volatility" not in out.columns

    def test_implied_volatility_alias_becomes_iv(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "impliedVolatility": 20.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert "iv" in out.columns

    def test_total_volume_alias_becomes_volume(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "totalVolume": 500}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert "volume" in out.columns
        assert out.iloc[0]["volume"] == 500


class TestSentinels:
    def test_minus_999_greek_becomes_nan(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "delta": -999.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert math.isnan(out.iloc[0]["delta"])

    def test_inf_iv_becomes_nan(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "iv": np.inf}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert math.isnan(out.iloc[0]["iv"])


class TestDerived:
    def test_no_quote_flag(self):
        calls = _df([{"strike": 100.0, "bid": 0.0, "ask": 0.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert bool(out.iloc[0]["no_quote"]) is True

    def test_quoted_is_not_no_quote(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert bool(out.iloc[0]["no_quote"]) is False

    def test_mid_computed(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert abs(out.iloc[0]["mid"] - 1.1) < 1e-9

    def test_mid_nan_when_no_quote(self):
        calls = _df([{"strike": 100.0, "bid": 0.0, "ask": 0.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert math.isnan(out.iloc[0]["mid"])

    def test_spread_pct_computed(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        # spread=0.2, mid=1.1 -> 0.1818...
        assert abs(out.iloc[0]["spread_pct"] - (0.2 / 1.1)) < 1e-6

    def test_moneyness_computed(self):
        calls = _df([{"strike": 110.0, "bid": 1.0, "ask": 1.2}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0)
        assert abs(out.iloc[0]["moneyness"] - 1.1) < 1e-9


class TestIVScale:
    def test_percent_scale_divides_by_100(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "iv": 25.0}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0, iv_scale="percent")
        assert abs(out.iloc[0]["iv"] - 0.25) < 1e-9

    def test_decimal_scale_passthrough(self):
        calls = _df([{"strike": 100.0, "bid": 1.0, "ask": 1.2, "iv": 0.25}])
        out, _ = normalize_chain(calls, pd.DataFrame(), underlying_price=100.0, iv_scale="decimal")
        assert abs(out.iloc[0]["iv"] - 0.25) < 1e-9


def test_empty_dataframe_is_safe():
    out, _ = normalize_chain(pd.DataFrame(), pd.DataFrame(), underlying_price=100.0)
    assert out.empty
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_normalizer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.normalizer'`

- [ ] **Step 4: Write the implementation**

Create `src/normalizer.py`:

```python
"""
src/normalizer.py
Capa de normalizacion: limpia la salida del parser y deriva metricas
por-contrato listas para el motor de reglas. Funcion pura, sin red.
"""

import numpy as np
import pandas as pd

import config

# Unico lugar a corregir cuando llegue la primera respuesta real de Schwab.
_FIELD_ALIASES = {
    "impliedVolatility": "iv",
    "volatility": "iv",
    "totalVolume": "volume",
}

_SENTINEL = -999.0
_SENTINEL_COLUMNS = ["delta", "gamma", "theta", "vega", "iv"]


def _canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    rename = {src: dst for src, dst in _FIELD_ALIASES.items()
              if src in df.columns and dst not in df.columns}
    return df.rename(columns=rename)


def _strip_sentinels(df: pd.DataFrame) -> None:
    for col in _SENTINEL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].replace(_SENTINEL, np.nan)
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)


def _normalize_one(df: pd.DataFrame, underlying_price: float, iv_scale: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    df = _canonicalize(df).copy()
    _strip_sentinels(df)

    bid = df["bid"] if "bid" in df.columns else pd.Series(np.nan, index=df.index)
    ask = df["ask"] if "ask" in df.columns else pd.Series(np.nan, index=df.index)

    df["no_quote"] = ~((bid > 0) | (ask > 0))

    mid = (bid + ask) / 2
    mid = mid.where(~df["no_quote"], np.nan)
    df["mid"] = mid.round(4)

    if "spread" not in df.columns:
        df["spread"] = (ask - bid).round(4)
    df["spread_pct"] = (df["spread"] / mid).round(6)

    if underlying_price and underlying_price > 0 and "strike" in df.columns:
        df["moneyness"] = (df["strike"] / underlying_price).round(6)
    else:
        df["moneyness"] = np.nan

    if "iv" in df.columns and iv_scale == "percent":
        df["iv"] = df["iv"] / 100.0

    return df


def normalize_chain(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    underlying_price: float,
    iv_scale: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Normaliza ambos lados de la cadena.

    Args:
        calls_df, puts_df: DataFrames del parser.
        underlying_price:  Precio del subyacente (para moneyness).
        iv_scale:          "percent" o "decimal". None usa config.IV_INPUT_SCALE.

    Returns:
        (calls_norm, puts_norm) con columnas iv, no_quote, mid, spread_pct, moneyness.
    """
    scale = iv_scale or config.IV_INPUT_SCALE
    calls = _normalize_one(calls_df, underlying_price, scale)
    puts = _normalize_one(puts_df, underlying_price, scale)
    return calls, puts
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_normalizer.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit**

```bash
git add src/normalizer.py tests/test_normalizer.py config.py
git commit -m "feat: add normalizer layer for clean per-contract metrics"
```

---

## Task 2: Parser underlying-price extraction

**Files:**
- Modify: `src/parser.py`
- Test: `tests/test_parser.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parser.py`:

```python
from src.parser import extract_underlying_price


def test_extract_underlying_price_present():
    raw = {"underlyingPrice": 581.25, "callExpDateMap": {}}
    assert extract_underlying_price(raw) == 581.25


def test_extract_underlying_price_missing_defaults_zero():
    assert extract_underlying_price({}) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parser.py::test_extract_underlying_price_present -v`
Expected: FAIL with `ImportError: cannot import name 'extract_underlying_price'`

- [ ] **Step 3: Write the implementation**

In `src/parser.py`, add after the imports block (after line 10):

```python
def extract_underlying_price(raw: dict) -> float:
    """Precio del subyacente desde la respuesta cruda. 0.0 si falta."""
    try:
        return float(raw.get("underlyingPrice", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_parser.py -v`
Expected: PASS (existing parser tests stay green plus the two new ones)

- [ ] **Step 5: Commit**

```bash
git add src/parser.py tests/test_parser.py
git commit -m "feat: extract underlying price from raw chain response"
```

---

## Task 3: Chain-level metrics builder

**Files:**
- Modify: `src/analyzer.py`
- Test: `tests/test_analyzer.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_analyzer.py`:

```python
from src.analyzer import build_chain_metrics


class TestChainMetrics:
    def test_keys_present(self):
        calls = _make_df([100, 105], [1000, 2000], [100, 200])
        puts = _make_df([100, 105], [500, 1500], [150, 150])
        m = build_chain_metrics(calls, puts, underlying_price=103.0)
        for key in (
            "pc_volume_ratio", "pc_oi_ratio", "max_pain_strike",
            "underlying_price", "distance_to_max_pain", "distance_to_max_pain_pct",
        ):
            assert key in m

    def test_distance_to_max_pain(self):
        calls = _make_df([100, 105, 110], [100, 50, 200])
        puts = _make_df([100, 105, 110], [300, 100, 50])
        m = build_chain_metrics(calls, puts, underlying_price=108.0)
        # max pain strike is 105.0 (see TestMaxPain) -> distance = 3.0
        assert m["max_pain_strike"] == 105.0
        assert abs(m["distance_to_max_pain"] - 3.0) < 1e-9
        assert abs(m["distance_to_max_pain_pct"] - 3.0 / 108.0) < 1e-9

    def test_zero_underlying_distance_pct_is_inf(self):
        calls = _make_df([100], [100])
        puts = _make_df([100], [100])
        m = build_chain_metrics(calls, puts, underlying_price=0.0)
        assert m["distance_to_max_pain_pct"] == float("inf")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analyzer.py::TestChainMetrics -v`
Expected: FAIL with `ImportError: cannot import name 'build_chain_metrics'`

- [ ] **Step 3: Write the implementation**

In `src/analyzer.py`, append at end of file:

```python
def build_chain_metrics(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    underlying_price: float,
) -> dict[str, float]:
    """
    Ensambla las metricas chain-level que el motor de reglas puede referenciar.

    Returns:
        dict con pc_volume_ratio, pc_oi_ratio, max_pain_strike, underlying_price,
        distance_to_max_pain, distance_to_max_pain_pct.
    """
    pc = calculate_pc_ratio(calls_df, puts_df)
    max_pain = calculate_max_pain(calls_df, puts_df)
    mp_strike = float(max_pain["strike"])

    distance = abs(underlying_price - mp_strike)
    if underlying_price and underlying_price > 0:
        distance_pct = distance / underlying_price
    else:
        distance_pct = float("inf")

    return {
        "pc_volume_ratio": pc["volume_ratio"],
        "pc_oi_ratio": pc["oi_ratio"],
        "max_pain_strike": mp_strike,
        "underlying_price": float(underlying_price),
        "distance_to_max_pain": round(distance, 4),
        "distance_to_max_pain_pct": distance_pct,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_analyzer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/analyzer.py tests/test_analyzer.py
git commit -m "feat: add build_chain_metrics for rule evaluation"
```

---

## Task 4: Rules engine

**Files:**
- Create: `src/rules.py`
- Modify: `requirements.txt` (add PyYAML)
- Test: `tests/test_rules.py`

- [ ] **Step 1: Add PyYAML dependency**

In `requirements.txt`, add after the `rich` line:

```
PyYAML>=6.0,<7.0
```

Then install: `pip install "PyYAML>=6.0,<7.0"`

- [ ] **Step 2: Write the failing tests**

Create `tests/test_rules.py`:

```python
"""Tests para src/rules.py. Sin red ni credenciales."""

import pandas as pd
import pytest

from config import ConfigError
from src.rules import Rule, Alert, load_rules, evaluate_rules


def _calls(rows: list[dict]) -> pd.DataFrame:
    base = {"no_quote": False}
    return pd.DataFrame([{**base, **r} for r in rows])


def _empty() -> pd.DataFrame:
    return pd.DataFrame()


METRICS = {
    "pc_volume_ratio": 1.8, "pc_oi_ratio": 0.9, "max_pain_strike": 100.0,
    "underlying_price": 100.0, "distance_to_max_pain": 0.4,
    "distance_to_max_pain_pct": 0.004,
}


class TestOperators:
    def test_gt_triggers(self):
        rule = Rule(name="r", scope="contract", field="iv", operator="gt", value=0.3)
        calls = _calls([{"strike": 100.0, "iv": 0.4}])
        alerts = evaluate_rules([rule], calls, _empty(), METRICS, "SPY")
        assert len(alerts) == 1
        assert isinstance(alerts[0], Alert)

    def test_lt_no_trigger(self):
        rule = Rule(name="r", scope="contract", field="iv", operator="lt", value=0.3)
        calls = _calls([{"strike": 100.0, "iv": 0.4}])
        assert evaluate_rules([rule], calls, _empty(), METRICS, "SPY") == []

    def test_between_triggers(self):
        rule = Rule(name="r", scope="contract", field="delta", operator="between", value=[0.25, 0.35])
        calls = _calls([{"strike": 100.0, "delta": 0.30}])
        assert len(evaluate_rules([rule], calls, _empty(), METRICS, "SPY")) == 1

    def test_outside_triggers(self):
        rule = Rule(name="r", scope="contract", field="delta", operator="outside", value=[0.25, 0.35])
        calls = _calls([{"strike": 100.0, "delta": 0.50}])
        assert len(evaluate_rules([rule], calls, _empty(), METRICS, "SPY")) == 1

    def test_nan_value_does_not_trigger(self):
        rule = Rule(name="r", scope="contract", field="iv", operator="gt", value=0.3)
        calls = _calls([{"strike": 100.0, "iv": float("nan")}])
        assert evaluate_rules([rule], calls, _empty(), METRICS, "SPY") == []


class TestSelectors:
    def test_no_quote_excluded(self):
        rule = Rule(name="r", scope="contract", field="iv", operator="gt", value=0.3)
        calls = pd.DataFrame([{"strike": 100.0, "iv": 0.4, "no_quote": True}])
        assert evaluate_rules([rule], calls, _empty(), METRICS, "SPY") == []

    def test_type_put_uses_puts_only(self):
        rule = Rule(name="r", scope="contract", field="iv", operator="gt", value=0.3, type="PUT")
        calls = _calls([{"strike": 100.0, "iv": 0.9}])
        puts = _calls([{"strike": 100.0, "iv": 0.4}])
        alerts = evaluate_rules([rule], calls, puts, METRICS, "SPY")
        assert len(alerts) == 1
        assert "P" in alerts[0].subject

    def test_strike_range(self):
        rule = Rule(name="r", scope="contract", field="iv", operator="gt", value=0.3,
                    strike_min=95.0, strike_max=105.0)
        calls = _calls([{"strike": 100.0, "iv": 0.4}, {"strike": 200.0, "iv": 0.4}])
        alerts = evaluate_rules([rule], calls, _empty(), METRICS, "SPY")
        assert len(alerts) == 1
        assert "100" in alerts[0].subject


class TestChainScope:
    def test_chain_rule_triggers(self):
        rule = Rule(name="pc", scope="chain", field="pc_volume_ratio", operator="gt", value=1.5)
        alerts = evaluate_rules([rule], _empty(), _empty(), METRICS, "SPY")
        assert len(alerts) == 1
        assert alerts[0].subject == "chain"

    def test_chain_rule_no_trigger(self):
        rule = Rule(name="pc", scope="chain", field="pc_oi_ratio", operator="gt", value=1.5)
        assert evaluate_rules([rule], _empty(), _empty(), METRICS, "SPY") == []


class TestLoadRules:
    def test_load_valid_yaml(self, tmp_path):
        p = tmp_path / "rules.yaml"
        p.write_text(
            "rules:\n"
            "  - name: high_iv\n"
            "    scope: contract\n"
            "    type: CALL\n"
            "    field: iv\n"
            "    operator: gt\n"
            "    value: 0.3\n"
        )
        rules = load_rules(str(p))
        assert len(rules) == 1
        assert rules[0].name == "high_iv"
        assert rules[0].type == "CALL"

    def test_load_strike_shorthand(self, tmp_path):
        p = tmp_path / "rules.yaml"
        p.write_text(
            "rules:\n"
            "  - name: r\n"
            "    scope: contract\n"
            "    field: iv\n"
            "    operator: gt\n"
            "    value: 0.3\n"
            "    strike: 100\n"
        )
        rules = load_rules(str(p))
        assert rules[0].strike_min == 100.0
        assert rules[0].strike_max == 100.0

    def test_invalid_operator_raises(self, tmp_path):
        p = tmp_path / "rules.yaml"
        p.write_text(
            "rules:\n"
            "  - name: r\n"
            "    scope: contract\n"
            "    field: iv\n"
            "    operator: bogus\n"
            "    value: 0.3\n"
        )
        with pytest.raises(ConfigError):
            load_rules(str(p))

    def test_invalid_field_raises(self, tmp_path):
        p = tmp_path / "rules.yaml"
        p.write_text(
            "rules:\n"
            "  - name: r\n"
            "    scope: contract\n"
            "    field: bogus\n"
            "    operator: gt\n"
            "    value: 0.3\n"
        )
        with pytest.raises(ConfigError):
            load_rules(str(p))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.rules'`

- [ ] **Step 4: Write the implementation**

Create `src/rules.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_rules.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/rules.py tests/test_rules.py requirements.txt
git commit -m "feat: add YAML rules engine with contract and chain scopes"
```

---

## Task 5: Alert state (edge-triggered cooldown)

**Files:**
- Create: `src/alert_state.py`
- Modify: `config.py` (add `ALERT_MIN_INTERVAL`)
- Test: `tests/test_alert_state.py`

- [ ] **Step 1: Add config constant**

In `config.py`, in the normalizacion/alertas block added in Task 1, add:

```python
ALERT_MIN_INTERVAL   = int(os.getenv("ALERT_MIN_INTERVAL", "300"))  # segundos
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_alert_state.py`:

```python
"""Tests para src/alert_state.py. Deterministas via reloj inyectado."""

from datetime import datetime, timedelta

from src.alert_state import AlertState
from src.rules import Alert


def _alert(name: str, subject: str, ts: datetime) -> Alert:
    return Alert(
        rule_name=name, symbol="SPY", scope="contract", subject=subject,
        field="iv", value=0.4, threshold=0.3, timestamp=ts, message="x",
    )


def test_first_occurrence_notifies():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    out = state.update([_alert("r", "SPY 100C", t0)], now=t0)
    assert len(out) == 1


def test_still_active_within_interval_is_suppressed():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    state.update([_alert("r", "SPY 100C", t0)], now=t0)
    out = state.update([_alert("r", "SPY 100C", t0)], now=t0 + timedelta(seconds=60))
    assert out == []


def test_still_active_after_interval_re_notifies():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    state.update([_alert("r", "SPY 100C", t0)], now=t0)
    out = state.update([_alert("r", "SPY 100C", t0)], now=t0 + timedelta(seconds=301))
    assert len(out) == 1


def test_cleared_then_reactivated_after_interval_is_fresh_edge():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    state.update([_alert("r", "SPY 100C", t0)], now=t0)
    # cleared for a full interval
    state.update([], now=t0 + timedelta(seconds=301))
    out = state.update([_alert("r", "SPY 100C", t0)], now=t0 + timedelta(seconds=400))
    assert len(out) == 1


def test_distinct_subjects_tracked_independently():
    state = AlertState(min_interval=300)
    t0 = datetime(2026, 6, 26, 10, 0, 0)
    out = state.update(
        [_alert("r", "SPY 100C", t0), _alert("r", "SPY 105C", t0)], now=t0
    )
    assert len(out) == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_alert_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.alert_state'`

- [ ] **Step 4: Write the implementation**

Create `src/alert_state.py`:

```python
"""
src/alert_state.py
Gate de cooldown edge-triggered. Evita el spam de notificar la misma condicion
en cada ciclo de polling. Una condicion dispara al activarse; se re-arma cuando
se despeja por al menos min_interval segundos.
"""

from datetime import datetime
from typing import Optional

from src.rules import Alert


class AlertState:
    def __init__(self, min_interval: float = 300.0) -> None:
        self.min_interval = min_interval
        self._last_fired: dict[tuple[str, str], datetime] = {}

    def update(self, current: list[Alert], now: Optional[datetime] = None) -> list[Alert]:
        """
        Recibe las alertas activas de este ciclo y devuelve solo las que se
        deben notificar (nuevas, o re-disparadas tras min_interval).
        """
        now = now or datetime.now()
        current_keys = {(a.rule_name, a.subject) for a in current}

        to_notify: list[Alert] = []
        for alert in current:
            key = (alert.rule_name, alert.subject)
            last = self._last_fired.get(key)
            if last is None or (now - last).total_seconds() >= self.min_interval:
                to_notify.append(alert)
                self._last_fired[key] = now

        # Re-armar: olvidar claves que llevan despejadas al menos min_interval.
        for key in list(self._last_fired):
            if key not in current_keys:
                if (now - self._last_fired[key]).total_seconds() >= self.min_interval:
                    del self._last_fired[key]

        return to_notify
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_alert_state.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/alert_state.py tests/test_alert_state.py config.py
git commit -m "feat: add edge-triggered alert cooldown state"
```

---

## Task 6: Notifiers

**Files:**
- Create: `src/notifier.py`
- Modify: `config.py` (Telegram creds + channel flags + conditional validation)
- Modify: `requirements.txt` (add windows-toasts)
- Test: `tests/test_notifier.py`

- [ ] **Step 1: Add config**

In `config.py`, in the normalizacion/alertas block, add:

```python
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "")
ALERTS_DESKTOP       = os.getenv("ALERTS_DESKTOP", "true").lower() == "true"
ALERTS_TELEGRAM      = os.getenv("ALERTS_TELEGRAM", "false").lower() == "true"
```

And append this function to `config.py`:

```python
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
```

- [ ] **Step 2: Add windows-toasts dependency**

In `requirements.txt`, add after the PyYAML line:

```
windows-toasts>=1.1.0 ; sys_platform == "win32"
```

Then install: `pip install "windows-toasts>=1.1.0"`

- [ ] **Step 3: Write the failing tests**

Create `tests/test_notifier.py`:

```python
"""Tests para src/notifier.py. requests y toast mockeados, sin red."""

from datetime import datetime

import pytest

from src.notifier import (
    TelegramNotifier, DesktopNotifier, CompositeNotifier, format_message,
)
from src.rules import Alert


def _alert() -> Alert:
    return Alert(
        rule_name="high_iv", symbol="SPY", scope="contract", subject="SPY 100C",
        field="iv", value=0.42, threshold=0.3, timestamp=datetime(2026, 6, 26, 10, 0),
        message="IV alta en SPY 100C",
    )


class _FakeResponse:
    ok = True


class _FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, data=None, timeout=None):
        self.calls.append({"url": url, "data": data})
        return _FakeResponse()


def test_format_message_includes_subject_and_value():
    msg = format_message(_alert())
    assert "SPY 100C" in msg
    assert "0.42" in msg


def test_telegram_posts_to_bot_api():
    session = _FakeSession()
    notifier = TelegramNotifier(token="TKN", chat_id="123", session=session)
    notifier.send(_alert())
    assert len(session.calls) == 1
    assert "/botTKN/sendMessage" in session.calls[0]["url"]
    assert session.calls[0]["data"]["chat_id"] == "123"
    assert "SPY 100C" in session.calls[0]["data"]["text"]


def test_telegram_swallows_network_error():
    class _BoomSession:
        def post(self, *a, **k):
            raise RuntimeError("network down")

    notifier = TelegramNotifier(token="TKN", chat_id="123", session=_BoomSession())
    # Must not raise.
    notifier.send(_alert())


def test_desktop_uses_injected_toast_fn():
    captured = {}

    def fake_toast(title, body):
        captured["title"] = title
        captured["body"] = body

    notifier = DesktopNotifier(toast_fn=fake_toast)
    notifier.send(_alert())
    assert "SPY 100C" in captured["body"]


def test_composite_continues_after_failing_notifier():
    sent = []

    class _Boom:
        def send(self, alert):
            raise RuntimeError("boom")

    class _Record:
        def send(self, alert):
            sent.append(alert)

    composite = CompositeNotifier([_Boom(), _Record()])
    composite.send(_alert())
    assert len(sent) == 1
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_notifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.notifier'`

- [ ] **Step 5: Write the implementation**

Create `src/notifier.py`:

```python
"""
src/notifier.py
Notificadores pluggables. Backends: toast de Windows y Telegram.
Un fallo de un canal nunca tumba a los demas. Nunca se loguea el token.
"""

import logging
from typing import Callable, Optional, Protocol

import requests

import config
from src.rules import Alert

log = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"


def format_message(alert: Alert) -> str:
    """Texto humano de una alerta."""
    return (
        f"[{alert.symbol}] {alert.message}\n"
        f"{alert.field}={alert.value:g} (umbral {alert.threshold})"
    )


class Notifier(Protocol):
    def send(self, alert: Alert) -> None: ...


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, session: Optional[object] = None) -> None:
        self._token = token
        self._chat_id = chat_id
        self._session = session or requests.Session()

    def send(self, alert: Alert) -> None:
        url = f"{_TELEGRAM_API}/bot{self._token}/sendMessage"
        try:
            self._session.post(
                url,
                data={"chat_id": self._chat_id, "text": format_message(alert)},
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001 - canal aislado
            log.debug("Telegram send fallo: %s", exc)


def _show_windows_toast(title: str, body: str) -> None:
    from windows_toasts import Toast, WindowsToaster  # lazy import

    toaster = WindowsToaster("Options Alert Monitor")
    toast = Toast()
    toast.text_fields = [title, body]
    toaster.show_toast(toast)


class DesktopNotifier:
    def __init__(self, toast_fn: Optional[Callable[[str, str], None]] = None) -> None:
        self._toast_fn = toast_fn or _show_windows_toast

    def send(self, alert: Alert) -> None:
        try:
            self._toast_fn(f"Alerta {alert.symbol}", format_message(alert))
        except Exception as exc:  # noqa: BLE001 - toast no disponible
            log.debug("Desktop toast fallo: %s", exc)


class CompositeNotifier:
    def __init__(self, notifiers: list) -> None:
        self._notifiers = notifiers

    def send(self, alert: Alert) -> None:
        for notifier in self._notifiers:
            try:
                notifier.send(alert)
            except Exception as exc:  # noqa: BLE001 - canal aislado
                log.debug("Notificador fallo: %s", exc)


def build_notifier_from_config() -> CompositeNotifier:
    """Construye el CompositeNotifier segun los flags de config."""
    notifiers: list = []
    if config.ALERTS_DESKTOP:
        notifiers.append(DesktopNotifier())
    if config.ALERTS_TELEGRAM:
        notifiers.append(TelegramNotifier(
            token=config.TELEGRAM_BOT_TOKEN, chat_id=config.TELEGRAM_CHAT_ID
        ))
    return CompositeNotifier(notifiers)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_notifier.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/notifier.py tests/test_notifier.py config.py requirements.txt
git commit -m "feat: add pluggable Telegram and desktop notifiers"
```

---

## Task 7: Monitor loop + market-hours helper + example rules

**Files:**
- Create: `monitor.py`
- Create: `rules.example.yaml`
- Test: `tests/test_monitor.py`

- [ ] **Step 1: Write the example rules file**

Create `rules.example.yaml`:

```yaml
# Reglas de ejemplo. Copiar a rules.yaml y ajustar.
# scope: contract (por contrato) o chain (agregado de la cadena).
# IV se expresa en fraccion decimal: 0.30 = 30%.
rules:
  - name: high_iv_calls
    scope: contract
    type: CALL
    field: iv
    operator: gt
    value: 0.30
    message: "IV de call por encima de 30%"

  - name: wide_spread
    scope: contract
    field: spread_pct
    operator: gt
    value: 0.10
    message: "Spread mayor al 10% del mid"

  - name: put_call_extreme
    scope: chain
    field: pc_volume_ratio
    operator: gt
    value: 1.5
    message: "Put/Call de volumen extremo"

  - name: near_max_pain
    scope: chain
    field: distance_to_max_pain_pct
    operator: lt
    value: 0.005
    message: "Precio a menos de 0.5% del Max Pain"
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_monitor.py`:

```python
"""Tests para monitor.run_cycle. fetch mockeado, sin red."""

from datetime import date, datetime

import pandas as pd
import pytest

import monitor
from src.rules import Rule
from src.alert_state import AlertState


class _RecordNotifier:
    def __init__(self):
        self.sent = []

    def send(self, alert):
        self.sent.append(alert)


def _fake_raw():
    return {
        "underlyingPrice": 100.0,
        "callExpDateMap": {
            "2026-07-17:21": {
                "100.0": [{
                    "bid": 1.0, "ask": 1.2, "last": 1.1, "volume": 100,
                    "openInterest": 500, "delta": 0.5, "gamma": 0.02,
                    "theta": -0.05, "vega": 0.1, "impliedVolatility": 40.0,
                    "inTheMoney": True, "expirationDate": "2026-07-17",
                }],
            }
        },
        "putExpDateMap": {},
    }


def test_run_cycle_fires_alert(monkeypatch):
    monkeypatch.setattr(monitor, "fetch_option_chain", lambda **kw: _fake_raw())
    rule = Rule(name="high_iv", scope="contract", field="iv", operator="gt", value=0.30)
    notifier = _RecordNotifier()
    state = AlertState(min_interval=300)

    out = monitor.run_cycle(
        client=None, symbol="SPY", expiration=date(2026, 7, 17),
        rules=[rule], state=state, notifier=notifier,
        contract_type="ALL", strike_count=None, iv_scale="percent",
        now=datetime(2026, 6, 26, 10, 0),
    )
    assert len(out) == 1
    assert len(notifier.sent) == 1


def test_run_cycle_survives_api_error(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("api down")

    monkeypatch.setattr(monitor, "fetch_option_chain", _boom)
    out = monitor.run_cycle(
        client=None, symbol="SPY", expiration=date(2026, 7, 17),
        rules=[], state=AlertState(), notifier=_RecordNotifier(),
        contract_type="ALL", strike_count=None, iv_scale="percent",
    )
    assert out == []


def test_is_market_hours_weekend_false():
    # 2026-06-27 is a Saturday.
    assert monitor.is_market_hours(datetime(2026, 6, 27, 12, 0)) is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_monitor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'monitor'`

- [ ] **Step 4: Write the implementation**

Create `monitor.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_monitor.py -v`
Expected: PASS

- [ ] **Step 6: Run the full suite and commit**

Run: `pytest -q`
Expected: PASS (all prior 36 tests plus the new modules green)

```bash
git add monitor.py rules.example.yaml tests/test_monitor.py
git commit -m "feat: add continuous monitor loop with market-hours guard"
```

---

## Task 8: Docs + .env.example

**Files:**
- Modify: `.env.example`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add env vars to `.env.example`**

Append to `.env.example`:

```
# -- Alertas / monitor ----------------------------------------
IV_INPUT_SCALE=percent
ALERT_MIN_INTERVAL=300
ALERTS_DESKTOP=true
ALERTS_TELEGRAM=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

(If `.env.example` does not exist, create it with the existing Schwab vars plus the block above. Check existing keys first with: `git show HEAD:.env.example` or read the file.)

- [ ] **Step 2: Document the monitor in CLAUDE.md**

In `CLAUDE.md`, under "Key Files", add:

```
- `monitor.py` — loop continuo de alertas (rules YAML, Telegram + toast)
- `src/normalizer.py` — limpieza y metricas por-contrato
- `src/rules.py` — motor de reglas declarativo (YAML)
- `src/alert_state.py` — cooldown edge-triggered
- `src/notifier.py` — notificadores Telegram / desktop
```

And add a "Monitor" subsection under "Quick Start":

```
- `python monitor.py --symbol SPY --expiration 2026-07-17 --rules rules.yaml`
- Copiar `rules.example.yaml` a `rules.yaml` y ajustar umbrales
- IV en reglas se expresa en decimal (0.30 = 30%)
```

- [ ] **Step 3: Commit**

```bash
git add .env.example CLAUDE.md
git commit -m "docs: document alert monitor config and usage"
```

---

## Verification (end of plan)

- [ ] Run full suite: `pytest -q` — all green.
- [ ] Run coverage: `pytest --cov=src --cov=. --cov-report=term-missing` — confirm >= 85%.
- [ ] Smoke-load rules: `python -c "from src.rules import load_rules; print(len(load_rules('rules.example.yaml')))"` — prints `4`.
- [ ] **Open question to revisit with real API data:** confirm Schwab's actual IV field name (`volatility` vs `impliedVolatility`) and scale (percent vs decimal); adjust `_FIELD_ALIASES` / `IV_INPUT_SCALE` default in `src/normalizer.py` / `config.py` if needed. The alias map and config make this a one-line change.
