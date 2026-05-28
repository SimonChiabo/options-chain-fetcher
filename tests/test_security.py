"""
tests/test_security.py
Tests de seguridad: validacion de inputs, path traversal, caracteres especiales.
"""

import sys
import pytest

from main import _validate_symbol, parse_args


class TestValidateSymbol:

    def test_valid_symbols(self):
        assert _validate_symbol("SPY") == "SPY"
        assert _validate_symbol("qqq") == "QQQ"
        assert _validate_symbol("BRK.B") == "BRK.B"
        assert _validate_symbol("A") == "A"

    def test_path_traversal_blocked(self):
        with pytest.raises(ValueError, match="Simbolo invalido"):
            _validate_symbol("../../../etc/passwd")

    def test_special_characters_blocked(self):
        with pytest.raises(ValueError, match="Simbolo invalido"):
            _validate_symbol("SPY;rm -rf /")

    def test_empty_symbol_blocked(self):
        with pytest.raises(ValueError, match="Simbolo invalido"):
            _validate_symbol("")

    def test_too_long_symbol_blocked(self):
        with pytest.raises(ValueError, match="Simbolo invalido"):
            _validate_symbol("ABCDEFGHIJK")  # 11 chars

    def test_null_byte_blocked(self):
        with pytest.raises(ValueError, match="Simbolo invalido"):
            _validate_symbol("SPY\x00evil")

    def test_spaces_blocked(self):
        with pytest.raises(ValueError, match="Simbolo invalido"):
            _validate_symbol("S P Y")

    def test_uppercase_conversion(self):
        assert _validate_symbol("spy") == "SPY"
        assert _validate_symbol("Qqq") == "QQQ"

    def test_max_length_boundary(self):
        assert _validate_symbol("ABCDEFGHIJ") == "ABCDEFGHIJ"  # 10 chars: OK

    def test_slash_blocked(self):
        with pytest.raises(ValueError, match="Simbolo invalido"):
            _validate_symbol("SPY/PUT")


class TestParseArgs:
    def test_required_args_parsed(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--symbol", "SPY", "--expiration", "2025-06-20"])
        args = parse_args()
        assert args.symbol == "SPY"
        assert str(args.expiration) == "2025-06-20"

    def test_optional_args_defaults(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "--symbol", "SPY", "--expiration", "2025-06-20"])
        args = parse_args()
        assert args.strikes is None
        assert args.type == "ALL"

    def test_strikes_and_type_parsed(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py", "-s", "QQQ", "-e", "2025-07-18", "-k", "10", "-t", "CALL"])
        args = parse_args()
        assert args.strikes == 10
        assert args.type == "CALL"
