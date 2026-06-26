# Changelog — Options Chain Fetcher

## Alert Monitor + Portfolio Readiness (2026-06)

### Nuevo: Monitor de alertas (`monitor.py`)
- Loop continuo de polling sobre la option chain con intervalo configurable.
- Motor de reglas declarativo en YAML (`src/rules.py`): reglas por contrato
  (IV, spread, delta, moneyness...) y por cadena (P/C ratio, distancia a Max Pain).
- Capa de normalizacion (`src/normalizer.py`): canonicaliza nombres de campo,
  limpia centinelas (-999/inf), marca contratos sin cotizacion y deriva
  mid / spread_pct / moneyness; estandariza la escala de IV.
- Cooldown edge-triggered (`src/alert_state.py`): no spamea la misma alerta cada ciclo.
- Notificadores pluggables (`src/notifier.py`): Telegram + toast de Windows,
  con aislamiento de fallos por canal. El token nunca se loguea.
- `build_chain_metrics` en `src/analyzer.py` para metricas a nivel de cadena.

### Nuevo: Modo demo sin credenciales
- `python main.py --demo` y `python monitor.py --demo` ejecutan el pipeline
  completo contra `examples/sample_chain.json`, sin Schwab API ni OAuth.

### Portfolio / infraestructura
- `LICENSE` MIT agregada (el badge del README apuntaba a un archivo inexistente).
- `tzdata` agregado a requirements en Windows (ZoneInfo del monitor lo requiere).
- CI mide cobertura de `monitor.py`.
- Suite ampliada a 157 tests.

## Audit History (5 rounds)

### Round 1 — Code Review (8 fixes)
- Early validate_config() in main, single client creation, try/except with ASCII messages
- Client injection via client= parameter in fetcher
- Non-mutating parser ({**contract, ...} instead of modifying dict)
- Robust ITM detection (string comparison with .lower())
- TOKEN_PATH anchored to project root via __file__
- "spread" added to CALLS_COLUMNS after "ask"

### Round 2 — Code Quality (15 fixes)
- ConfigError custom exception (replaces EnvironmentError)
- PUTS_COLUMNS = list(CALLS_COLUMNS) (independent copy, not alias)
- NUMERIC_COLUMNS centralized in config.py
- Dead import pickle removed from auth.py
- Token corruption recovery with try/except and file deletion
- contract_type validation before getattr
- Empty option maps raise RuntimeError with helpful message
- Type hints on fetcher (client, return type) and exporter (Worksheet)
- INFO_HEADER_COLOR constant, _write_sheet helper to eliminate duplication
- Docstrings with Args/Returns/Raises sections
- Windows encoding auto-fix (sys.stdout.reconfigure)

### Round 3 — Security Audit (7 fixes)
- CVEs patched: requests>=2.33.0, cryptography>=46.0.6, setuptools>=78.1.1
- Path traversal blocked: _validate_symbol() with regex [A-Za-z0-9.]{1,10}
- Error sanitization: response.text removed from user-facing errors
- Token permissions: chmod(0o600) after OAuth flow
- Exception sanitization: str(e) removed from user-facing token warnings
- SSL warning documented for OAuth
- requirements.txt: all deps pinned with upper bounds

### Round 4 — Test Coverage (73% -> 85%)
- test_auth.py: Token corruption triggers reauth + valid token skips login
- test_config.py: ConfigError raised correctly, regression test vs EnvironmentError
- test_fetcher.py: strike_count passed/omitted, symbol uppercased
- test_parser.py: MOCK_RAW converted to fixture, concrete sort values, spread position
- test_security.py: 10 tests for path traversal, special chars, null bytes, length

### Round 5 — Improvement Plan (generated, not yet applied)
See Roadmap section in project documentation.
