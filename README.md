# Options Chain Fetcher

Herramienta Python para obtener cadenas de opciones (puts & calls) en tiempo real desde la **Schwab API** (ex TD Ameritrade) y exportarlas a Excel para analisis financiero profesional.

---

## Objetivo

Proveer a un analista financiero una hoja Excel actualizable con:
- Cadena completa de opciones (calls y puts) por subyacente
- Filtro por vencimiento
- Precios **bid / ask** por strike
- Greeks (delta, gamma, theta, vega)
- Volumen y Open Interest

---

## Arquitectura

```
Schwab API (OAuth2)
       |
  Python Script
  (auth + fetch + parse)
       |
   Excel (.xlsx)
   |-- Sheet: CALLS
   |-- Sheet: PUTS
   +-- Sheet: SUMMARY
       |
  Excel Power Query
  (auto-refresh con VBA)
```

---

## Estructura del proyecto

```
options-chain-fetcher/
├── src/
│   ├── __init__.py
│   ├── auth.py          # OAuth2 con Schwab API
│   ├── fetcher.py       # Llamadas a la API (option chains)
│   ├── parser.py        # Transformacion de datos a DataFrame
│   └── exporter.py      # Exportacion a .xlsx
├── tests/
│   ├── __init__.py
│   ├── test_fetcher.py
│   └── test_parser.py
├── docs/
│   └── schwab_setup.md  # Guia para configurar credenciales
├── output/              # Archivos .xlsx generados (gitignored)
├── main.py              # Entry point
├── config.py            # Configuracion general
├── requirements.txt
├── .env.example         # Template de variables de entorno
├── .gitignore
└── README.md
```

---

## Instalacion

### Prerequisitos

- Python 3.10 o superior
- Git
- Cuenta en [developer.schwab.com](https://developer.schwab.com) con app registrada (ver seccion Credenciales)

### Paso a paso

```bash
# 1. Clonar el repositorio
git clone https://github.com/SimonChiabo/options-chain-fetcher.git
cd options-chain-fetcher

# 2. Crear entorno virtual
python -m venv .venv
```

### Activar el entorno virtual

El comando para activar el entorno virtual depende de tu terminal:

| Terminal | Comando |
|---|---|
| Git Bash (Windows) | `source .venv/Scripts/activate` |
| PowerShell (Windows) | `.venv\Scripts\Activate.ps1` |
| CMD (Windows) | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

Sabras que esta activo cuando veas `(.venv)` al inicio de la linea.

```bash
# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar credenciales
cp .env.example .env
# --> Editar .env con tus credenciales de Schwab (ver seccion Credenciales)
```

---

## Uso

### Comando basico

En **Git Bash (Windows)**, usar el prefijo de encoding:

```bash
PYTHONIOENCODING=utf-8 python main.py --symbol SPY --expiration 2025-06-20
```

En **macOS / Linux / PowerShell**:

```bash
python main.py --symbol SPY --expiration 2025-06-20
```

### Parametros disponibles

| Parametro | Requerido | Descripcion | Ejemplo |
|---|---|---|---|
| `--symbol` / `-s` | Si | Ticker del subyacente | `SPY`, `QQQ`, `AAPL` |
| `--expiration` / `-e` | Si | Fecha de vencimiento (YYYY-MM-DD) | `2025-06-20` |
| `--strikes` / `-k` | No | Cantidad de strikes a cada lado del ATM | `20` |
| `--type` / `-t` | No | Tipo de contrato: ALL, CALL o PUT | `ALL` |

### Salida

El comando genera `output/{SYMBOL}_{YYYYMMDD}_options.xlsx` con tres sheets:
- **CALLS** - Cadena de calls con bid/ask, volume, OI, Greeks
- **PUTS** - Cadena de puts con bid/ask, volume, OI, Greeks
- **SUMMARY** - Metricas clave (IV media, P/C Ratio, dias al vencimiento)

---

## Primera autenticacion

La primera vez que corras el script:

1. Se abre el navegador con la pagina de login de Schwab
2. Inicia sesion con tu **cuenta de trading** de Schwab (no la de developer)
3. El navegador muestra una **advertencia de certificado SSL** - esto es normal y seguro. Haz clic en "Avanzado" > "Continuar al sitio"
4. El token se guarda automaticamente en `token.pickle`
5. Las siguientes ejecuciones reusan el token (se refresca automaticamente)

**Nota:** El refresh token expira cada 7 dias. Cuando eso ocurra, elimina `token.pickle` y vuelve a autenticarte.

---

## Credenciales Schwab

Ver guia completa en [`docs/schwab_setup.md`](docs/schwab_setup.md).

En resumen:
1. Crear cuenta de desarrollador en [developer.schwab.com](https://developer.schwab.com) (separada de la cuenta de trading)
2. Registrar una nueva app con estos datos:
   - **App Name:** `options-chain-fetcher`
   - **Callback URL:** `https://127.0.0.1:8182` (con puerto, obligatorio)
   - **API Product:** Market Data Production
3. Obtener `Client ID` (App Key) y `Client Secret`
4. Esperar a que el status de la app sea **Active/Approved**
5. Copiar credenciales al archivo `.env`

**IMPORTANTE:** La Callback URL en el portal y `SCHWAB_REDIRECT_URI` en `.env` deben coincidir exactamente: `https://127.0.0.1:8182`

---

## Dependencias principales

| Paquete | Uso |
|---|---|
| `schwab-py` | Cliente oficial para Schwab API |
| `pandas` | Manipulacion de datos |
| `openpyxl` | Exportacion a Excel |
| `python-dotenv` | Manejo de variables de entorno |
| `argparse` | CLI para parametros de entrada |

---

## Troubleshooting

| Problema | Solucion |
|---|---|
| `UnicodeEncodeError` con emojis en Windows | Usar `PYTHONIOENCODING=utf-8` antes del comando |
| `RedirectServerExitedError` | Verificar que la Callback URL incluya `:8182` tanto en `.env` como en el portal de Schwab |
| `command not found: activate` en Git Bash | Usar `source .venv/Scripts/activate` (con `source` y barras `/`) |
| Advertencia SSL en el navegador | Normal. Hacer clic en "Avanzado" > "Continuar" |
| Token expirado despues de 7 dias | Eliminar `token.pickle` y volver a correr el script |

---

## Roadmap

- [x] Estructura base del proyecto
- [x] Autenticacion OAuth2
- [x] Fetch de option chains
- [x] Parser a DataFrame
- [x] Exportador Excel con formato
- [ ] Power Query + macro VBA para Excel
- [ ] Refresh automatico (scheduler)
- [ ] Soporte multi-subyacente
- [ ] Validacion de inputs (simbolo, fecha, formato)
- [ ] Interfaz web (Streamlit)
- [ ] GitHub Actions CI

---

## Autores

Proyecto colaborativo entre desarrollador Python y analista financiero profesional.
