# Options Chain Fetcher — Expansion Plan (3 Phases)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the options chain CLI with financial domain features (Max Pain, P/C Ratio, breakeven, IV Skew, multi-expiration), portfolio-quality packaging (pyproject.toml, GitHub Actions, README), and rich terminal output.

**Architecture:** New `src/analyzer.py` handles all domain calculations (Max Pain, P/C Ratio, IV Skew). `src/parser.py` gains a breakeven column. `src/exporter.py` gains an ANALYSIS sheet and a separate multi-expiration export function. `src/fetcher.py` gains `fetch_multiple_expirations`. `main.py` integrates all of the above and gains rich output. No restructuring of the existing src/ layout.

**Tech Stack:** Python 3.10+, pandas, openpyxl, schwab-py, rich (new dependency), pytest, GitHub Actions

---

## File Map

| File | Action | Phase |
|---|---|---|
| `src/analyzer.py` | Create | A |
| `tests/test_analyzer.py` | Create | A |
| `src/parser.py` | Modify — add `_add_breakeven` | A |
| `tests/test_parser.py` | Modify — add breakeven tests | A |
| `src/exporter.py` | Modify — add ANALYSIS sheet + `export_multiple_to_excel` | A, B |
| `tests/test_exporter.py` | Modify — add ANALYSIS and multi-exp tests | A, B |
| `main.py` | Modify — integrate analyzer, rich, `--expirations` | A, C, B |
| `requirements.txt` | Modify — add `rich` | C |
| `pyproject.toml` | Create | C |
| `.github/workflows/tests.yml` | Create | C |
| `README.md` | Create | C |
| `src/fetcher.py` | Modify — add `fetch_multiple_expirations` | B |
| `tests/test_fetcher.py` | Modify — add multi-exp tests | B |
| `tests/test_analyzer.py` | Modify — add IV Skew tests | B |

---

## FASE A — Domain Features Core

### Task A1: src/analyzer.py — Max Pain y Put/Call Ratio

**Files:**
- Create: `src/analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_analyzer.py`:

```python
"""Tests para src/analyzer.py. No requieren credenciales de Schwab."""

import pandas as pd
import pytest
from src.analyzer import calculate_max_pain, calculate_pc_ratio


def _make_df(strikes, oi, vol=None):
    return pd.DataFrame({
        "strike": [float(s) for s in strikes],
        "openInterest": oi,
        "volume": vol if vol is not None else [100] * len(strikes),
    })


class TestMaxPain:
    def test_max_pain_strike_is_minimum_buyer_value(self):
        # At S=100: call_pain=0, put_pain=(105-100)*100+(110-100)*50=1000 => total=1000
        # At S=105: call_pain=(105-100)*100=500, put_pain=(110-105)*50=250 => total=750  <- min
        # At S=110: call_pain=(110-100)*100+(110-105)*50=1250, put_pain=0 => total=1250
        calls = _make_df([100, 105, 110], [100, 50, 200])
        puts  = _make_df([100, 105, 110], [300, 100, 50])
        result = calculate_max_pain(calls, puts)
        assert result["strike"] == 105.0

    def test_max_pain_returns_pain_by_strike_dict(self):
        calls = _make_df([100, 105, 110], [100, 50, 200])
        puts  = _make_df([100, 105, 110], [300, 100, 50])
        result = calculate_max_pain(calls, puts)
        assert isinstance(result["pain_by_strike"], dict)
        assert 105.0 in result["pain_by_strike"]
        assert abs(result["pain_by_strike"][105.0] - 750) < 0.01

    def test_max_pain_empty_data(self):
        empty = pd.DataFrame({"strike": [], "openInterest": [], "volume": []})
        result = calculate_max_pain(empty, empty)
        assert result["strike"] == 0.0
        assert result["pain_by_strike"] == {}

    def test_max_pain_single_strike(self):
        calls = _make_df([100], [500])
        puts  = _make_df([100], [500])
        result = calculate_max_pain(calls, puts)
        assert result["strike"] == 100.0


class TestPCRatio:
    def test_volume_ratio(self):
        calls = _make_df([100, 105], [1000, 2000], [100, 200])
        puts  = _make_df([100, 105], [500, 1500],  [150, 150])
        result = calculate_pc_ratio(calls, puts)
        # put_vol=300, call_vol=300 => 1.0
        assert result["volume_ratio"] == 1.0

    def test_oi_ratio(self):
        calls = _make_df([100, 105], [1000, 2000], [100, 200])
        puts  = _make_df([100, 105], [500, 1500],  [150, 150])
        result = calculate_pc_ratio(calls, puts)
        # put_oi=2000, call_oi=3000 => 0.6667
        assert abs(result["oi_ratio"] - round(2000 / 3000, 4)) < 0.0001

    def test_zero_call_volume_returns_inf(self):
        calls = _make_df([100], [100], [0])
        puts  = _make_df([100], [100], [50])
        result = calculate_pc_ratio(calls, puts)
        assert result["volume_ratio"] == float("inf")

    def test_zero_call_oi_returns_inf(self):
        calls = pd.DataFrame({"strike": [100.0], "openInterest": [0], "volume": [100]})
        puts  = _make_df([100], [200], [50])
        result = calculate_pc_ratio(calls, puts)
        assert result["oi_ratio"] == float("inf")
```

- [ ] **Step 2: Verificar que los tests fallan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analyzer.py -v
```

Resultado esperado: `ImportError: No module named 'src.analyzer'`

- [ ] **Step 3: Crear src/analyzer.py**

```python
"""
src/analyzer.py
Calculos de dominio financiero sobre option chains.
"""

from datetime import date
from typing import Any
import pandas as pd


def calculate_max_pain(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Calcula el Max Pain strike.

    Para cada strike candidato S:
      call_value = sum(K < S): (S - K) * call_OI[K]
      put_value  = sum(K > S): (K - S) * put_OI[K]
    Max Pain = S que minimiza (call_value + put_value).

    Returns:
        {"strike": float, "pain_by_strike": dict[float, float]}
    """
    call_oi: dict[float, float] = {}
    put_oi:  dict[float, float] = {}

    if not calls_df.empty and "strike" in calls_df.columns:
        call_oi = dict(zip(calls_df["strike"].astype(float), calls_df["openInterest"]))
    if not puts_df.empty and "strike" in puts_df.columns:
        put_oi  = dict(zip(puts_df["strike"].astype(float),  puts_df["openInterest"]))

    all_strikes = sorted(set(call_oi) | set(put_oi))
    if not all_strikes:
        return {"strike": 0.0, "pain_by_strike": {}}

    pain: dict[float, float] = {}
    for s in all_strikes:
        call_pain = sum((s - k) * oi for k, oi in call_oi.items() if k < s)
        put_pain  = sum((k - s) * oi for k, oi in put_oi.items()  if k > s)
        pain[s] = call_pain + put_pain

    max_pain_strike = min(pain, key=pain.__getitem__)
    return {"strike": max_pain_strike, "pain_by_strike": pain}


def calculate_pc_ratio(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
) -> dict[str, float]:
    """
    Calcula el Put/Call Ratio por volumen y por Open Interest.

    > 1.0 => sentimiento bearish, < 1.0 => sentimiento bullish.

    Returns:
        {"volume_ratio": float, "oi_ratio": float}
    """
    call_vol = float(calls_df["volume"].sum())
    put_vol  = float(puts_df["volume"].sum())
    call_oi  = float(calls_df["openInterest"].sum())
    put_oi   = float(puts_df["openInterest"].sum())

    return {
        "volume_ratio": round(put_vol / call_vol, 4) if call_vol > 0 else float("inf"),
        "oi_ratio":     round(put_oi  / call_oi,  4) if call_oi  > 0 else float("inf"),
    }
```

- [ ] **Step 4: Verificar que los tests pasan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analyzer.py -v
```

Resultado esperado: `8 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/analyzer.py tests/test_analyzer.py
git commit -m "feat: add analyzer module with Max Pain and P/C Ratio"
```

---

### Task A2: Breakeven column en parser

**Files:**
- Modify: `src/parser.py`
- Modify: `tests/test_parser.py`

- [ ] **Step 1: Agregar tests de breakeven en test_parser.py**

Agregar al final de `tests/test_parser.py`:

```python
def test_calls_have_breakeven_column(mock_raw):
    calls, _ = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert "breakeven" in calls.columns


def test_puts_have_breakeven_column(mock_raw):
    _, puts = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    assert "breakeven" in puts.columns


def test_call_breakeven_value(mock_raw):
    # strike=575, bid=12.0, ask=12.2, midpoint=12.1 => breakeven=587.1
    calls, _ = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    row = calls[calls["strike"] == 575.0].iloc[0]
    assert abs(row["breakeven"] - 587.1) < 0.01


def test_put_breakeven_value(mock_raw):
    # strike=575, bid=7.5, ask=7.7, midpoint=7.6 => breakeven=567.4
    _, puts = parse_option_chain(mock_raw, MOCK_EXPIRATION)
    row = puts[puts["strike"] == 575.0].iloc[0]
    assert abs(row["breakeven"] - 567.4) < 0.01


def test_breakeven_empty_dataframe():
    calls, puts = parse_option_chain({}, MOCK_EXPIRATION)
    # No debe lanzar excepcion con DataFrames vacios
    assert calls.empty
    assert puts.empty
```

- [ ] **Step 2: Verificar que los tests fallan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_parser.py::test_calls_have_breakeven_column -v
```

Resultado esperado: `FAILED — AssertionError`

- [ ] **Step 3: Agregar _add_breakeven en src/parser.py**

Agregar la funcion privada y las dos llamadas en `parse_option_chain`. El archivo completo queda:

```python
"""
src/parser.py
Transforma la respuesta cruda de la Schwab API en DataFrames
estructurados y listos para exportar a Excel.
"""

from datetime import date
import pandas as pd

import config


def _extract_legs(exp_date_map: dict, expiration: date) -> list[dict]:
    target = expiration.strftime("%Y-%m-%d")
    rows = []
    for date_key, strikes in exp_date_map.items():
        if not date_key.startswith(target):
            continue
        for strike_price, contracts in strikes.items():
            for contract in contracts:
                row = {**contract, "strike": float(strike_price)}
                rows.append(row)
    return rows


def _add_breakeven(df: pd.DataFrame, option_type: str) -> None:
    """Agrega columna breakeven al DataFrame in-place. No lanza si faltan columnas."""
    if df.empty or "bid" not in df.columns or "ask" not in df.columns or "strike" not in df.columns:
        return
    midpoint = ((df["bid"] + df["ask"]) / 2).round(4)
    if option_type == "CALL":
        df["breakeven"] = (df["strike"] + midpoint).round(4)
    else:
        df["breakeven"] = (df["strike"] - midpoint).round(4)


def parse_option_chain(raw: dict, expiration: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Parsea la respuesta cruda de la API.

    Args:
        raw:        Dict devuelto por fetcher.fetch_option_chain()
        expiration: Fecha de vencimiento usada en la consulta

    Returns:
        Tupla (calls_df, puts_df) con columnas estandarizadas.
    """
    calls_raw = _extract_legs(raw.get("callExpDateMap", {}), expiration)
    puts_raw  = _extract_legs(raw.get("putExpDateMap",  {}), expiration)

    calls_df = _to_dataframe(calls_raw, config.CALLS_COLUMNS)
    puts_df  = _to_dataframe(puts_raw,  config.PUTS_COLUMNS)

    _add_breakeven(calls_df, option_type="CALL")
    _add_breakeven(puts_df,  option_type="PUT")

    return calls_df, puts_df


def _to_dataframe(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    """Convierte lista de dicts a DataFrame con columnas seleccionadas."""
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)

    available = [c for c in columns if c in df.columns]
    df = df[available].copy()

    for col in config.NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "strike" in df.columns:
        df = df.sort_values("strike").reset_index(drop=True)

    if "bid" in df.columns and "ask" in df.columns and "spread" not in df.columns:
        ask_pos = df.columns.get_loc("ask")
        df.insert(ask_pos + 1, "spread", (df["ask"] - df["bid"]).round(4))

    return df
```

- [ ] **Step 4: Verificar que todos los tests de parser pasan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_parser.py -v
```

Resultado esperado: `14 passed` (9 originales + 5 nuevos)

- [ ] **Step 5: Commit**

```powershell
git add src/parser.py tests/test_parser.py
git commit -m "feat: add breakeven column to parser output"
```

---

### Task A3: ANALYSIS sheet en exporter

**Files:**
- Modify: `src/exporter.py`
- Modify: `tests/test_exporter.py`

- [ ] **Step 1: Agregar tests de ANALYSIS sheet en test_exporter.py**

Agregar al final de `tests/test_exporter.py`:

```python
def _analysis_fixture():
    return {
        "max_pain": {"strike": 500.0, "pain_by_strike": {500.0: 100.0, 505.0: 200.0}},
        "pc_ratio": {"volume_ratio": 1.25, "oi_ratio": 0.8750},
    }


def test_analysis_sheet_created_when_analysis_provided(tmp_path, monkeypatch):
    monkeypatch.setattr("config.OUTPUT_DIR", str(tmp_path))
    filepath = export_to_excel(
        _minimal_calls(), _minimal_puts(), "SPY", EXPIRATION,
        analysis=_analysis_fixture(),
    )
    wb = openpyxl.load_workbook(filepath)
    assert "ANALYSIS" in wb.sheetnames


def test_analysis_sheet_absent_without_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr("config.OUTPUT_DIR", str(tmp_path))
    filepath = export_to_excel(_minimal_calls(), _minimal_puts(), "SPY", EXPIRATION)
    wb = openpyxl.load_workbook(filepath)
    assert "ANALYSIS" not in wb.sheetnames


def test_analysis_sheet_contains_max_pain(tmp_path, monkeypatch):
    monkeypatch.setattr("config.OUTPUT_DIR", str(tmp_path))
    filepath = export_to_excel(
        _minimal_calls(), _minimal_puts(), "SPY", EXPIRATION,
        analysis=_analysis_fixture(),
    )
    wb = openpyxl.load_workbook(filepath)
    ws = wb["ANALYSIS"]
    all_values = [ws.cell(row=r, column=2).value for r in range(2, ws.max_row + 1)]
    assert "$500.00" in all_values


def test_analysis_sheet_contains_pc_ratio(tmp_path, monkeypatch):
    monkeypatch.setattr("config.OUTPUT_DIR", str(tmp_path))
    filepath = export_to_excel(
        _minimal_calls(), _minimal_puts(), "SPY", EXPIRATION,
        analysis=_analysis_fixture(),
    )
    wb = openpyxl.load_workbook(filepath)
    ws = wb["ANALYSIS"]
    all_values = [ws.cell(row=r, column=2).value for r in range(2, ws.max_row + 1)]
    assert "1.2500" in all_values
```

- [ ] **Step 2: Verificar que los tests fallan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_exporter.py::test_analysis_sheet_created_when_analysis_provided -v
```

Resultado esperado: `FAILED — TypeError` (export_to_excel no acepta `analysis`)

- [ ] **Step 3: Modificar src/exporter.py**

Agregar `_write_analysis_sheet` y el parametro opcional `analysis` a `export_to_excel`. Solo se muestran las partes modificadas:

Agregar despues de la constante `ALT_ROW_COLOR`:

```python
# -- Constantes de formato ya existentes ... --
# (sin cambios en _style_sheet ni _write_sheet)
```

Agregar nueva funcion antes de `export_to_excel`:

```python
def _write_analysis_sheet(
    writer: pd.ExcelWriter,
    analysis: dict,
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
) -> None:
    max_pain = analysis.get("max_pain", {})
    pc_ratio = analysis.get("pc_ratio", {})

    mp_strike = max_pain.get("strike")
    vol_ratio = pc_ratio.get("volume_ratio")
    oi_ratio  = pc_ratio.get("oi_ratio")

    data = {
        "Metrica": [
            "Max Pain Strike",
            "P/C Ratio (Volumen)",
            "P/C Ratio (Open Interest)",
            "Total Calls",
            "Total Puts",
        ],
        "Valor": [
            f"${mp_strike:.2f}" if isinstance(mp_strike, (int, float)) else "N/A",
            f"{vol_ratio:.4f}"  if isinstance(vol_ratio, float) and vol_ratio != float("inf") else str(vol_ratio),
            f"{oi_ratio:.4f}"   if isinstance(oi_ratio,  float) and oi_ratio  != float("inf") else str(oi_ratio),
            str(len(calls_df)),
            str(len(puts_df)),
        ],
        "Interpretacion": [
            "Strike donde la mayoria de opciones expira worthless",
            "> 1.0 bearish  /  < 1.0 bullish",
            "> 1.0 bearish  /  < 1.0 bullish",
            "",
            "",
        ],
    }
    _write_sheet(writer, pd.DataFrame(data), "ANALYSIS", INFO_HEADER_COLOR)
```

Modificar la firma de `export_to_excel` (solo los cambios):

```python
def export_to_excel(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    symbol: str,
    expiration: date,
    analysis: dict | None = None,
) -> pathlib.Path:
    """
    Genera el archivo Excel con las sheets CALLS, PUTS, INFO y (opcional) ANALYSIS.

    Args:
        calls_df:   DataFrame de calls devuelto por parse_option_chain().
        puts_df:    DataFrame de puts devuelto por parse_option_chain().
        symbol:     Ticker del subyacente (ej: "SPY"). Se convierte a uppercase.
        expiration: Fecha de vencimiento usada para nombrar el archivo.
        analysis:   Dict opcional con "max_pain" y "pc_ratio" de analyzer.py.
                    Si se provee, se genera una sheet ANALYSIS adicional.

    Returns:
        Path absoluto del archivo .xlsx generado en OUTPUT_DIR.
    """
    output_dir = pathlib.Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{symbol.upper()}_{expiration.strftime('%Y%m%d')}_options.xlsx"
    filepath = output_dir / filename

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        _write_sheet(writer, calls_df, "CALLS", CALL_HEADER_COLOR)
        _write_sheet(writer, puts_df,  "PUTS",  PUT_HEADER_COLOR)

        if analysis is not None:
            _write_analysis_sheet(writer, analysis, calls_df, puts_df)

        info_data = {
            "Campo": [
                "Subyacente", "Vencimiento", "Descargado el",
                "Calls encontradas", "Puts encontradas", "Fuente",
            ],
            "Valor": [
                symbol.upper(),
                expiration.strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                len(calls_df),
                len(puts_df),
                "Schwab Market Data API",
            ],
        }
        _write_sheet(writer, pd.DataFrame(info_data), "INFO", INFO_HEADER_COLOR)

    print(f"[OK] Excel generado: {filepath}")
    return filepath
```

- [ ] **Step 4: Verificar que todos los tests de exporter pasan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_exporter.py -v
```

Resultado esperado: `7 passed` (3 originales + 4 nuevos)

- [ ] **Step 5: Commit**

```powershell
git add src/exporter.py tests/test_exporter.py
git commit -m "feat: add ANALYSIS sheet to Excel export with Max Pain and P/C Ratio"
```

---

### Task A4: Integrar analyzer en main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Modificar main.py**

Agregar imports al principio del archivo (despues de los imports existentes):

```python
from src.analyzer import calculate_max_pain, calculate_pc_ratio
```

Reemplazar el bloque dentro de `main()` que va desde `raw = fetch_option_chain(...)` hasta `print(f"\n[OK] Listo...")`:

```python
        raw = fetch_option_chain(
            symbol=args.symbol,
            expiration=args.expiration,
            contract_type=args.type,
            strike_count=args.strikes,
            client=client,
        )

        calls_df, puts_df = parse_option_chain(raw, args.expiration)

        max_pain = calculate_max_pain(calls_df, puts_df)
        pc_ratio = calculate_pc_ratio(calls_df, puts_df)
        analysis = {"max_pain": max_pain, "pc_ratio": pc_ratio}

        print(f"    -> {len(calls_df)} calls | {len(puts_df)} puts encontradas")
        print(f"    -> Max Pain: ${max_pain['strike']:.2f}")
        print(f"    -> P/C Ratio  Vol: {pc_ratio['volume_ratio']:.2f}  |  OI: {pc_ratio['oi_ratio']:.2f}")

        filepath = export_to_excel(calls_df, puts_df, args.symbol, args.expiration, analysis=analysis)

        print(f"\n[OK] Listo. Abri el archivo: {filepath}\n")
```

- [ ] **Step 2: Correr la suite completa**

```powershell
.\.venv\Scripts\python.exe -m pytest --tb=short -q
```

Resultado esperado: todos los tests pasan (minimo 41 passed).

- [ ] **Step 3: Commit**

```powershell
git add main.py
git commit -m "feat: integrate Max Pain and P/C Ratio into main CLI output"
```

---

### CHECKPOINT A

- [ ] **Verificar cobertura**

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=src --cov=main --cov=config --cov-report=term-missing --tb=no -q
```

Resultado esperado: coverage total >= 85%, `src/analyzer.py` >= 90%.

- [ ] **Smoke test manual** (opcional si no hay credenciales):

```powershell
.\.venv\Scripts\python.exe main.py --help
```

Debe mostrar la ayuda sin errores de import.

---

## FASE C — Packaging y Presentacion

### Task C1: pyproject.toml

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Crear pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=78.1.1"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "options-chain-fetcher"
version = "1.0.0"
description = "Download options chains from Schwab API and export to Excel"
requires-python = ">=3.10"
readme = "README.md"
license = { text = "MIT" }
dependencies = [
    "schwab-py>=1.5.1,<2.0.0",
    "pandas>=2.0.0,<3.0.0",
    "openpyxl>=3.1.5,<4.0.0",
    "python-dotenv>=1.2.0,<2.0.0",
    "requests>=2.33.0,<3.0.0",
    "cryptography>=46.0.6",
    "rich>=13.0.0,<15.0.0",
]

[project.scripts]
options-chain = "main:main"

[tool.setuptools]
py-modules = ["main", "config"]
packages   = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.coverage.run]
source = ["src", "main", "config"]
```

- [ ] **Step 2: Verificar que pytest sigue funcionando con la nueva config**

```powershell
.\.venv\Scripts\python.exe -m pytest --tb=short -q
```

Resultado esperado: misma cantidad de tests passing que antes.

- [ ] **Step 3: Commit**

```powershell
git add pyproject.toml
git commit -m "chore: add pyproject.toml for packaging and pytest config"
```

---

### Task C2: GitHub Actions CI

**Files:**
- Create: `.github/workflows/tests.yml`

- [ ] **Step 1: Crear el directorio y el workflow**

```powershell
New-Item -ItemType Directory -Force ".github/workflows"
```

Crear `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: pip install -r requirements.txt pytest pytest-cov

      - name: Run tests with coverage
        run: |
          python -m pytest \
            --cov=src --cov=main --cov=config \
            --cov-report=term-missing \
            --cov-fail-under=85 \
            -q
```

- [ ] **Step 2: Commit**

```powershell
git add .github/workflows/tests.yml
git commit -m "ci: add GitHub Actions workflow for tests on Python 3.10 and 3.12"
```

---

### Task C3: rich terminal output

**Files:**
- Modify: `requirements.txt`
- Modify: `main.py`

- [ ] **Step 1: Agregar rich a requirements.txt**

Agregar al final de `requirements.txt`:

```
rich>=13.0.0,<15.0.0
```

- [ ] **Step 2: Instalar rich en el venv**

```powershell
.\.venv\Scripts\python.exe -m pip install "rich>=13.0.0,<15.0.0"
```

- [ ] **Step 3: Reemplazar los prints de main.py con rich**

El archivo `main.py` completo queda:

```python
"""
main.py
Entry point del proyecto. Acepta parametros por CLI.

Uso:
    python main.py --symbol SPY --expiration 2025-06-20
    python main.py --symbol QQQ --expiration 2025-03-21 --strikes 20
"""

import argparse
import re
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table

import config
from config       import ConfigError
from src.auth     import get_client
from src.fetcher  import fetch_option_chain
from src.parser   import parse_option_chain
from src.exporter import export_to_excel
from src.analyzer import calculate_max_pain, calculate_pc_ratio

console = Console()


def _validate_symbol(symbol: str) -> str:
    """Solo letras, numeros y punto. Maximo 10 caracteres."""
    if not re.fullmatch(r"[A-Za-z0-9.]{1,10}", symbol):
        raise ValueError(
            f"Simbolo invalido: '{symbol}'. "
            "Solo letras, numeros y punto. Maximo 10 caracteres."
        )
    return symbol.upper()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga option chains desde Schwab API y exporta a Excel."
    )
    parser.add_argument(
        "--symbol", "-s",
        required=True,
        type=str,
        help="Ticker del subyacente (ej: SPY, QQQ, AAPL)",
    )
    parser.add_argument(
        "--expiration", "-e",
        required=True,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Fecha de vencimiento en formato YYYY-MM-DD",
    )
    parser.add_argument(
        "--strikes", "-k",
        required=False,
        type=int,
        default=None,
        help="Cantidad de strikes a cada lado del ATM (default: todos)",
    )
    parser.add_argument(
        "--type", "-t",
        required=False,
        choices=["ALL", "CALL", "PUT"],
        default="ALL",
        help="Tipo de contrato: ALL, CALL o PUT (default: ALL)",
    )
    return parser.parse_args()


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        config.validate_config()
        args = parse_args()
        args.symbol = _validate_symbol(args.symbol)

        console.print(
            f"\n[bold cyan][*][/bold cyan] Descargando option chain: "
            f"[bold]{args.symbol}[/bold] | Vencimiento: {args.expiration}"
        )

        client = get_client()

        raw = fetch_option_chain(
            symbol=args.symbol,
            expiration=args.expiration,
            contract_type=args.type,
            strike_count=args.strikes,
            client=client,
        )

        calls_df, puts_df = parse_option_chain(raw, args.expiration)

        max_pain = calculate_max_pain(calls_df, puts_df)
        pc_ratio = calculate_pc_ratio(calls_df, puts_df)
        analysis = {"max_pain": max_pain, "pc_ratio": pc_ratio}

        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Metrica", style="cyan", min_width=22)
        table.add_column("Valor",   style="bold green")
        table.add_row("Calls encontradas",   str(len(calls_df)))
        table.add_row("Puts encontradas",    str(len(puts_df)))
        table.add_row("Max Pain Strike",     f"${max_pain['strike']:.2f}")
        table.add_row("P/C Ratio (Volumen)", f"{pc_ratio['volume_ratio']:.2f}")
        table.add_row("P/C Ratio (OI)",      f"{pc_ratio['oi_ratio']:.2f}")
        console.print(table)

        filepath = export_to_excel(calls_df, puts_df, args.symbol, args.expiration, analysis=analysis)

        console.print(f"\n[bold green][OK][/bold green] Abri el archivo: [underline]{filepath}[/underline]\n")

    except (ValueError, ConfigError) as e:
        console.print(f"\n[bold red][ERROR][/bold red] {e}")
        raise SystemExit(1)
    except RuntimeError as e:
        console.print(f"\n[bold red][ERROR][/bold red] API: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr la suite completa**

```powershell
.\.venv\Scripts\python.exe -m pytest --tb=short -q
```

Resultado esperado: todos los tests pasan.

- [ ] **Step 5: Commit**

```powershell
git add requirements.txt main.py
git commit -m "feat: add rich terminal output with summary table"
```

---

### Task C4: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Crear README.md**

```markdown
# Options Chain Fetcher

[![Tests](https://github.com/TU_USUARIO/options-chain-fetcher/actions/workflows/tests.yml/badge.svg)](https://github.com/TU_USUARIO/options-chain-fetcher/actions)
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
git clone https://github.com/TU_USUARIO/options-chain-fetcher.git
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

36+ tests, 85%+ coverage. Sin mocks de BD: todos los tests usan datos locales.

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
  tests/           # 36+ tests con pytest
```
```

> **Nota:** Reemplazar `TU_USUARIO` con tu usuario de GitHub en los badges antes de pushear.

- [ ] **Step 2: Commit**

```powershell
git add README.md
git commit -m "docs: add README with badges, usage, output example, and structure"
```

---

### CHECKPOINT C

- [ ] **Verificar suite completa**

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=src --cov=main --cov=config --cov-fail-under=85 -q
```

- [ ] **Verificar que rich importa correctamente**

```powershell
.\.venv\Scripts\python.exe -c "from rich.console import Console; Console().print('[green]OK[/green]')"
```

- [ ] **Verificar pyproject.toml es valido**

```powershell
.\.venv\Scripts\python.exe -m pip install --dry-run -e . 2>&1 | Select-String -Pattern "error|Error" -NotMatch
```

---

## FASE B — Multi-vencimiento + IV Skew

### Task B1: fetch_multiple_expirations en fetcher.py

**Files:**
- Modify: `src/fetcher.py`
- Modify: `tests/test_fetcher.py`

- [ ] **Step 1: Agregar tests de multi-expiracion en test_fetcher.py**

Agregar al final de `tests/test_fetcher.py`:

```python
from src.fetcher import fetch_multiple_expirations


VALID_MULTI = {
    "status": "SUCCESS",
    "callExpDateMap": {"2025-06-20:30": {"500.0": [{"bid": 1.0}]}},
    "putExpDateMap":  {"2025-06-20:30": {"500.0": [{"bid": 0.8}]}},
}


def test_fetch_multiple_returns_dict_keyed_by_date():
    exp1 = date(2025, 6, 20)
    exp2 = date(2025, 7, 18)
    client = _mock_client_with_response(VALID_MULTI)
    results = fetch_multiple_expirations("SPY", [exp1, exp2], client=client)
    assert set(results.keys()) == {exp1, exp2}


def test_fetch_multiple_calls_api_once_per_expiration():
    exp1 = date(2025, 6, 20)
    exp2 = date(2025, 7, 18)
    client = _mock_client_with_response(VALID_MULTI)
    fetch_multiple_expirations("SPY", [exp1, exp2], client=client)
    assert client.get_option_chain.call_count == 2


def test_fetch_multiple_single_expiration_works():
    exp = date(2025, 6, 20)
    client = _mock_client_with_response(VALID_MULTI)
    results = fetch_multiple_expirations("SPY", [exp], client=client)
    assert exp in results
    assert results[exp] == VALID_MULTI
```

- [ ] **Step 2: Verificar que los tests fallan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fetcher.py::test_fetch_multiple_returns_dict_keyed_by_date -v
```

Resultado esperado: `ImportError: cannot import name 'fetch_multiple_expirations'`

- [ ] **Step 3: Agregar fetch_multiple_expirations en src/fetcher.py**

Agregar al final de `src/fetcher.py` (sin modificar nada existente):

```python
def fetch_multiple_expirations(
    symbol: str,
    expirations: list[date],
    contract_type: str = "ALL",
    strike_count: Optional[int] = None,
    client: Optional[schwab.client.Client] = None,
) -> dict[date, dict[str, Any]]:
    """
    Descarga la option chain para multiples vencimientos reusando el mismo cliente.

    Args:
        symbol:        Ticker del subyacente.
        expirations:   Lista de fechas de vencimiento.
        contract_type: "CALL", "PUT" o "ALL" (default).
        strike_count:  Strikes a cada lado del ATM. None = todos.
        client:        Cliente autenticado. Se crea uno si es None.

    Returns:
        {expiration: raw_data} con la misma estructura que fetch_option_chain().
    """
    if client is None:
        client = get_client()

    return {
        exp: fetch_option_chain(symbol, exp, contract_type, strike_count, client)
        for exp in expirations
    }
```

- [ ] **Step 4: Verificar que todos los tests de fetcher pasan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fetcher.py -v
```

Resultado esperado: `11 passed` (8 originales + 3 nuevos)

- [ ] **Step 5: Commit**

```powershell
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add fetch_multiple_expirations to fetcher"
```

---

### Task B2: calculate_iv_skew en analyzer.py

**Files:**
- Modify: `src/analyzer.py`
- Modify: `tests/test_analyzer.py`

- [ ] **Step 1: Agregar tests de IV Skew en test_analyzer.py**

Agregar al final de `tests/test_analyzer.py`:

```python
from datetime import date
from src.analyzer import calculate_iv_skew


class TestIVSkew:
    def _calls(self, strikes, ivs):
        return pd.DataFrame({"strike": [float(s) for s in strikes], "impliedVolatility": ivs})

    def _puts(self, strikes, ivs):
        return pd.DataFrame({"strike": [float(s) for s in strikes], "impliedVolatility": ivs})

    def test_iv_skew_returns_dataframe(self):
        exp = date(2025, 6, 20)
        data = {exp: (self._calls([100, 105], [0.20, 0.18]), self._puts([100, 105], [0.22, 0.21]))}
        skew = calculate_iv_skew(data)
        assert isinstance(skew, pd.DataFrame)

    def test_iv_skew_has_strike_column(self):
        exp = date(2025, 6, 20)
        data = {exp: (self._calls([100], [0.20]), self._puts([100], [0.22]))}
        skew = calculate_iv_skew(data)
        assert "strike" in skew.columns

    def test_iv_skew_has_expiration_column(self):
        exp = date(2025, 6, 20)
        data = {exp: (self._calls([100], [0.20]), self._puts([100], [0.22]))}
        skew = calculate_iv_skew(data)
        assert "2025-06-20" in skew.columns

    def test_iv_skew_multiple_expirations(self):
        exp1 = date(2025, 6, 20)
        exp2 = date(2025, 7, 18)
        data = {
            exp1: (self._calls([100], [0.20]), self._puts([100], [0.22])),
            exp2: (self._calls([100], [0.25]), self._puts([100], [0.26])),
        }
        skew = calculate_iv_skew(data)
        assert set(skew.columns) == {"strike", "2025-06-20", "2025-07-18"}

    def test_iv_skew_call_iv_values(self):
        exp = date(2025, 6, 20)
        data = {exp: (self._calls([100.0], [0.20]), self._puts([100.0], [0.22]))}
        skew = calculate_iv_skew(data)
        row = skew[skew["strike"] == 100.0].iloc[0]
        assert abs(row["2025-06-20"] - 0.20) < 0.001

    def test_iv_skew_empty_data(self):
        skew = calculate_iv_skew({})
        assert skew.empty
```

- [ ] **Step 2: Verificar que los tests fallan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analyzer.py::TestIVSkew -v
```

Resultado esperado: `ImportError: cannot import name 'calculate_iv_skew'`

- [ ] **Step 3: Agregar calculate_iv_skew en src/analyzer.py**

Agregar al final de `src/analyzer.py`:

```python
def calculate_iv_skew(
    expirations_data: dict[date, tuple[pd.DataFrame, pd.DataFrame]],
) -> pd.DataFrame:
    """
    Construye la tabla de volatility skew por strike y vencimiento.

    Usa la impliedVolatility de las calls. Si un strike no tiene call
    para una expiracion, el valor queda como None.

    Args:
        expirations_data: {expiration: (calls_df, puts_df)}

    Returns:
        DataFrame con strikes como filas y fechas de vencimiento como columnas.
    """
    if not expirations_data:
        return pd.DataFrame()

    all_strikes: set[float] = set()
    for calls_df, puts_df in expirations_data.values():
        if "strike" in calls_df.columns:
            all_strikes |= set(calls_df["strike"].tolist())
        if "strike" in puts_df.columns:
            all_strikes |= set(puts_df["strike"].tolist())

    sorted_strikes = sorted(all_strikes)
    table: dict[str, list] = {"strike": sorted_strikes}

    for exp in sorted(expirations_data):
        calls_df, _ = expirations_data[exp]
        col = exp.strftime("%Y-%m-%d")
        if "impliedVolatility" in calls_df.columns and "strike" in calls_df.columns:
            iv_map = dict(zip(calls_df["strike"], calls_df["impliedVolatility"]))
        else:
            iv_map = {}
        table[col] = [iv_map.get(s) for s in sorted_strikes]

    return pd.DataFrame(table)
```

- [ ] **Step 4: Verificar todos los tests de analyzer**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analyzer.py -v
```

Resultado esperado: `14 passed` (8 originales + 6 nuevos)

- [ ] **Step 5: Commit**

```powershell
git add src/analyzer.py tests/test_analyzer.py
git commit -m "feat: add calculate_iv_skew to analyzer"
```

---

### Task B3: Multi-expiration Excel en exporter.py

**Files:**
- Modify: `src/exporter.py`
- Modify: `tests/test_exporter.py`

- [ ] **Step 1: Agregar tests de export_multiple_to_excel en test_exporter.py**

Agregar al final de `tests/test_exporter.py`:

```python
import pandas as pd
from src.exporter import export_multiple_to_excel


def test_export_multiple_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr("config.OUTPUT_DIR", str(tmp_path))
    exp1 = date(2025, 6, 20)
    exp2 = date(2025, 7, 18)
    parsed = {
        exp1: (_minimal_calls(), _minimal_puts()),
        exp2: (_minimal_calls(), _minimal_puts()),
    }
    skew_df = pd.DataFrame({"strike": [500.0], "2025-06-20": [0.20], "2025-07-18": [0.25]})
    filepath = export_multiple_to_excel(parsed, skew_df, "SPY")
    assert filepath.exists()
    assert filepath.suffix == ".xlsx"


def test_export_multiple_sheet_names(tmp_path, monkeypatch):
    monkeypatch.setattr("config.OUTPUT_DIR", str(tmp_path))
    exp1 = date(2025, 6, 20)
    parsed = {exp1: (_minimal_calls(), _minimal_puts())}
    skew_df = pd.DataFrame({"strike": [500.0], "2025-06-20": [0.20]})
    filepath = export_multiple_to_excel(parsed, skew_df, "SPY")
    wb = openpyxl.load_workbook(filepath)
    assert "CALLS_20250620" in wb.sheetnames
    assert "PUTS_20250620" in wb.sheetnames
    assert "IV_SKEW" in wb.sheetnames
    assert "INFO" in wb.sheetnames


def test_export_multiple_filename_contains_all_dates(tmp_path, monkeypatch):
    monkeypatch.setattr("config.OUTPUT_DIR", str(tmp_path))
    exp1 = date(2025, 6, 20)
    exp2 = date(2025, 7, 18)
    parsed = {
        exp1: (_minimal_calls(), _minimal_puts()),
        exp2: (_minimal_calls(), _minimal_puts()),
    }
    skew_df = pd.DataFrame({"strike": [500.0]})
    filepath = export_multiple_to_excel(parsed, skew_df, "SPY")
    assert "20250620" in filepath.name
    assert "20250718" in filepath.name
```

- [ ] **Step 2: Verificar que los tests fallan**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_exporter.py::test_export_multiple_creates_file -v
```

Resultado esperado: `ImportError: cannot import name 'export_multiple_to_excel'`

- [ ] **Step 3: Agregar export_multiple_to_excel en src/exporter.py**

Agregar al final de `src/exporter.py` (antes del `if __name__ == "__main__"` si existiera):

```python
def export_multiple_to_excel(
    parsed: dict,
    skew_df: pd.DataFrame,
    symbol: str,
) -> pathlib.Path:
    """
    Genera el archivo Excel para multiples vencimientos.

    Args:
        parsed:  {expiration: (calls_df, puts_df)} de parse_option_chain().
        skew_df: DataFrame de IV Skew de calculate_iv_skew().
        symbol:  Ticker del subyacente.

    Returns:
        Path absoluto del archivo .xlsx generado en OUTPUT_DIR.
    """
    output_dir = pathlib.Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    sorted_exps = sorted(parsed.keys())
    dates_str   = "_".join(exp.strftime("%Y%m%d") for exp in sorted_exps)
    filename    = f"{symbol.upper()}_{dates_str}_options.xlsx"
    filepath    = output_dir / filename

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for exp in sorted_exps:
            calls_df, puts_df = parsed[exp]
            tag = exp.strftime("%Y%m%d")
            _write_sheet(writer, calls_df, f"CALLS_{tag}", CALL_HEADER_COLOR)
            _write_sheet(writer, puts_df,  f"PUTS_{tag}",  PUT_HEADER_COLOR)

        if not skew_df.empty:
            _write_sheet(writer, skew_df, "IV_SKEW", INFO_HEADER_COLOR)

        total_calls = sum(len(parsed[e][0]) for e in sorted_exps)
        total_puts  = sum(len(parsed[e][1]) for e in sorted_exps)
        exps_str    = ", ".join(exp.strftime("%Y-%m-%d") for exp in sorted_exps)

        info_data = {
            "Campo": [
                "Subyacente", "Vencimientos", "Descargado el",
                "Total Calls", "Total Puts", "Fuente",
            ],
            "Valor": [
                symbol.upper(),
                exps_str,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                total_calls,
                total_puts,
                "Schwab Market Data API",
            ],
        }
        _write_sheet(writer, pd.DataFrame(info_data), "INFO", INFO_HEADER_COLOR)

    print(f"[OK] Excel generado: {filepath}")
    return filepath
```

- [ ] **Step 4: Verificar todos los tests de exporter**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_exporter.py -v
```

Resultado esperado: `10 passed` (7 anteriores + 3 nuevos)

- [ ] **Step 5: Commit**

```powershell
git add src/exporter.py tests/test_exporter.py
git commit -m "feat: add export_multiple_to_excel with per-expiration sheets and IV Skew"
```

---

### Task B4: --expirations en CLI (main.py)

**Files:**
- Modify: `main.py`

- [ ] **Step 0: Agregar los nuevos imports al tope de main.py**

Al bloque de imports existente de main.py, agregar estas 3 lineas junto a los otros imports de src/:

```python
from src.fetcher  import fetch_multiple_expirations
from src.analyzer import calculate_iv_skew
from src.exporter import export_multiple_to_excel
```

- [ ] **Step 1: Agregar --expirations al parser de argumentos**

En `parse_args()`, cambiar `--expiration` a `required=False` y agregar `--expirations`:

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga option chains desde Schwab API y exporta a Excel."
    )
    parser.add_argument(
        "--symbol", "-s",
        required=True,
        type=str,
        help="Ticker del subyacente (ej: SPY, QQQ, AAPL)",
    )
    parser.add_argument(
        "--expiration", "-e",
        required=False,
        default=None,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Fecha de vencimiento en formato YYYY-MM-DD",
    )
    parser.add_argument(
        "--expirations", "-E",
        required=False,
        default=None,
        type=lambda s: [datetime.strptime(d.strip(), "%Y-%m-%d").date() for d in s.split(",")],
        help="Multiples vencimientos separados por coma: 2025-06-20,2025-07-18",
    )
    parser.add_argument(
        "--strikes", "-k",
        required=False,
        type=int,
        default=None,
        help="Cantidad de strikes a cada lado del ATM (default: todos)",
    )
    parser.add_argument(
        "--type", "-t",
        required=False,
        choices=["ALL", "CALL", "PUT"],
        default="ALL",
        help="Tipo de contrato: ALL, CALL o PUT (default: ALL)",
    )
    return parser.parse_args()
```

- [ ] **Step 2: Reemplazar el bloque de ejecucion en main() con logica bifurcada**

Reemplazar el bloque desde `client = get_client()` hasta el final del bloque `try`:

```python
        client = get_client()

        if args.expirations:
            # -- Flujo multi-vencimiento ---------------------------------
            expirations = args.expirations
            console.print(f"    [dim]Vencimientos: {', '.join(str(e) for e in expirations)}[/dim]")

            raw_dict = fetch_multiple_expirations(
                symbol=args.symbol,
                expirations=expirations,
                contract_type=args.type,
                strike_count=args.strikes,
                client=client,
            )
            parsed = {exp: parse_option_chain(raw, exp) for exp, raw in raw_dict.items()}
            skew_df = calculate_iv_skew(parsed)

            total_calls = sum(len(calls) for calls, _ in parsed.values())
            total_puts  = sum(len(puts)  for _, puts  in parsed.values())

            table = Table(show_header=True, header_style="bold magenta", box=None)
            table.add_column("Metrica", style="cyan", min_width=22)
            table.add_column("Valor",   style="bold green")
            table.add_row("Total Calls",       str(total_calls))
            table.add_row("Total Puts",        str(total_puts))
            table.add_row("Vencimientos",      str(len(expirations)))
            table.add_row("Strikes en IV Skew", str(len(skew_df)))
            console.print(table)

            filepath = export_multiple_to_excel(parsed, skew_df, args.symbol)

        else:
            # -- Flujo single vencimiento (comportamiento original) -------
            if args.expiration is None:
                console.print("[bold red][ERROR][/bold red] Se requiere --expiration o --expirations")
                raise SystemExit(1)

            raw = fetch_option_chain(
                symbol=args.symbol,
                expiration=args.expiration,
                contract_type=args.type,
                strike_count=args.strikes,
                client=client,
            )
            calls_df, puts_df = parse_option_chain(raw, args.expiration)

            max_pain = calculate_max_pain(calls_df, puts_df)
            pc_ratio = calculate_pc_ratio(calls_df, puts_df)
            analysis = {"max_pain": max_pain, "pc_ratio": pc_ratio}

            table = Table(show_header=True, header_style="bold magenta", box=None)
            table.add_column("Metrica", style="cyan", min_width=22)
            table.add_column("Valor",   style="bold green")
            table.add_row("Calls encontradas",   str(len(calls_df)))
            table.add_row("Puts encontradas",    str(len(puts_df)))
            table.add_row("Max Pain Strike",     f"${max_pain['strike']:.2f}")
            table.add_row("P/C Ratio (Volumen)", f"{pc_ratio['volume_ratio']:.2f}")
            table.add_row("P/C Ratio (OI)",      f"{pc_ratio['oi_ratio']:.2f}")
            console.print(table)

            filepath = export_to_excel(calls_df, puts_df, args.symbol, args.expiration, analysis=analysis)

        console.print(f"\n[bold green][OK][/bold green] Abri el archivo: [underline]{filepath}[/underline]\n")
```

- [ ] **Step 3: Correr la suite completa**

```powershell
.\.venv\Scripts\python.exe -m pytest --tb=short -q
```

Resultado esperado: todos los tests pasan.

- [ ] **Step 4: Verificar que --help muestra los nuevos parametros**

```powershell
.\.venv\Scripts\python.exe main.py --help
```

Debe mostrar `--expirations` / `-E` en la lista de opciones.

- [ ] **Step 5: Commit**

```powershell
git add main.py
git commit -m "feat: add --expirations for multi-expiration mode with IV Skew sheet"
```

---

### CHECKPOINT B — Final

- [ ] **Suite completa con coverage**

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=src --cov=main --cov=config --cov-report=term-missing --cov-fail-under=85 -q
```

Resultado esperado: >= 85% coverage, todos los tests pasan.

- [ ] **Verificar --help del CLI**

```powershell
.\.venv\Scripts\python.exe main.py --help
```

- [ ] **Actualizar README con la seccion de multi-vencimiento**

Agregar en la seccion "Uso" del README:

```markdown
# Multiples vencimientos con IV Skew
python main.py -s SPY -E "2025-06-20,2025-07-18,2025-08-15"
```

- [ ] **Commit final**

```powershell
git add README.md
git commit -m "docs: update README with multi-expiration usage"
```
