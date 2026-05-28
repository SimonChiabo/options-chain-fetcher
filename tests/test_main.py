"""
tests/test_main.py
Tests para main.py. Valida CLI parsing y flujos principales.
"""

import argparse
from datetime import date
from unittest.mock import MagicMock, patch, call
from pathlib import Path

import pandas as pd
import pytest

from main import _validate_symbol, parse_args, main
from config import ConfigError


class TestValidateSymbol:
    """Tests para _validate_symbol."""

    def test_valid_symbols(self):
        """Simbolos validos deben pasarse sin error."""
        assert _validate_symbol("SPY") == "SPY"
        assert _validate_symbol("spy") == "SPY"
        assert _validate_symbol("AAPL") == "AAPL"
        assert _validate_symbol("BRK.A") == "BRK.A"
        assert _validate_symbol("QQQ") == "QQQ"

    def test_lowercase_conversion(self):
        """Simbolos en minusculas deben convertirse a mayusculas."""
        assert _validate_symbol("spy") == "SPY"
        assert _validate_symbol("aapl") == "AAPL"

    def test_mixed_case_conversion(self):
        """Simbolos en mixto deben convertirse a mayusculas."""
        assert _validate_symbol("SpY") == "SPY"

    def test_symbol_with_dot(self):
        """Simbolos con punto (like BRK.A) son validos."""
        assert _validate_symbol("BRK.A") == "BRK.A"

    def test_symbol_with_numbers(self):
        """Simbolos con numeros son validos."""
        assert _validate_symbol("SPY1") == "SPY1"

    def test_invalid_empty_symbol(self):
        """Simbolo vacio debe fallar."""
        with pytest.raises(ValueError, match="invalido"):
            _validate_symbol("")

    def test_invalid_special_chars(self):
        """Simbolos con caracteres especiales deben fallar."""
        with pytest.raises(ValueError, match="invalido"):
            _validate_symbol("SPY!")

    def test_invalid_long_symbol(self):
        """Simbolos mayores a 10 caracteres deben fallar."""
        with pytest.raises(ValueError, match="invalido"):
            _validate_symbol("AAAABBBBCCCC")


class TestParseArgs:
    """Tests para parse_args()."""

    def test_parse_args_with_single_expiration(self):
        """--expiration debe parsearse correctamente."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20"]):
            args = parse_args()
            assert args.symbol == "SPY"
            assert args.expiration == date(2025, 6, 20)
            assert args.expirations is None

    def test_parse_args_with_multiple_expirations(self):
        """--expirations debe parsearse correctamente."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-E", "2025-06-20,2025-07-18"]):
            args = parse_args()
            assert args.symbol == "SPY"
            assert args.expirations == [date(2025, 6, 20), date(2025, 7, 18)]
            assert args.expiration is None

    def test_parse_args_with_spaces_in_expirations(self):
        """--expirations debe manejar espacios alrededor de comas."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-E", "2025-06-20 , 2025-07-18"]):
            args = parse_args()
            assert len(args.expirations) == 2
            assert args.expirations[0] == date(2025, 6, 20)
            assert args.expirations[1] == date(2025, 7, 18)

    def test_parse_args_with_strikes(self):
        """--strikes debe parsearse correctamente."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20", "-k", "10"]):
            args = parse_args()
            assert args.strikes == 10

    def test_parse_args_with_type_all(self):
        """--type ALL debe ser valido."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20", "-t", "ALL"]):
            args = parse_args()
            assert args.type == "ALL"

    def test_parse_args_with_type_call(self):
        """--type CALL debe ser valido."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20", "-t", "CALL"]):
            args = parse_args()
            assert args.type == "CALL"

    def test_parse_args_with_type_put(self):
        """--type PUT debe ser valido."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20", "-t", "PUT"]):
            args = parse_args()
            assert args.type == "PUT"

    def test_parse_args_type_default(self):
        """--type debe tener default ALL."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20"]):
            args = parse_args()
            assert args.type == "ALL"

    def test_parse_args_no_symbol_fails(self):
        """Falta de --symbol debe fallar."""
        with patch("sys.argv", ["main.py"]):
            with pytest.raises(SystemExit):
                parse_args()

    def test_parse_args_both_expiration_and_expirations(self):
        """Se puede especificar ambos --expiration y --expirations."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20", "-E", "2025-07-18"]):
            args = parse_args()
            assert args.expiration == date(2025, 6, 20)
            assert args.expirations == [date(2025, 7, 18)]

    def test_parse_args_neither_expiration_nor_expirations(self):
        """Sin --expiration ni --expirations es permitido (error sera en main)."""
        with patch("sys.argv", ["main.py", "-s", "SPY"]):
            args = parse_args()
            assert args.expiration is None
            assert args.expirations is None

    def test_parse_args_long_form_symbol(self):
        """--symbol debe aceptar forma larga."""
        with patch("sys.argv", ["main.py", "--symbol", "SPY", "--expiration", "2025-06-20"]):
            args = parse_args()
            assert args.symbol == "SPY"

    def test_parse_args_long_form_expirations(self):
        """--expirations debe aceptar forma larga."""
        with patch("sys.argv", ["main.py", "-s", "SPY", "--expirations", "2025-06-20,2025-07-18"]):
            args = parse_args()
            assert args.expirations == [date(2025, 6, 20), date(2025, 7, 18)]


class TestMainFunction:
    """Tests para main()."""

    def _mock_client(self):
        """Crea un mock client basico."""
        return MagicMock()

    def _mock_calls_df(self):
        """DataFrame minimo de calls."""
        return pd.DataFrame({
            "strike": [500.0, 505.0],
            "bid": [1.0, 0.8],
            "ask": [1.2, 1.0],
            "inTheMoney": [False, False],
        })

    def _mock_puts_df(self):
        """DataFrame minimo de puts."""
        return pd.DataFrame({
            "strike": [500.0, 505.0],
            "bid": [0.5, 0.6],
            "ask": [0.7, 0.8],
            "inTheMoney": [False, False],
        })

    @patch("main.get_client")
    @patch("main.export_to_excel")
    @patch("main.parse_option_chain")
    @patch("main.fetch_option_chain")
    @patch("config.validate_config")
    def test_main_single_expiration_flow(
        self, mock_validate, mock_fetch, mock_parse, mock_export, mock_get_client
    ):
        """main() debe ejecutar flujo single expiration correctamente."""
        mock_get_client.return_value = self._mock_client()
        mock_fetch.return_value = {"some": "data"}
        mock_parse.return_value = (self._mock_calls_df(), self._mock_puts_df())
        mock_export.return_value = Path("/tmp/test.xlsx")

        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20"]):
            with patch("main.calculate_max_pain") as mock_pain, \
                 patch("main.calculate_pc_ratio") as mock_ratio:
                mock_pain.return_value = {"strike": 500.0, "pain_by_strike": {}}
                mock_ratio.return_value = {"volume_ratio": 1.0, "oi_ratio": 1.0}
                main()

        mock_validate.assert_called_once()
        mock_get_client.assert_called_once()
        mock_fetch.assert_called_once()
        mock_parse.assert_called_once()
        mock_export.assert_called_once()

    @patch("main.get_client")
    @patch("main.export_multiple_to_excel")
    @patch("main.calculate_iv_skew")
    @patch("main.parse_option_chain")
    @patch("main.fetch_multiple_expirations")
    @patch("config.validate_config")
    def test_main_multiple_expirations_flow(
        self, mock_validate, mock_fetch_multi, mock_parse, mock_skew, mock_export_multi, mock_get_client
    ):
        """main() debe ejecutar flujo multi expirations correctamente."""
        mock_get_client.return_value = self._mock_client()
        mock_fetch_multi.return_value = {
            date(2025, 6, 20): {"data": "call1"},
            date(2025, 7, 18): {"data": "call2"},
        }
        calls_df = self._mock_calls_df()
        puts_df = self._mock_puts_df()
        mock_parse.side_effect = lambda raw, exp: (calls_df, puts_df)
        mock_skew.return_value = pd.DataFrame({"strike": [500.0]})
        mock_export_multi.return_value = Path("/tmp/test.xlsx")

        with patch("sys.argv", ["main.py", "-s", "SPY", "-E", "2025-06-20,2025-07-18"]):
            main()

        mock_validate.assert_called_once()
        mock_get_client.assert_called_once()
        mock_fetch_multi.assert_called_once()
        mock_skew.assert_called_once()
        mock_export_multi.assert_called_once()

    @patch("main.get_client")
    @patch("config.validate_config")
    def test_main_missing_expiration_and_expirations(self, mock_validate, mock_get_client):
        """main() debe fallar si no se especifica ni --expiration ni --expirations."""
        with patch("sys.argv", ["main.py", "-s", "SPY"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("config.validate_config")
    def test_main_config_error_handling(self, mock_validate):
        """main() debe manejar ConfigError correctamente."""
        mock_validate.side_effect = ConfigError("Test error")

        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("config.validate_config")
    def test_main_value_error_handling(self, mock_validate):
        """main() debe manejar ValueError (simbolo invalido)."""
        with patch("sys.argv", ["main.py", "-s", "INVALID!", "-e", "2025-06-20"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("main.get_client")
    @patch("main.export_to_excel")
    @patch("main.parse_option_chain")
    @patch("main.fetch_option_chain")
    @patch("config.validate_config")
    def test_main_runtime_error_handling(
        self, mock_validate, mock_fetch, mock_parse, mock_export, mock_get_client
    ):
        """main() debe manejar RuntimeError (API error)."""
        mock_get_client.return_value = self._mock_client()
        mock_fetch.side_effect = RuntimeError("API Error")

        with patch("sys.argv", ["main.py", "-s", "SPY", "-e", "2025-06-20"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("main.get_client")
    @patch("main.export_to_excel")
    @patch("main.parse_option_chain")
    @patch("main.fetch_option_chain")
    @patch("config.validate_config")
    def test_main_passes_correct_parameters_to_fetch(
        self, mock_validate, mock_fetch, mock_parse, mock_export, mock_get_client
    ):
        """main() debe pasar parametros correctos a fetch_option_chain."""
        mock_get_client.return_value = self._mock_client()
        mock_fetch.return_value = {"some": "data"}
        mock_parse.return_value = (self._mock_calls_df(), self._mock_puts_df())
        mock_export.return_value = Path("/tmp/test.xlsx")

        with patch("sys.argv", ["main.py", "-s", "QQQ", "-e", "2025-07-18", "-t", "CALL", "-k", "15"]):
            with patch("main.calculate_max_pain") as mock_pain, \
                 patch("main.calculate_pc_ratio") as mock_ratio:
                mock_pain.return_value = {"strike": 400.0, "pain_by_strike": {}}
                mock_ratio.return_value = {"volume_ratio": 1.0, "oi_ratio": 1.0}
                main()

        # Verificar que fetch_option_chain fue llamado con los parametros correctos
        call_kwargs = mock_fetch.call_args[1]
        assert call_kwargs["symbol"] == "QQQ"
        assert call_kwargs["expiration"] == date(2025, 7, 18)
        assert call_kwargs["contract_type"] == "CALL"
        assert call_kwargs["strike_count"] == 15
