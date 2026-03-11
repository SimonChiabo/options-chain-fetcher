# Options Chain Fetcher 📊

Herramienta Python para obtener cadenas de opciones (puts & calls) en tiempo real desde la **Schwab API** (ex TD Ameritrade) y exportarlas a Excel para análisis financiero profesional.

---

## 🎯 Objetivo

Proveer a un analista financiero una hoja Excel actualizable con:
- Cadena completa de opciones (calls y puts) por subyacente
- Filtro por vencimiento
- Precios **bid / ask** por strike
- Greeks (delta, gamma, theta, vega)
- Volumen y Open Interest

---

## 🏗️ Arquitectura

```
Schwab API (OAuth2)
       ↓
  Python Script
  (auth + fetch + parse)
       ↓
   Excel (.xlsx)
   ├── Sheet: CALLS
   └── Sheet: PUTS
       ↓
  Excel Power Query
  (auto-refresh con VBA)
```

---

## 📁 Estructura del proyecto

```
options-chain-fetcher/
├── src/
│   ├── __init__.py
│   ├── auth.py          # OAuth2 con Schwab API
│   ├── fetcher.py       # Llamadas a la API (option chains)
│   ├── parser.py        # Transformación de datos a DataFrame
│   └── exporter.py      # Exportación a .xlsx
├── tests/
│   ├── __init__.py
│   ├── test_fetcher.py
│   └── test_parser.py
├── docs/
│   └── schwab_setup.md  # Guía para configurar credenciales
├── output/              # Archivos .xlsx generados (gitignored)
├── main.py              # Entry point
├── config.py            # Configuración general
├── requirements.txt
├── .env.example         # Template de variables de entorno
├── .gitignore
└── README.md
```

---

## ⚙️ Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/SimonChiabo/options-chain-fetcher.git
cd options-chain-fetcher

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar credenciales
cp .env.example .env
# → Editar .env con tus credenciales de Schwab
```

---

## 🚀 Uso rápido

```bash
python main.py --symbol SPY --expiration 2025-06-20
```

Esto genera `output/SPY_20250620_options.xlsx` con las sheets CALLS y PUTS.

---

## 🔐 Credenciales Schwab

Ver guía completa en [`docs/schwab_setup.md`](docs/schwab_setup.md).

En resumen:
1. Crear cuenta de desarrollador en [developer.schwab.com](https://developer.schwab.com)
2. Registrar una nueva app → obtener `Client ID` y `Client Secret`
3. Configurar redirect URI: `https://127.0.0.1`
4. Copiar credenciales al archivo `.env`

---

## 📦 Dependencias principales

| Paquete | Uso |
|---|---|
| `schwab-py` | Cliente oficial para Schwab API |
| `pandas` | Manipulación de datos |
| `openpyxl` | Exportación a Excel |
| `python-dotenv` | Manejo de variables de entorno |
| `argparse` | CLI para parámetros de entrada |

---

## 🗺️ Roadmap

- [x] Estructura base del proyecto
- [x] Autenticación OAuth2
- [ ] Fetch de option chains
- [ ] Parser a DataFrame
- [ ] Exportador Excel con formato
- [ ] Power Query + macro VBA para Excel
- [ ] Refresh automático (scheduler)
- [ ] Soporte multi-subyacente
- [ ] Añadir Greeks al output

---

## 👥 Autores

Proyecto colaborativo entre desarrollador Python y analista financiero profesional.
