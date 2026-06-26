"""
tests/test_demo.py
Tests for --demo mode (credential-free demo path).

Covers:
- examples/sample_chain.json structure and parsing
- main.run_demo() produces Excel without credentials
- monitor.run_demo() fires alerts without credentials
"""

import json
from datetime import date
from pathlib import Path

import pytest

from src.parser import parse_option_chain
import config


SAMPLE_PATH = Path(__file__).parent.parent / "examples" / "sample_chain.json"


# ---------------------------------------------------------------------------
# Sample JSON structure tests
# ---------------------------------------------------------------------------

class TestSampleChainJson:
    """The bundled sample JSON exists, is well-formed, and parseable."""

    def test_sample_file_exists(self) -> None:
        assert SAMPLE_PATH.exists(), f"Missing: {SAMPLE_PATH}"

    def test_sample_has_required_top_level_keys(self) -> None:
        with open(SAMPLE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        assert "underlyingPrice" in raw
        assert "callExpDateMap" in raw
        assert "putExpDateMap" in raw

    def test_sample_underlying_price_near_581(self) -> None:
        with open(SAMPLE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        assert abs(raw["underlyingPrice"] - 581.0) < 1.0

    def test_sample_parses_to_non_empty_calls(self) -> None:
        with open(SAMPLE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        calls_df, _ = parse_option_chain(raw, date(2025, 6, 20))
        assert not calls_df.empty

    def test_sample_parses_to_non_empty_puts(self) -> None:
        with open(SAMPLE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _, puts_df = parse_option_chain(raw, date(2025, 6, 20))
        assert not puts_df.empty

    def test_sample_put_volume_exceeds_call_volume_by_1_5x(self) -> None:
        with open(SAMPLE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        calls_df, puts_df = parse_option_chain(raw, date(2025, 6, 20))
        call_vol = calls_df["volume"].sum()
        put_vol = puts_df["volume"].sum()
        assert put_vol / call_vol > 1.5, (
            f"Put/Call volume ratio must be > 1.5, got {put_vol/call_vol:.2f}"
        )

    def test_sample_has_calls_with_high_iv(self) -> None:
        """At least 2 call strikes must have impliedVolatility > 30.0 (percent scale)."""
        with open(SAMPLE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        calls_df, _ = parse_option_chain(raw, date(2025, 6, 20))
        high_iv = calls_df[calls_df["impliedVolatility"] > 30.0]
        assert len(high_iv) >= 2, (
            f"Expected >= 2 calls with IV > 30, got {len(high_iv)}"
        )


# ---------------------------------------------------------------------------
# main.run_demo() tests
# ---------------------------------------------------------------------------

class TestMainRunDemo:
    """main.run_demo() produces Excel without calling get_client or needing credentials."""

    def test_run_demo_produces_excel_file(self, tmp_path, monkeypatch) -> None:
        import main as main_module

        monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))

        def _boom(*a, **kw):
            raise AssertionError("get_client must NOT be called in demo mode")

        monkeypatch.setattr(main_module, "get_client", _boom)

        main_module.run_demo()

        excel_files = list(tmp_path.glob("*.xlsx"))
        assert len(excel_files) == 1, f"Expected 1 xlsx, got: {excel_files}"

    def test_run_demo_excel_named_correctly(self, tmp_path, monkeypatch) -> None:
        import main as main_module

        monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
        monkeypatch.setattr(main_module, "get_client", lambda: (_ for _ in ()).throw(
            AssertionError("get_client called")))

        main_module.run_demo()

        expected = tmp_path / "SPY_20250620_options.xlsx"
        assert expected.exists(), f"Expected {expected}"

    def test_run_demo_works_without_schwab_env_vars(self, tmp_path, monkeypatch) -> None:
        import main as main_module

        monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
        monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
        monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)

        # Should complete without raising ConfigError
        main_module.run_demo()


# ---------------------------------------------------------------------------
# monitor.run_demo() tests
# ---------------------------------------------------------------------------

class TestMonitorRunDemo:
    """monitor.run_demo() fires alerts without calling get_client or needing credentials."""

    def test_run_demo_returns_non_empty_alerts(self, monkeypatch) -> None:
        import monitor as monitor_module

        def _boom(*a, **kw):
            raise AssertionError("get_client must NOT be called in demo mode")

        monkeypatch.setattr(monitor_module, "get_client", _boom)

        alerts = monitor_module.run_demo()
        assert len(alerts) > 0, "At least one alert must fire in demo mode"

    def test_run_demo_never_calls_get_client(self, monkeypatch) -> None:
        import monitor as monitor_module

        calls_recorded = []
        monkeypatch.setattr(monitor_module, "get_client", lambda: calls_recorded.append(1) or None)

        monitor_module.run_demo()

        assert calls_recorded == [], "get_client was unexpectedly called"
