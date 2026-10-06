# Servidor MCP para el Siglent SDS1104X-E — Diseño

Fecha: 2026-10-05
Estado: revisión 2 — incorpora la revisión con `mcp-builder` y el SDK `mcp` 2.3.0

## Objetivo

Exponer el osciloscopio SDS1104X-E (USBTMC, dialecto LeCroy X-Stream) como un
servidor MCP para que un agente LLM pueda:

1. **Depurar hardware**: configurar el equipo, capturar, medir, decodificar
   buses y ver la pantalla.
2. **Observar**: leer mediciones, formas de onda y bytes decodificados.
3. **Automatizar pruebas**: secuencias repetibles AWG → disparo → espera →
   captura → medición.
4. **Distribuirse públicamente**: instalable por la comunidad, con tools bien
   descritas, acotadas y probadas.

### Restricciones acordadas

- Solo transporte **USB (USBTMC)** sobre `osc_cli/device.py`. La herramienta
  LAN/VXI-11 de `tools/` queda fuera de este proyecto.
- **Todas las operaciones expuestas**; la seguridad se delega en las
  annotations MCP y en los permisos del cliente. No hay modo read-only.
- SDK oficial `mcp` (Python) `>=2.3,<3`, API `MCPServer`, transporte stdio.
- Prefijo de tools `siglent_`; servidor `siglent_sds1104xe_mcp`.
- El texto que imprime el CLI `osc` no cambia. Sí se corrigen bugs de
  comportamiento compartidos (ver «Correcciones en la capa de dispositivo»).

### Fuera de alcance

- Transporte LAN / VXI-11 y streamable HTTP.
- Leer el decodificador interno del equipo (no es accesible por USBTMC; se
  decodifica por software como hace el CLI).
- Gestión de licencias y demás funciones de `tools/`.

## Arquitectura

```
osc_cli/
  device.py        (existe, se corrige)  Oscilloscope: transporte USBTMC
  decoders.py      (existe)              decodificación UART/I2C/SPI
  imaging.py       (nuevo)               BMP → PNG solo con stdlib
  ops/             (nuevo)               lógica del dialecto → datos estructurados
    channel.py  timebase.py  trigger.py  acquisition.py  measure.py
    system.py   waveform.py  screen.py   decode.py       awg.py   misc.py
  commands/        (existe)              click: opciones → ops → texto
siglent_mcp/       (nuevo)
  server.py        instancia MCPServer, lifespan, registro de tools, main()
  session.py       conexión persistente, lock, reintentos, CHDR
  storage.py       OSC_DATA_DIR: rutas seguras, retención de archivos
  errors.py        decorador que mapea excepciones → ToolError
  models.py        TypedDict de retorno de cada tool
  tools/           un módulo por dominio, envoltorios delgados sobre ops
```

### Responsabilidades

- **`osc_cli/ops/*`** — no importa `click` ni `mcp`. Cada función recibe un
  `Oscilloscope` y devuelve dicts, números o bytes. Única fuente de verdad del
  protocolo. Los parsers toleran respuestas con cabecera corta (`C1:VDIV
  5.00E-01V`) y sin cabecera (`5.00E-01V`) mediante un helper
  `ops._parse.value_of(resp)`. `misc.py` agrupa math, display, cursor,
  contador y save/recall.
- **`osc_cli/commands/*`** — se adelgazan: parsean opciones, llaman `ops` y
  formatean exactamente el mismo texto que hoy.
- **`osc_cli/imaging.py`** — `bmp_to_png(data: bytes) -> bytes`. Soporta BMP
  sin comprimir de 16 (RGB565/555 con BI_BITFIELDS), 24 y 32 bpp, bottom-up y
  top-down; valida firma `BM` y tamaño declarado. El formato real de `SCDP` se
  confirma en el test de hardware.
- **`siglent_mcp/session.py`** — clase `Session`:
  - `run(fn, *args, retry: bool, timeout_ms: int | None = None)`. Adquiere el
    lock con `Lock.acquire(timeout=OSC_LOCK_TIMEOUT_S)` (default 120 s); si no
    lo obtiene lanza `ToolError("Equipo ocupado con otra operación…")`.
  - Conexión lazy y persistente. Al (re)conectar ejecuta `CHDR SHORT`.
  - Si `timeout_ms` se pasa, lo aplica solo durante esa llamada y restaura el
    anterior.
  - Reintento: **solo** si `retry=True` **y** el error es de transporte
    (`pyvisa.errors.VisaIOError`, `usb.core.USBError`, timeout). Entonces
    cierra, reconecta y reintenta una vez. Errores de parseo o de protocolo
    nunca se reintentan. Nunca hace `dev.reset()` USB.
  - Tras `siglent_reset`, `siglent_recall_setup` y `siglent_send_raw_command`
    vuelve a fijar `CHDR SHORT`.
  - Inyección de fábrica de dispositivos (tests). Entorno: `OSC_RESOURCE`,
    `OSC_TIMEOUT_MS`, `OSC_LOCK_TIMEOUT_S`.
- **`siglent_mcp/storage.py`** — raíz `OSC_DATA_DIR` (default
  `$XDG_DATA_HOME/siglent-mcp`, o `~/.local/share/siglent-mcp`). Las rutas de
  **salida** (`save_path`, directorio de CSV/JSON) se resuelven dentro de esa
  raíz y se rechaza cualquier ruta que escape de ella. Las rutas de
  **entrada** (`*_csv` de los decoders) pueden estar en cualquier lugar pero
  deben existir y ser archivos regulares. Retención: se conservan los últimos
  `OSC_KEEP_FILES` (default 20) archivos de cada tipo generado.
- **`siglent_mcp/errors.py`** — decorador `@tool_errors` aplicado a cada tool:
  `OscError`, `ValueError` (p. ej. «samples per bit» de `decoders.py`),
  `OSError` y errores de pyvisa → `ToolError` con mensaje accionable.
- **`siglent_mcp/models.py`** — un `TypedDict` por tipo de retorno, para que
  el SDK genere `outputSchema` (con `-> dict` lo envolvería en `{"result": …}`
  sin schema).
- **`siglent_mcp/tools/*`** — funciones **síncronas** (`def`); el SDK las
  ejecuta en un hilo de trabajo de anyio, sin bloquear el event loop. Tipos con
  `Literal` / `Annotated[..., Field(...)]`; annotations con
  `ToolAnnotations(read_only_hint=…, destructive_hint=…, idempotent_hint=…,
  open_world_hint=False)` de `mcp_types`. Las tools largas reciben `Context` y
  reportan progreso con `anyio.from_thread.run(ctx.report_progress, …)`.
- **`siglent_mcp/server.py`** — objeto `MCPServer("siglent_sds1104xe_mcp")` a
  nivel de módulo (necesario para `mcp dev`), con `instructions` que indican
  llamar primero a `siglent_get_status`, y un `lifespan` que cierra la
  conexión al terminar. `main()` ejecuta stdio. Los logs van a stderr.

### Correcciones en la capa de dispositivo (afectan también al CLI)

1. `read_binary_block` termina por **longitud declarada** con un plazo total
   (no por 10 000 iteraciones, que trunca sin aviso bloques > ~5 MB) y lanza
   `OscError` si la lectura queda corta.
2. `get_waveform` restaura `CHDR SHORT` en `try/finally`, y convierte las
   muestras con `array`/`memoryview` en lugar de listas de floats de Python.
3. Nuevo `read_raw_until(nbytes_from_header)` para `SCDP`: lectura con
   terminación desactivada hasta el tamaño declarado en la cabecera BMP
   (`query_raw` actual corta en el primer `0x0A`).
4. `query(cmd, retries=3)`: el número de reintentos internos es configurable;
   las operaciones no idempotentes y largas (`*CAL?`, `*TST?`) usan
   `retries=0`.
5. `osc timebase run` envía hoy `ARM`, que en LeCroy arma **una** captura.
   Pasa a usar `ops.acquisition.run` (ver abajo). El texto impreso no cambia.

### Empaquetado

En `pyproject.toml`:

- `requires-python = ">=3.10"` (exigido por `mcp` 2.3.0).
- `packages` añade `osc_cli.ops`, `siglent_mcp`, `siglent_mcp.tools`.
- Extras: `mcp = ["mcp>=2.3,<3"]`;
  `dev = ["pytest", "anyio", "mcp[cli]>=2.3,<3"]`.
- Script `siglent-mcp = "siglent_mcp.server:main"`.
- El CLI sigue sin depender de `mcp`.

Registro y pruebas manuales (README):

```bash
claude mcp add siglent -- siglent-mcp
mcp dev siglent_mcp/server.py   # MCP Inspector; requiere mcp[cli], uv y npx
```

## Catálogo de tools (34)

Lecturas y escrituras se consolidan en pares `get`/`set` con parámetros
opcionales: solo cambia lo que se pasa y el `set` devuelve el estado
resultante, leído del equipo.

**Criterio de annotations.** `read_only_hint` describe el efecto sobre el
**estado visible del equipo** (adquisición, configuración, salidas). Los
ajustes de transferencia que el servidor restaura (`CHDR`, `WFSU`) y los
archivos escritos en `OSC_DATA_DIR` no cuentan como modificación.
`open_world_hint=False` en todas. Columnas: RO = read_only, D = destructive,
I = idempotent, R = reintento automático tras error de transporte.

### Lectura

| Tool | RO | D | I | R | Devuelve |
|---|---|---|---|---|---|
| `siglent_identify()` | ✓ | – | ✓ | ✓ | fabricante, modelo, serie, firmware |
| `siglent_get_status()` | ✓ | – | ✓ | ✓ | estado de adquisición (`SAST?`), trigger mode, timebase, canales activos con su configuración |
| `siglent_get_channel(channel: 1-4 \| None)` | ✓ | – | ✓ | ✓ | configuración de uno o de los cuatro canales |
| `siglent_get_timebase()` | ✓ | – | ✓ | ✓ | tdiv, delay, sample_rate, memory, averages |
| `siglent_get_trigger()` | ✓ | – | ✓ | ✓ | mode, type, source, level, coupling |
| `siglent_measure(source: C1-C4, items: list[Param] \| None)` | ✓ | – | ✓ | ✓ | `{item: {value: float \| None, unit, note?}}` |
| `siglent_capture_screen(save_path: str \| None)` | ✓ | – | ✓ | ✓ | contenido: imagen PNG + texto con la ruta si se guardó |
| `siglent_read_counter()` | ✓ | – | ✓ | ✓ | frecuencia del contador |
| `siglent_get_awg()` | ✓ | – | ✓ | ✓ | onda, freq, amp, offset, fase, duty, salida, carga, modulación, sync, burst, sweep |
| `siglent_get_error()` | ✓ | – | ✓ | ✓ | último error del equipo |
| `siglent_wait_for_acquisition(timeout_s: 0.1-300 = 10)` | ✓ | – | ✓ | ✓ | `{triggered: bool, state, waited_s}` |

`Param` (de `measure.py`): PKPK, MAX, MIN, TOP, BASE, AMPL, MEAN, RMS, PER,
FREQ, RISE, FALL, WID, DUTY, OVSN, FPRE, CMEAN, CRMS. Default de `items`:
PKPK, FREQ, PER, MEAN, RMS, MIN, MAX, DUTY.

`siglent_wait_for_acquisition` consulta `SAST?` cada 50 ms **liberando el
lock entre consultas**, hasta que el estado indique captura completada
(`Stop` tras `single`, o `Trig'd`), o se agote el tiempo. Si `SAST?` no
resulta fiable en el hardware, se usa el bit 0 de `INR?` (nueva adquisición).
La elección se confirma en el test de hardware.

### Escritura sin riesgo

| Tool | RO | D | I | R | Notas |
|---|---|---|---|---|---|
| `siglent_set_channel(channel, enabled?, vdiv?, offset?, coupling?, bw_limit?, probe?, invert?, unit?, skew?)` | – | – | ✓ | ✓ | coupling ∈ A1M/D1M/A50/D50/GND; bw_limit ∈ OFF/20M/200M; unit ∈ V/A |
| `siglent_set_timebase(tdiv?, delay?, memory?, averages?)` | – | – | ✓ | ✓ | la descripción avisa del coste de memorias grandes en `capture_waveform` |
| `siglent_set_trigger(mode?, type?, source?, level?, coupling?)` | – | – | ✓ | ✓ | mode ∈ AUTO/NORM/SINGLE/STOP; type ∈ EDGE/SERIAL/PULSE/VIDEO/SLOPE/PATTERN/DROP/INTV/RUNT; source ∈ C1-C4/EXT/LINE; coupling ∈ DC/AC/HFREJ/LFREJ |
| `siglent_control_acquisition(action: run \| stop \| single \| force)` | – | – | – | – | ver mapeo abajo |
| `siglent_capture_waveform(sources: list[C1-C4], max_points=500, save_csv=True)` | – | – | ✓ | ✓ | ver «Forma de onda» |
| `siglent_decode_uart(rx, baud=115200, bits=8, parity=NONE, stop_bits=1.0, polarity=HIGH, msb_first=False, threshold?, freeze=True, csv_path?, limit=200, offset=0)` | – | – | ✓ | ✓ | frames `{time, value, ascii, errors}` + texto ASCII de la página |
| `siglent_decode_i2c(scl=C1, sda=C2, threshold?, freeze=True, scl_csv?, sda_csv?, limit=200, offset=0)` | – | – | ✓ | ✓ | transacciones `{time, address, read, data, acks, repeated_start}` |
| `siglent_decode_spi(clk=C1, mosi?, miso?, cs?, bits=8, cpol=0, cpha=0, lsb_first=False, threshold?, freeze=True, *_csv?, limit=200, offset=0)` | – | – | ✓ | ✓ | frames `{time, mosi, miso}`; exige mosi o miso |
| `siglent_configure_uart_trigger(rx=C1, tx?, baud=115200, parity=NONE, stop_bits=1.0, polarity=HIGH)` | – | – | ✓ | ✓ | `TRSE SERIAL` + `TRIG_UART:*` |
| `siglent_configure_i2c_trigger(scl=C1, sda=C2)` | – | – | ✓ | ✓ | `TRIG_IIC:*` |
| `siglent_configure_spi_trigger(clk=C1, miso=C2, mosi=C3, cs=C4)` | – | – | ✓ | ✓ | `TRIG_SPI:*` |
| `siglent_set_math(function?, offset?, scale?)` | – | – | ✓ | ✓ | function ∈ FX/FY/FZ/ADD/SUB/MUL/DIV/FFT |
| `siglent_set_display(grid?, intensity?, menu?, cursor_mode?)` | – | – | ✓ | ✓ | grid ∈ FULL/HALF/OFF; menu ∈ ON/OFF; cursor_mode ∈ OFF/TRACK/HABS/HREL/VABS/VREL |
| `siglent_set_counter(enabled: bool)` | – | – | ✓ | ✓ | `FCNT STATE,ON/OFF` |
| `siglent_save_setup(path)` | – | – | ✓ | ✓ | archivo **en el equipo** (`STORE_SETUP`) |

Mapeo de `siglent_control_acquisition`:
- `run` → `TRMD <modo previo>`: la sesión recuerda el último modo continuo
  (AUTO o NORM) visto o fijado; si no conoce ninguno usa AUTO.
- `stop` → `STOP`.
- `single` → `TRMD SINGLE`. Usar después `siglent_wait_for_acquisition`.
- `force` → `*TRG`.

`freeze=True` en los decoders y una lista de varias `sources` en
`capture_waveform` envían `STOP` para que todos los canales provengan de la
misma adquisición. El equipo **queda en STOP**; la respuesta incluye
`acquisition_stopped: true` y una nota para reanudar con
`siglent_control_acquisition(run)`. Con rutas `*_csv` los decoders no tocan el
equipo.

**Paginación de decoders.** `limit` 1–2000 (default 200), `offset` ≥ 0. La
respuesta incluye `total`, `count`, `offset`, `has_more`, `next_offset` y
`json_path` (resultado completo guardado en `OSC_DATA_DIR`). Si no hay frames:
lista vacía + diagnóstico (niveles min/max, umbral usado, sugerencias de
baud/umbral/canal).

### Escritura con riesgo — `destructive_hint=True`

| Tool | RO | D | I | R | Motivo / notas |
|---|---|---|---|---|---|
| `siglent_recall_setup(path)` | – | ✓ | ✓ | – | sobrescribe toda la configuración; luego fija `CHDR SHORT` |
| `siglent_set_awg(enabled?, wave?, freq?, amp?, offset?, phase?, duty?, load?, arb?, modulation?, sync?)` | – | ✓ | ✓ | ✓ | inyecta señal. wave ∈ SINE/SQUARE/RAMP/PULSE/NOISE/ARB/DC; load ∈ HZ/50; arb ∈ formas del equipo |
| `siglent_set_awg_burst(enabled?, cycles?, period?)` | – | ✓ | ✓ | ✓ | inyecta señal |
| `siglent_set_awg_sweep(enabled?, start?, stop?, time?, direction?)` | – | ✓ | ✓ | ✓ | inyecta señal; direction ∈ UP/DOWN |
| `siglent_reset()` | – | ✓ | ✓ | – | `*RST`; luego fija `CHDR SHORT` |
| `siglent_run_selftest()` | – | ✓ | – | – | `*TST?`, `timeout_ms=120000`, `retries=0`, progreso |
| `siglent_calibrate()` | – | ✓ | – | – | `*CAL?`, `timeout_ms=120000`, `retries=0`, progreso |
| `siglent_send_raw_command(command, expect_response: bool)` | – | ✓ | – | – | SCPI arbitrario; luego fija `CHDR SHORT`. La descripción resume el dialecto LeCroy y advierte que cambiar `CHDR` lo revierte el servidor |

## Forma de onda (`siglent_capture_waveform`)

1. **Tamaño previo.** Para cada fuente se consulta el número de puntos
   (`SANU? Cn`). Límite `OSC_MAX_SAMPLES` (default 2 000 000 por canal).
   - Si se supera, se intenta `WFSU SP,<k>` (sparsing en el equipo) para
     traer como máximo el límite. Si el test de hardware demuestra que el
     firmware ignora `SP`, se rechaza la captura con `ToolError`: «La memoria
     actual (N puntos) excede el límite; reduce la memoria con
     `siglent_set_timebase(memory=…)` o ajusta `OSC_MAX_SAMPLES`».
2. **Transferencia.** `timeout_ms` por llamada proporcional al tamaño
   (5 s + 2 s por millón de puntos). Progreso reportado por canal.
3. **Procesamiento en streaming.** Los códigos ADC (`int8`) se mantienen en
   un `array`. Las estadísticas (`min`, `max`, `mean`, `rms`, `vpp`) se
   calculan con un histograma de 256 códigos, sin crear listas de floats.
   También se devuelven `n`, `sample_rate`, `duration`, `vdiv`, `offset` y
   `horz_interval`.
4. **Diezmado min/max.** `max_points` en el rango 2–5000 (default 500):
   `max_points // 2` buckets; de cada bucket se emiten el mínimo y el máximo
   en orden temporal como pares `[time, voltage]`. Si `n <= max_points` se
   devuelven todas las muestras.
5. **CSV.** Si `save_csv`, se escribe en streaming `index,voltage,time` (el
   formato de `osc waveform capture`, compatible con los decoders) en
   `OSC_DATA_DIR`, con retención. Se devuelve la ruta absoluta.

Retorno: `{sources: {C1: {...stats, points, csv_path?}, …},
acquisition_stopped: bool}`.

## Pantalla (`siglent_capture_screen`)

`SCDP` → `read_raw_until` (tamaño de la cabecera BMP) → validación →
`imaging.bmp_to_png` → `[Image(data=png, format="png"), texto con la ruta]`.
Es contenido no estructurado: no lleva `outputSchema`.

## Manejo de errores

| Situación | Comportamiento |
|---|---|
| Sin dispositivo / sin permisos | «Osciloscopio no encontrado. Verifica que esté encendido y conectado por USB, y que esté instalada la regla udev (`sudo ./install-udev.sh`).» |
| Error de transporte, tool con R ✓ | reconexión + un reintento; si falla: «El equipo no responde. Si persiste, apágalo y enciéndelo físicamente (replugar el USB no basta).» |
| Error de transporte, tool sin R | sin reintento: «La operación pudo haberse ejecutado o no; consulta `siglent_get_status` antes de repetirla.» |
| Lock ocupado más de `OSC_LOCK_TIMEOUT_S` | «Equipo ocupado con otra operación; reintenta en unos segundos.» |
| Argumento inválido | rechazado por el schema antes de tocar el equipo |
| Ruta fuera de `OSC_DATA_DIR` o CSV inexistente | `ToolError` indicando la raíz permitida o la ruta que falta |
| Medición inválida (`****` o no numérica) | `value: null` + `note` sugiriendo ajustar vdiv/tdiv/trigger |
| Captura demasiado grande | ver «Forma de onda», paso 1 |
| BMP truncado o con cabecera inválida | `ToolError` con bytes recibidos/esperados |

## Pruebas

Se usa pytest con el plugin de anyio (el SDK está basado en anyio).

1. **Capa de dispositivo** con un transporte VISA falso: `read_binary_block`
   con más de 10 000 trozos y con lectura corta; `get_waveform` restaura CHDR
   tras un timeout; `read_raw_until` con bytes `0x0A` en los píxeles;
   `query(retries=0)`.
2. **Unitarias de `ops/`** con `tests/fakes.py::FakeOscilloscope`: registra
   `write`/`query` y responde desde un dict. Cada op verifica los comandos
   exactos enviados y el resultado, con respuestas con y sin cabecera.
   Waveform con bloque `WF?` sintético: estadísticas por histograma frente a
   un cálculo directo, diezmado (glitch de una muestra sobrevive, `n` impar,
   `max_points=2`, `n <= max_points`), CSV en streaming, límite de muestras.
3. **`imaging`**: BMP de 16/24/32 bpp, bottom-up y top-down → PNG; se valida
   firma, IHDR y píxeles descomprimidos.
4. **Regresión del CLI**: antes de refactorizar cada grupo se fija su salida
   con `CliRunner` + fake; tras el refactor debe ser idéntica.
5. **`Session`**: reconexión + reintento solo para errores de transporte con
   `retry=True`; ningún reintento sin `R` ni ante errores de parseo; `CHDR
   SHORT` al reconectar y tras reset/recall/raw; lock ocupado → `ToolError`;
   `timeout_ms` por llamada restaurado.
6. **`storage`**: rechazo de rutas que escapan de la raíz; retención.
7. **Servidor en memoria** con `async with Client(server)` de `mcp.client`,
   usando `Session` con el fake:
   - snapshot de `tools/list`: 34 tools con nombre, annotations (la tabla de
     este spec) y `outputSchema`;
   - llamadas representativas por dominio con resultado estructurado;
   - `siglent_capture_screen` devuelve imagen PNG;
   - paginación de decoders (`has_more`, `next_offset`);
   - errores mapeados a `ToolError`.
8. **stdout limpio**: el servidor lanzado como subproceso stdio solo emite
   JSON-RPC por stdout.
9. **Hardware real** (`tests/hw/`, solo con `OSC_HW=1`): identify, status,
   measure sobre la señal de calibración (1 kHz), capture, screenshot (confirma
   bpp de `SCDP`), `WFSU SP`, `SAST?`/`INR?` tras `single`, `TRMD` frente a
   `ARM` para `run`, y un ciclo set/get de canal que restaura el estado.
10. **Evaluación mcp-builder** (opcional, tras implementar): `evaluation.xml`
    con ~10 preguntas realistas, ejecutada por el usuario con
    `scripts/evaluation.py` contra el equipo real.

`tests/test_decoders.py` se migra a pytest y debe seguir pasando.

## Orden de implementación sugerido

1. Infraestructura de tests (pytest + anyio, fakes) y migración de
   `test_decoders.py`.
2. Correcciones de `device.py` con sus tests.
3. `imaging.py`.
4. Refactor a `ops/` grupo por grupo, con tests de regresión del CLI.
5. `siglent_mcp/session.py`, `storage.py`, `errors.py`, `models.py`.
6. `siglent_mcp/tools/*` + `server.py`, con tests en memoria.
7. Empaquetado, README y smoke test de hardware.
