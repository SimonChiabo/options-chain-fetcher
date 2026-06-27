# AGENTS.md — Options Chain Fetcher

Instrucciones para agentes de IA (Claude Code, Cursor, Codex, Aider, Gemini
CLI, etc.) que trabajen en este repositorio. Es la fuente de verdad unica;
`CLAUDE.md` apunta aqui.

> Si sos una persona (no un agente) que quiere instalar o usar el proyecto,
> mira el `README.md`: ahi esta el paso a paso de instalacion y uso.

## Project Overview
CLI Python que descarga cadenas de opciones de Schwab API y exporta a Excel,
mas un monitor de alertas continuo. Proyecto auditado (5 rondas, suite pytest,
>=85% coverage).

## Quick Start
- `source .venv/Scripts/activate` (Git Bash en Windows)
- `pip install -r requirements.txt`
- `python main.py --symbol SPY --expiration 2025-06-20`
- Modo sin credenciales para probar: `python main.py --demo`

## Monitor de Alertas
- `python monitor.py --symbol SPY --expiration 2026-07-17 --rules rules.yaml`
- Copiar `rules.example.yaml` a `rules.yaml` y ajustar umbrales
- IV en reglas se expresa en decimal (0.30 = 30%)
- Canales: toast de Windows + Telegram (configurar en .env)
- Modo demo: `python monitor.py --demo`

## Key Files
- `main.py` — entry point CLI, validacion de simbolo, encoding fix Windows
- `monitor.py` — loop continuo de alertas (rules YAML, Telegram + toast)
- `config.py` — config central, lee .env, ConfigError custom
- `src/auth.py` — OAuth2 Schwab con token recovery
- `src/fetcher.py` — API calls con validacion de inputs
- `src/parser.py` — JSON -> DataFrames con spread column
- `src/normalizer.py` — limpieza y metricas por-contrato
- `src/analyzer.py` — max pain, P/C ratio, IV skew, chain metrics
- `src/rules.py` — motor de reglas declarativo (YAML)
- `src/alert_state.py` — cooldown edge-triggered
- `src/notifier.py` — notificadores Telegram / desktop
- `src/exporter.py` — Excel con sheets CALLS/PUTS/INFO, ITM highlighting
- `tests/` — suite pytest (parser, exporter, fetcher, auth, config, security,
  normalizer, analyzer, rules, alert_state, notifier, monitor, demo)

## CLI Parameters
- `--symbol / -s` (required): Ticker, validado con regex [A-Za-z0-9.]{1,10}
- `--expiration / -e` (required): Fecha YYYY-MM-DD
- `--strikes / -k` (optional): Strikes cada lado de ATM
- `--type / -t` (optional): ALL, CALL, o PUT (default: ALL)
- `--demo` (optional): corre con datos de ejemplo, sin credenciales

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
- Tests: usar el interprete del venv (`.venv/Scripts/python.exe -m pytest`);
  el Python del sistema no tiene schwab-py ni openpyxl

## Dependencies
Pinned con rangos y CVE minimums en requirements.txt.
schwab-py, pandas, openpyxl, python-dotenv, requests, cryptography, setuptools,
tzdata.
