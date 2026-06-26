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

    def test_invalid_type_raises(self, tmp_path):
        p = tmp_path / "rules.yaml"
        p.write_text(
            "rules:\n"
            "  - name: r\n"
            "    scope: contract\n"
            "    type: PUTS\n"
            "    field: iv\n"
            "    operator: gt\n"
            "    value: 0.3\n"
        )
        with pytest.raises(ConfigError):
            load_rules(str(p))
