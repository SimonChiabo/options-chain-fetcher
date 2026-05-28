# Options Chain Fetcher

[![Tests](https://github.com/simonchiabo/options-chain-fetcher/actions/workflows/tests.yml/badge.svg)](https://github.com/simonchiabo/options-chain-fetcher/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CLI que descarga options chains desde la **Schwab API** y las exporta a Excel con formato, Greeks, Max Pain y P/C Ratio.

## Features

- Greeks completos (Delta, Gamma, Theta, Vega) exportados directamente
- **Max Pain** calculado automaticamente desde el Open Interest
- **Put/Call Ratio** por volumen y por OI con interpretacion de sentimiento
- **Breakeven** calculado para cada contrato (strike +/- midpoint)
- Excel con sheets CALLS / PUTS / ANALYSIS / INFO y filas ITM destacadas en verde
- Output en terminal con tabla rich y colores

## Instalacion

```bash
git clone https://github.com/simonchiabo/options-chain-fetcher.git
cd options-chain-fetcher
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env            # completar con tus credenciales Schwab
```

## Uso

```bash
# Cadena completa para SPY vencimiento 2025-06-20
python main.py --symbol SPY --expiration 2025-06-20

# Solo calls, 10 strikes alrededor del ATM
python main.py -s QQQ -e 2025-07-18 -k 10 -t CALL

# Multiples vencimientos con IV Skew
python main.py -s SPY -E "2025-06-20,2025-07-18,2025-08-15"
```

## Output

```
[*] Descargando option chain: SPY | Vencimiento: 2025-06-20

  Metrica                   Valor
  Calls encontradas         247
  Puts encontradas          247
  Max Pain Strike           $585.00
  P/C Ratio (Volumen)       1.23
  P/C Ratio (OI)            0.98

[OK] Excel generado: output/SPY_20250620_options.xlsx
```

El Excel contiene:
| Sheet | Contenido |
|---|---|
| **CALLS** | Cadena de calls con Greeks, breakeven, spread, ITM destacado |
| **PUTS** | Cadena de puts con la misma estructura |
| **ANALYSIS** | Max Pain, P/C Ratio (Vol y OI), totales |
| **INFO** | Metadatos: simbolo, fecha, hora de descarga, fuente |

## Configuracion (.env)

```
SCHWAB_CLIENT_ID=tu_app_key
SCHWAB_CLIENT_SECRET=tu_app_secret
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182
OUTPUT_DIR=output
```

Ver `docs/schwab_setup.md` para crear la app en el portal de Schwab.

## Tests

```bash
python -m pytest --cov=src --cov=main --cov=config -q
```

53+ tests, 86%+ coverage. Sin mocks de BD: todos los tests usan datos locales.

## Estructura

```
options-chain-fetcher/
  main.py          # CLI entry point
  config.py        # Variables de entorno y constantes
  src/
    auth.py        # OAuth2 con schwab-py
    fetcher.py     # GET /marketdata/v1/chains
    parser.py      # JSON -> DataFrames + breakeven
    analyzer.py    # Max Pain, P/C Ratio, IV Skew
    exporter.py    # DataFrames -> Excel formateado
  tests/           # 53+ tests con pytest
```
