# Design — Options Alert Monitor

Fecha: 2026-06-26
Estado: aprobado para planificacion

## Objetivo

Agregar al proyecto un monitor continuo que vigile cadenas de opciones en vivo
y dispare alertas cuando se cruzan umbrales definidos por el usuario. Dos clases
de alerta:

- **Senales de mercado**: IV alta/baja, P/C ratio extremo, spread ancho, precio
  cerca de Max Pain, etc.
- **Umbrales personalizados**: el usuario define sus propias reglas en un archivo
  YAML, sin tocar codigo.

Entrega de alertas por **toast de Windows** + **Telegram** (para enterarse lejos
de la PC). Email queda como backend futuro detras de la misma interfaz.

## No-objetivos (v1)

- Alertas de calidad de datos como feature explicito (se cubren indirectamente:
  los contratos sin cotizacion se marcan y se ignoran para no generar falsos
  positivos, pero no se notifican).
- Expresiones arbitrarias en el YAML (sin `eval` / `df.query` libre).
- Backend de email (interfaz lista, implementacion despues).
- Persistencia historica de alertas a base de datos.

## Arquitectura

Flujo del monitor:

```
fetch -> parse -> normalize -> analyze -> evaluar reglas -> filtrar cooldown -> notificar -> sleep(interval) -> repeat
```

Entry point nuevo `monitor.py`, separado de `main.py` (que sigue siendo el
exportador one-shot a Excel). El monitor reusa fetcher, parser y analyzer
existentes; agrega normalizador, motor de reglas y notificadores.

### Componentes

#### `src/normalizer.py` (capa de normalizacion)

Funcion pura, sin red. Toma los DataFrames del parser mas el precio del
subyacente y devuelve DataFrames enriquecidos + un dict de metricas chain-level.

Responsabilidades:

1. **Canonicalizacion de nombres de campo.** Mapea los nombres crudos de Schwab
   a nombres canonicos del proyecto en un unico lugar documentado. Acepta alias
   conocidos para no romper si el campo real difiere de la suposicion actual:
   - `impliedVolatility` o `volatility` -> `iv`
   - `volume` o `totalVolume` -> `volume`
   Este es el unico punto a corregir cuando llegue la primera respuesta real de
   la API (OAuth pendiente impide confirmarlo en vivo hoy).
2. **Centinelas.** Reemplaza valores centinela de Schwab (`-999`, no-finitos) en
   griegas e IV por `NaN`.
3. **Flag `no_quote`.** `no_quote = (bid <= 0) & (ask <= 0)`. Los contratos que
   no cotizan se marcan; el motor de reglas los ignora por defecto en reglas
   contract-level (principal fuente de falsos positivos).
4. **Columnas derivadas:**
   - `mid = (bid + ask) / 2` (NaN si `no_quote`)
   - `spread_pct = spread / mid`
   - `moneyness = strike / underlying_price` (requiere precio del subyacente)
5. **Escala de IV.** Estandariza `iv` a fraccion decimal (`0.30` = 30%) con una
   convencion documentada y configurable (`IV_INPUT_SCALE` = `percent` |
   `decimal`, default `percent` segun formato real de Schwab). Asi todas las
   reglas YAML expresan IV en una unica unidad. **Tarea de verificacion**: con la
   primera respuesta real confirmar escala y nombre de campo, ajustar el default.

Interfaz:

```python
def normalize_chain(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    underlying_price: float,
) -> tuple[pd.DataFrame, pd.DataFrame]: ...
```

Metricas chain-level (P/C ratio, max pain, distancia a max pain) se calculan en
el monitor reusando `analyzer`, no aca, para mantener el normalizador enfocado
en por-contrato.

#### `src/parser.py` (cambio menor)

Extraer `underlyingPrice` del dict crudo y exponerlo, para no obligar al
normalizador a volver al raw (mantiene limpio el limite "el normalizador recibe
DataFrames + un float"). Opciones de implementacion a decidir en el plan: que
`parse_option_chain` devuelva tambien el precio, o una funcion auxiliar
`extract_underlying_price(raw) -> float`.

#### `src/rules.py` (motor de reglas)

Carga `rules.yaml` y evalua contra la cadena normalizada + metricas chain-level.

Dos scopes de regla:

- **contract** (por fila): selectores opcionales (`type`: call/put, `strike` o
  rango, `moneyness`) + `field` / `operator` / `value`. Ignora filas `no_quote`
  por defecto.
- **chain** (agregado): compara una metrica global unica.

Operadores: `gt`, `lt`, `gte`, `lte`, `eq`, `between`, `outside`.

Campos disponibles:

- contract: `strike`, `bid`, `ask`, `mid`, `spread`, `spread_pct`, `last`,
  `volume`, `openInterest`, `delta`, `gamma`, `theta`, `vega`, `iv`, `moneyness`,
  `inTheMoney`
- chain: `pc_volume_ratio`, `pc_oi_ratio`, `max_pain_strike`, `underlying_price`,
  `distance_to_max_pain`, `distance_to_max_pain_pct`

Produce objetos `Alert`:

```python
@dataclass(frozen=True)
class Alert:
    rule_name: str
    symbol: str
    scope: str          # "contract" | "chain"
    subject: str        # ej "SPY 600C 2026-07-17" o "chain"
    field: str
    value: float
    threshold: ...      # numero o par para between/outside
    timestamp: datetime
    message: str
```

Validacion del YAML al cargar: campos/operadores desconocidos -> error claro
(reusar patron `ConfigError`), no fallo silencioso.

Ejemplo `rules.yaml`:

```yaml
rules:
  - name: high_iv_calls
    scope: contract
    type: CALL
    field: iv
    operator: gt
    value: 0.30
    message: "IV de call por encima de 30%"

  - name: wide_spread
    scope: contract
    field: spread_pct
    operator: gt
    value: 0.10

  - name: put_call_extreme
    scope: chain
    field: pc_volume_ratio
    operator: gt
    value: 1.5

  - name: near_max_pain
    scope: chain
    field: distance_to_max_pain_pct
    operator: lt
    value: 0.005
```

#### `src/notifier.py` (notificadores)

Interfaz comun:

```python
class Notifier(Protocol):
    def send(self, alert: Alert) -> None: ...
```

Backends:

- `DesktopNotifier`: toast de Windows (dependencia liviana mantenida, ej
  `windows-toasts`). Degrada silenciosamente si no esta disponible.
- `TelegramNotifier`: POST a la Bot API con `requests`. Lee
  `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` de config/.env. Si Telegram esta
  habilitado y faltan credenciales -> `ConfigError`. **Nunca** loguear el token.
- `CompositeNotifier`: despacha a todos los backends habilitados; un fallo en uno
  no tumba a los demas (loguea y sigue).

Email: no se implementa en v1, pero la interfaz `Notifier` deja el hueco trivial.

#### Estado / cooldown

`AlertState` en memoria, semantica **edge-triggered**:

- Una regla dispara solo cuando la condicion pasa de falsa a verdadera para un
  sujeto dado (`(rule_name, subject)`).
- Se re-arma cuando la condicion se despeja (vuelve a falsa).
- Guard de intervalo minimo opcional (`min_interval`, default ~p.ej. 5 min) para
  evitar parpadeo si el valor oscila alrededor del umbral.

Esto evita el spam que produciria notificar en cada ciclo de polling (60s).
Persistencia a disco: no en v1 (proceso de larga duracion; reiniciar re-arma).

#### `monitor.py` (entry point + loop)

CLI:

- `--symbol` / `-s` (uno o varios)
- `--expiration` / `-e` o `--expirations` / `-E`
- `--rules` (path a `rules.yaml`, default `rules.yaml`)
- `--interval` (default `config.REFRESH_INTERVAL`)
- `--type` (ALL/CALL/PUT)
- `--market-hours-only` (opcional, default off): si on, salta ciclos fuera de
  horario de mercado US para no gastar llamadas ni alertar sobre quotes stale.

Loop por ciclo:

1. Para cada symbol/expiration: `fetch -> parse -> extraer underlying -> normalize`.
2. Calcular metricas chain-level con `analyzer`.
3. Evaluar reglas -> lista de `Alert`.
4. Filtrar por `AlertState` (edge-triggered + cooldown).
5. Notificar las que pasan via `CompositeNotifier`.
6. `sleep(interval)`.

Robustez:

- Errores de API (red, rate limit, expiracion) -> loguear y continuar al
  proximo ciclo, no abortar.
- schwab-py refresca el access token (~30 min) transparente mientras el refresh
  token (7 dias) sea valido. Al expirar el refresh, mostrar mensaje claro de
  re-auth (correr `main.py` para re-loguear). No hay re-auth dentro del loop.
- `Ctrl+C` corta limpio (resumen final opcional).

### Configuracion nueva (`config.py` / `.env`)

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `IV_INPUT_SCALE` (default `percent`)
- `ALERT_MIN_INTERVAL` (segundos, default p.ej. 300)
- Flags de habilitacion de canales (ej `ALERTS_DESKTOP`, `ALERTS_TELEGRAM`)

`validate_config` gana validacion condicional: si un canal esta habilitado,
exigir sus credenciales con `ConfigError`.

## Manejo de errores (resumen)

| Caso | Comportamiento |
|------|----------------|
| Falla API en un ciclo | Log + continuar proximo ciclo |
| Refresh token expirado (7 dias) | Mensaje claro de re-auth, cortar |
| Credencial de canal faltante | `ConfigError` al iniciar |
| YAML invalido | `ConfigError` con detalle del campo/operador |
| Fallo de un notificador | Log + seguir con los demas |
| Contrato `no_quote` | Ignorado en reglas contract por defecto |

## Testing

Mantener >= 85% coverage. Sin red real en tests.

- `normalizer`: canonicalizacion de alias, centinelas -> NaN, flag `no_quote`,
  `mid` / `spread_pct` / `moneyness`, conversion de escala de IV
  (percent->decimal y decimal passthrough).
- `rules`: cada operador, scope contract vs chain, selectores
  (type/strike/moneyness), exclusion de `no_quote`, validacion de YAML invalido.
- `notifier`: `TelegramNotifier` con `requests` mockeado (assert payload sin
  token en logs), `DesktopNotifier` con toast mockeado, `CompositeNotifier`
  tolerante a fallo de un backend.
- `AlertState`: edge-trigger (no re-dispara mientras la condicion siga
  verdadera), re-arme al despejar, guard de `min_interval`.
- `monitor`: un ciclo con cliente/fetch mockeados (loop iteracion unica).

## Reglas del proyecto (CLAUDE.md) a respetar

- Type hints en todas las funciones nuevas.
- Sin emojis ni tildes en source Python (Windows cp1252).
- Errores al usuario nunca incluyen `response.text` ni contenido de token;
  `log.debug()` para diagnostico sensible.
- `ConfigError` para validacion de config.
- Conventional commits (`feat:`, `test:`, etc.).

## Decisiones abiertas para el plan

- Forma exacta de exponer `underlying_price` desde el parser (retorno extendido
  vs helper).
- Eleccion final de libreria de toast de Windows (mantenimiento/CVE).
- Valor default de `ALERT_MIN_INTERVAL`.
