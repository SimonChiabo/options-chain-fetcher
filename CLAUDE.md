# CLAUDE.md — Options Chain Fetcher

## Project Overview
CLI Python que descarga cadenas de opciones de Schwab API y exporta a Excel.
Proyecto auditado (5 rondas, 36 tests, 85% coverage).

## Quick Start
- `source .venv/Scripts/activate` (Git Bash en Windows)
- `pip install -r requirements.txt`
- `python main.py --symbol SPY --expiration 2025-06-20`

## Key Files
- `main.py` — entry point CLI, validacion de simbolo, encoding fix Windows
- `config.py` — config central, lee .env, ConfigError custom
- `src/auth.py` — OAuth2 Schwab con token recovery
- `src/fetcher.py` — API calls con validacion de inputs
- `src/parser.py` — JSON -> DataFrames con spread column
- `src/exporter.py` — Excel con sheets CALLS/PUTS/INFO, ITM highlighting
- `tests/` — 36 tests (parser, exporter, fetcher, auth, config, security)

## CLI Parameters
- `--symbol / -s` (required): Ticker, validado con regex [A-Za-z0-9.]{1,10}
- `--expiration / -e` (required): Fecha YYYY-MM-DD
- `--strikes / -k` (optional): Strikes cada lado de ATM
- `--type / -t` (optional): ALL, CALL, o PUT (default: ALL)

## Current State
Post-auditoria, funcional. Todos los commits pusheados a origin/main.
OAuth pendiente de configurar en maquina del colaborador.

## Code Rules
- Type hints en todas las funciones nuevas
- Tests para todo codigo nuevo (mantener >=85% coverage)
- Errores al usuario NUNCA incluyen response.text ni contenido de token
- ConfigError para validacion de config (no EnvironmentError)
- No emojis ni tildes en source Python (Windows cp1252)
- log.debug() para diagnostico sensible
- Commits: conventional commits (feat:, fix:, docs:, test:, chore:)

## Environment
- OS: Windows, Terminal: Git Bash, IDE: VS Code
- .venv activar con: source .venv/Scripts/activate
- Schwab redirect URI DEBE incluir :8182
- Token refresh expira cada 7 dias
- SSL warning durante OAuth es normal (self-signed cert)

## Dependencies
Pinned con rangos y CVE minimums en requirements.txt.
schwab-py, pandas, openpyxl, python-dotenv, requests, cryptography, setuptools.
