# Servidor MCP para el Siglent SDS1104X-E — Diseño

Fecha: 2026-10-05
Estado: aprobado en conversación, pendiente de revisión escrita

## Objetivo

Exponer el osciloscopio SDS1104X-E (USBTMC, dialecto LeCroy X-Stream) como un
servidor MCP para que un agente LLM pueda:

1. **Depurar hardware**: configurar el equipo, capturar, medir, decodificar
   buses y ver la pantalla.
2. **Observar**: leer mediciones, formas de onda y bytes decodificados.
3. **Automatizar pruebas**: secuencias repetibles AWG → captura → medición.
4. **Distribuirse públicamente**: instalable por la comunidad, con tools bien
   descritas y probadas.

### Restricciones acordadas

- Solo transporte **USB (USBTMC)** sobre `osc_cli/device.py`. La herramienta
  LAN/VXI-11 de `tools/` queda fuera de este proyecto.
- **Todas las operaciones expuestas**; la seguridad se delega en las
  annotations MCP (`readOnlyHint`, `destructiveHint`, `idempotentHint`) y en
  los permisos del cliente. No hay modo read-only.
- SDK oficial `mcp` (Python) `>=2.3,<3`, API `MCPServer`, transporte stdio.
- La salida del CLI `osc` existente no cambia.

### Fuera de alcance

- Transporte LAN / VXI-11 y streamable HTTP.
- Leer el decodificador interno del equipo (no es accesible por USBTMC; se
  decodifica por software como hace el CLI).
- Gestión de licencias y demás funciones de `tools/`.

## Arquitectura

```
osc_cli/
  device.py        (existe)  Oscilloscope: transporte USBTMC
  decoders.py      (existe)  decodificación UART/I2C/SPI por software
  imaging.py       (nuevo)   BMP → PNG solo con stdlib (zlib + struct)
  ops/             (nuevo)   lógica del dialecto; devuelve datos estructurados
    channel.py  timebase.py  trigger.py  measure.py  system.py
    waveform.py  screen.py   decode.py   awg.py      misc.py
  commands/        (existe)  click: parseo de opciones → ops → formato de texto
osc_mcp/           (nuevo)
  server.py        instancia MCPServer, registro de tools, main()
  session.py       conexión persistente + lock + reconexión
  tools/           un módulo por dominio, envoltorios delgados sobre ops
```

### Responsabilidades

- **`osc_cli/ops/*`**: no importa `click` ni `mcp`. Cada función recibe un
  `Oscilloscope` y devuelve dicts, números o bytes, por ejemplo
  `channel.get(o, 1) -> {"channel": 1, "enabled": True, "vdiv": 0.5,
  "offset": 0.0, "coupling": "D1M", "bw_limit": "OFF", "probe": 10.0,
  "invert": False, "unit": "V", "skew": 0.0}`. Es la única fuente de verdad
  sobre los comandos SCPI/LeCroy. `misc.py` agrupa math, display, cursor,
  contador y save/recall.
- **`osc_cli/commands/*`**: se adelgazan. Parsean las opciones de click,
  llaman a `ops`, y formatean exactamente el mismo texto que hoy.
- **`osc_cli/imaging.py`**: `bmp_to_png(data: bytes) -> bytes`. Soporta BMP
  sin comprimir de 24 y 32 bpp (bottom-up y top-down), que es lo que devuelve
  `SCDP` (800×480).
- **`osc_mcp/session.py`**: clase `Session` con `run(fn, *args)`. Bajo un
  `threading.Lock` abre el `Oscilloscope` la primera vez (lazy), ejecuta
  `fn(osc, *args)` y lo reutiliza en llamadas siguientes. Ante `OscError` o un
  error de E/S cierra la conexión, reconecta y reintenta **una sola vez**.
  Nunca hace `dev.reset()` USB. Admite inyectar una fábrica de dispositivos
  (para tests) y lee `OSC_RESOURCE` / `OSC_TIMEOUT_MS` del entorno.
- **`osc_mcp/tools/*`**: declaran tipos con `Literal` / `Annotated[..., Field]`
  para generar schemas precisos, llaman `session.run(ops.x, ...)` y devuelven
  resultados estructurados. Las descripciones (docstrings) son la documentación
  que lee el agente: qué hace, unidades (V, s, Hz) y cuándo usarla.
- **`osc_mcp/server.py`**: crea `MCPServer("siglent-sds1104x-e")`, registra
  todas las tools e instrucciones del servidor (recomendar llamar
  `osc_get_status` primero) y expone `main()` que ejecuta stdio.

### Empaquetado

En `pyproject.toml`:

- `packages` añade `osc_cli.ops` y `osc_mcp`, `osc_mcp.tools`.
- Extra `mcp = ["mcp>=2.3,<3"]` y extra `dev = ["pytest", "pytest-asyncio"]`
  (más `mcp` para los tests del servidor).
- Script `osc-mcp = "osc_mcp.server:main"`.
- El CLI sigue sin depender de `mcp`.

Registro en clientes (documentado en README):

```bash
claude mcp add siglent -- osc-mcp
mcp dev osc_mcp/server.py      # MCP Inspector
```

## Catálogo de tools (31)

Prefijo `osc_`. Lecturas y escrituras se consolidan en pares `get`/`set` con
parámetros opcionales: solo se cambian los que se pasan; el `set` devuelve el
estado resultante (leído del equipo tras escribir).

### Solo lectura — `readOnlyHint=True`

| Tool | Devuelve |
|---|---|
| `osc_identify()` | fabricante, modelo, serie, firmware |
| `osc_get_status()` | run/stop, timebase, trigger, canales activos con su configuración |
| `osc_channel_get(channel: 1-4 \| None)` | configuración de un canal o de los cuatro |
| `osc_timebase_get()` | tdiv, delay, sample_rate, memory, averages |
| `osc_trigger_get()` | mode, type, source, level, coupling |
| `osc_measure(source: C1-C4, items: list[Param] = default)` | `{item: {"value": float \| None, "unit": str, "note"?: str}}`. Default: PKPK, FREQ, PER, MEAN, RMS, MIN, MAX, DUTY |
| `osc_screenshot(save_path: str \| None)` | imagen PNG (+ ruta si se guarda) |
| `osc_counter_read()` | frecuencia del contador |
| `osc_awg_get()` | onda, frecuencia, amplitud, offset, fase, duty, salida, carga, modulación, sync |
| `osc_system_error()` | último error del equipo |

### Escritura sin riesgo — `readOnlyHint=False`, `destructiveHint=False`

| Tool | Notas |
|---|---|
| `osc_channel_set(channel, enabled?, vdiv?, offset?, coupling?, bw_limit?, probe?, invert?, unit?, skew?)` | coupling ∈ A1M/D1M/A50/D50/GND; bw_limit ∈ OFF/20M/200M; unit ∈ V/A. Idempotente |
| `osc_timebase_set(tdiv?, delay?, memory?, averages?)` | idempotente |
| `osc_trigger_set(mode?, type?, source?, level?, coupling?)` | mode ∈ AUTO/NORM/SINGLE/STOP; type ∈ EDGE/SERIAL/PULSE/VIDEO/SLOPE/PATTERN/DROP/INTV/RUNT; source ∈ C1-C4/EXT/LINE; coupling ∈ DC/AC/HFREJ/LFREJ. Idempotente |
| `osc_acquisition(action: run \| stop \| single \| force)` | force = disparo forzado |
| `osc_capture_waveform(source, max_points=500, csv_dir?)` | ver «Forma de onda» |
| `osc_decode_uart(rx, baud, bits, parity, stop_bits, polarity, msb_first, threshold?, freeze=True, csv_path?)` | frames `{time, value, ascii, errors}` + texto ASCII |
| `osc_decode_i2c(scl, sda, threshold?, freeze=True, scl_csv?, sda_csv?)` | transacciones `{time, address, read, data, acks, repeated_start}` |
| `osc_decode_spi(clk, mosi?, miso?, cs?, bits, cpol, cpha, lsb_first, threshold?, freeze=True, *_csv?)` | frames `{time, mosi, miso}` |
| `osc_decode_configure(protocol: uart \| i2c \| spi, ...)` | configura el disparo serie del equipo |
| `osc_math_set(function?, offset?, scale?)` | |
| `osc_display_set(grid?, intensity?, menu?, cursor_mode?)` | |
| `osc_counter_set(enabled: bool)` | |
| `osc_setup_save(path)` / `osc_setup_recall(path)` | archivo en el equipo |

Las tools de decode con `freeze=True` envían `STOP` para que todos los canales
provengan de la misma adquisición; por eso no son read-only. Con rutas `*_csv`
decodifican archivos sin tocar el equipo.

### Escritura con riesgo — `destructiveHint=True`

| Tool | Motivo |
|---|---|
| `osc_awg_set(enabled?, wave?, freq?, amp?, offset?, phase?, duty?, load?, arb?, modulation?, sync?)` | inyecta señal al circuito. wave ∈ SINE/SQUARE/RAMP/PULSE/NOISE/ARB/DC; load ∈ HZ/50; arb ∈ formas del equipo |
| `osc_awg_burst(enabled?, cycles?, period?)` | inyecta señal |
| `osc_awg_sweep(enabled?, start?, stop?, time?, direction?)` | inyecta señal |
| `osc_reset()` | `*RST` borra la configuración |
| `osc_selftest()` / `osc_calibrate()` | desconectan entradas, tardan |
| `osc_raw_command(command, expect_response: bool)` | SCPI arbitrario; la descripción resume el dialecto LeCroy y sus diferencias con el SCPI Siglent |

`system header` (CHDR) **no** se expone: el servidor y `get_waveform` lo
gestionan internamente y cambiarlo rompe el parseo.

## Flujo de datos

```
agente → tool (valida args) → Session.run → lock → osc (lazy)
       → ops.<fn>(osc, ...) → dict → resultado estructurado → agente
```

### Forma de onda (`osc_capture_waveform`)

1. `ops.waveform.capture(o, source)` usa `Oscilloscope.get_waveform()` y
   obtiene la memoria completa (hasta ~1.4M puntos).
2. Estadísticas sobre **todas** las muestras: `n`, `sample_rate`, `duration`,
   `min`, `max`, `mean`, `rms`, `vpp`, más `vdiv`, `offset`, `horz_interval`.
3. Diezmado min/max: `max_points` (default 500, rango 2–5000) → `max_points/2`
   buckets; de cada bucket se emiten el mínimo y el máximo en orden temporal,
   como pares `[time, voltage]`. Si `n <= max_points` se devuelven todas.
4. CSV completo `index,voltage,time` (mismo formato que `osc waveform capture`,
   compatible con las tools de decode) en `csv_dir` o, si se omite, en un
   directorio temporal propio del servidor. Se devuelve la ruta absoluta.

### Pantalla (`osc_screenshot`)

`SCDP` → BMP 800×480 → `imaging.bmp_to_png` → `Image(data=png, format="png")`.
Con `save_path` también se escribe el PNG en disco.

## Manejo de errores

Los errores se lanzan como `ToolError` con un mensaje accionable; nunca un
traceback. Los logs van a stderr (stdout es del protocolo stdio).

| Situación | Comportamiento |
|---|---|
| Sin dispositivo / sin permisos | «Osciloscopio no encontrado. Verifica que esté encendido y conectado por USB, y que esté instalada la regla udev (`sudo ./install-udev.sh`).» |
| Timeout / E/S | reconexión + un reintento; si falla: «El equipo no responde. Si persiste, apágalo y enciéndelo físicamente (replugar el USB no basta).» |
| Argumento inválido | rechazado por el schema antes de tocar el equipo |
| Medición inválida (`****` o no numérica) | `value: null`, `note` sugiriendo ajustar vdiv/tdiv/trigger |
| Decode sin frames | lista vacía + diagnóstico: niveles min/max, umbral usado, sugerencia (baud, umbral, canal) |

Un único lock global serializa el acceso: el equipo atiende un comando a la
vez y las capturas largas simplemente bloquean las llamadas siguientes.

## Pruebas

1. **Unitarias de `ops/`** con `tests/fakes.py::FakeOscilloscope`: registra
   `write`/`query`/`query_raw` y responde desde un dict configurable. Cada op
   verifica los comandos exactos enviados y el resultado. Un bloque `WF?`
   sintético (WAVEDESC 346 bytes + muestras) prueba estadísticas, diezmado (un
   glitch de una muestra debe sobrevivir) y CSV.
2. **`imaging`**: BMP pequeño generado en el test → PNG; se valida firma, IHDR
   y píxeles descomprimidos con zlib.
3. **Regresión del CLI**: antes de refactorizar cada grupo se fija su salida
   con `click.testing.CliRunner` + fake; tras el refactor debe ser idéntica.
4. **Servidor MCP en memoria**: cliente del SDK conectado al servidor en el
   mismo proceso con `Session` usando el fake. Verifica: 31 tools listadas con
   sus annotations, resultados estructurados, `osc_screenshot` devuelve imagen
   PNG, errores como `ToolError` (sin dispositivo; timeout → reconexión).
5. **Hardware real** (`tests/hw/`, solo con `OSC_HW=1`): identify, status,
   measure sobre la señal de calibración (1 kHz), capture, screenshot y un
   ciclo set/get de canal que restaura el estado original.
6. **Evaluación mcp-builder** (opcional, tras implementar):
   `evaluation.xml` con ~10 preguntas realistas, ejecutada por el usuario con
   `scripts/evaluation.py` contra el equipo real.

`tests/test_decoders.py` se migra a pytest y debe seguir pasando.

## Orden de implementación sugerido

1. Infraestructura de tests (pytest, `FakeOscilloscope`) y migración de
   `test_decoders.py`.
2. `imaging.py`.
3. Refactor a `ops/` grupo por grupo, cada uno con tests de regresión del CLI.
4. `osc_mcp/session.py`.
5. `osc_mcp/tools/*` + `server.py`, con tests en memoria.
6. Empaquetado, README, smoke test de hardware.
