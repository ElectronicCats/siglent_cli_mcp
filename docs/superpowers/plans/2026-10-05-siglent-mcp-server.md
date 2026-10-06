# Servidor MCP Siglent SDS1104X-E — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer el osciloscopio SDS1104X-E como servidor MCP (34 tools, stdio) construido sobre una capa `osc_cli/ops` compartida con el CLI `osc`, corrigiendo de paso los bugs de transporte de `device.py`.

**Architecture:** `osc_cli/device.py` (transporte USBTMC) ← `osc_cli/ops/*` (lógica del dialecto LeCroy, devuelve dicts) ← dos clientes delgados: `osc_cli/commands/*` (click, texto idéntico al actual) y `siglent_mcp/tools/*` (tools MCP síncronas). `siglent_mcp/session.py` mantiene una conexión persistente protegida por lock, con reintento solo ante errores de transporte en operaciones idempotentes.

**Tech Stack:** Python ≥3.10, pyvisa + pyvisa-py, click, `mcp` 2.3.x (`MCPServer`), pydantic (vía mcp), pytest + plugin anyio.

**Spec:** `docs/superpowers/specs/2026-10-05-mcp-server-design.md` (revisión 2).

## Global Constraints

- `requires-python = ">=3.10"`; SDK `mcp>=2.3,<3`, API `from mcp.server.mcpserver import MCPServer, Context, Image`; `ToolError` desde `mcp.server.mcpserver.exceptions`; `ToolAnnotations` desde `mcp_types`.
- `TypedDict` y `NotRequired` se importan de `typing_extensions` (pydantic lo exige en Python < 3.12).
- Prefijo de tools `siglent_`; nombre del servidor `siglent_sds1104xe_mcp`; paquete `siglent_mcp`; script `siglent-mcp`.
- Todas las tools son `def` síncronas, llevan `@tool_errors` debajo de `@server.tool(...)`, y `open_world_hint=False`.
- Solo transporte USB (USBTMC). Nada de `tools/` (LAN) entra en este trabajo; no se toca ni se commitea ese directorio.
- El texto que imprime el CLI `osc` no cambia (los tests de caracterización lo fijan). Única excepción de comportamiento: `osc timebase run` deja de enviar `ARM`.
- `osc_cli/ops/*` no importa `click` ni `mcp`.
- Nunca `dev.reset()` USB. Reintento automático solo si `retry=True` y la excepción es `OscTransportError`.
- Variables de entorno: `OSC_RESOURCE`, `OSC_TIMEOUT_MS` (5000), `OSC_LOCK_TIMEOUT_S` (120), `OSC_DATA_DIR` (`$XDG_DATA_HOME/siglent-mcp` o `~/.local/share/siglent-mcp`), `OSC_KEEP_FILES` (20), `OSC_MAX_SAMPLES` (2 000 000), `OSC_LOG_LEVEL` (INFO).
- Texto dirigido al agente (descripciones de tools, errores, notas) en **inglés**, como los docstrings del código; los mensajes en español del spec se traducen con el mismo contenido.
- Todos los comandos se ejecutan desde la raíz del repo con el venv del proyecto: `.venv/bin/python -m pytest …`.
- Parámetro offline del decoder UART: `rx_csv` (el spec decía `csv_path`; se renombra para seguir el patrón `<línea>_csv` de I2C/SPI).

## Review Focus

1. **USB desconectado entre llamadas y vuelto a conectar** → la llamada que falla da un error accionable y la siguiente reconecta sola, sin reiniciar el servidor. Test: `test_reconnects_on_next_call_after_failed_call` (Task 10).
2. **El CSV de `siglent_capture_waveform` se pasa a `siglent_decode_uart(rx_csv=…)`** → decodifica los mismos bytes que en vivo. Test: `test_decode_uart_from_capture_csv_round_trip` (Task 14).
3. **Dos llamadas MCP concurrentes** (p. ej. captura + status) → la segunda espera; nunca se intercala tráfico USB. Test: `test_concurrent_runs_are_serialized` (Task 10).
4. **`siglent_send_raw_command("CHDR OFF")` seguido de cualquier lectura** → el servidor restaura `CHDR SHORT` y los parsers toleran respuestas sin cabecera. Tests: `test_raw_command_restores_header` (Task 15) y `test_read_parses_without_headers` (Task 4).
5. **`sources=["C1","C1"]` en `siglent_capture_waveform`, y `offset` más allá del total en un decoder** → se deduplica / devuelve página vacía con `has_more=false`, sin error. Tests: `test_capture_waveform_dedupes_sources` (Task 14) y `test_paginate_offset_past_end` (Task 9).

## File Structure

```
pyproject.toml                         (mod) python>=3.10, extras mcp/dev, paquetes, script, pytest
osc_cli/device.py                      (mod) errores tipados, retries, read_binary_block, read_bmp, WaveformRaw
osc_cli/imaging.py                     (new) bmp_to_png
osc_cli/ops/__init__.py                (new)
osc_cli/ops/_parse.py                  (new) value_of, to_float, split_number, to_bool, pairs
osc_cli/ops/channel.py                 (new)
osc_cli/ops/timebase.py                (new)
osc_cli/ops/trigger.py                 (new)
osc_cli/ops/acquisition.py             (new) resume/stop/single/force/state/wait
osc_cli/ops/measure.py                 (new)
osc_cli/ops/system.py                  (new)
osc_cli/ops/misc.py                    (new) math, display, cursor, counter, setups
osc_cli/ops/awg.py                     (new)
osc_cli/ops/waveform.py                (new) fetch, stats, decimate, csv, capture
osc_cli/ops/screen.py                  (new)
osc_cli/ops/decode.py                  (new) triggers serie, load_csv, capture_lines, paginate, diagnose
osc_cli/commands/*.py                  (mod) usan ops; mismo texto
siglent_mcp/__init__.py                (new)
siglent_mcp/session.py                 (new) Session, ScopeBusy
siglent_mcp/storage.py                 (new) Storage
siglent_mcp/errors.py                  (new) tool_errors
siglent_mcp/models.py                  (new) TypedDicts de retorno
siglent_mcp/server.py                  (new) create_server, server, main
siglent_mcp/tools/__init__.py          (new)
siglent_mcp/tools/common.py            (new) Deps, annotations, tipos, report_progress
siglent_mcp/tools/status.py            (new) 10 tools de lectura
siglent_mcp/tools/config.py            (new) 11 tools de configuración
siglent_mcp/tools/capture.py           (new) pantalla + forma de onda
siglent_mcp/tools/decode.py            (new) 3 decoders paginados
siglent_mcp/tools/danger.py            (new) 8 tools destructivas
tests/__init__.py, tests/conftest.py   (new)
tests/fakes.py                         (new) FakeOscilloscope, FakeInstrument, bloques sintéticos, run_cli
tests/bmp_util.py                      (new) make_bmp, read_png
tests/test_*.py                        (new) device, imaging, ops_*, cli_*
tests/mcp_server/conftest.py + test_*  (new) servidor en memoria
tests/hw/test_smoke.py                 (new) solo con OSC_HW=1
evaluation/siglent_eval.xml            (new)
README.md                              (mod) sección MCP
```

---

### Task 1: Infraestructura de tests y empaquetado base

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/fakes.py`, `tests/test_cli_system.py`

**Interfaces:**
- Produces: `tests.fakes.FakeOscilloscope(responses=None)` con `.write(cmd)`, `.query(cmd, retries=3)`, `.query_float`, `.idn()`, `.reset()`, `.timeout(ms)` (context manager), `.close()`, atributos `.log: list[tuple]` (`("w", cmd)`, `("q", cmd)`), `.writes: list[str]`, `.last_retries`, `.timeout_ms`, `.fail_writes: dict[str, Exception]`, `.raw: dict[str, bytes]`, `.blocks: dict[str, bytes]`, `.honor_sparsing: bool`. Una respuesta puede ser `str`, una `list` (se consume en orden; el último elemento se repite) o una excepción (se lanza).
- Produces: `tests.fakes.scope_responses() -> dict`, `tests.fakes.without_headers(responses) -> dict`, `tests.fakes.run_cli(monkeypatch, fake, *args) -> click.testing.Result`, constantes `IDN`, `MEASURE_PARAMS`.

- [ ] **Step 1: Actualizar `pyproject.toml`**

Reemplazar el bloque `[project]` hasta el final por:

```toml
[project]
name = "sds1104x-cli"
version = "1.0.0"
description = "Full-featured CLI to control a Siglent SDS1104X-E oscilloscope over USBTMC"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
dependencies = [
    "click>=8.0",
    "pyvisa>=1.13",
    "pyvisa-py>=0.5",
    "pyusb>=1.2",
]

[project.optional-dependencies]
mcp = ["mcp>=2.3,<3", "typing_extensions>=4.12"]
dev = ["pytest>=8", "anyio>=4.10", "mcp[cli]>=2.3,<3", "typing_extensions>=4.12"]

[project.scripts]
osc = "osc_cli.cli:run"

[tool.setuptools]
packages = ["osc_cli", "osc_cli.commands"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["hw: needs a real SDS1104X-E connected (run with OSC_HW=1)"]
```

Instalar: `.venv/bin/pip install -e ".[dev]"`
Expected: termina con `Successfully installed …` (incluye `mcp-2.3.x`).

- [ ] **Step 2: Crear `tests/__init__.py` (vacío) y `tests/conftest.py`**

```python
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
```

- [ ] **Step 3: Crear `tests/fakes.py`**

```python
"""Test doubles for the oscilloscope, so no hardware is needed."""

from __future__ import annotations

import re
from contextlib import contextmanager

from click.testing import CliRunner

from osc_cli.device import OscError, parse_float

IDN = "*IDN SIGLENT,SDS1104X-E,SDSMMEBQ3R1234,8.1.6.1.37R2"
MEASURE_PARAMS = (
    "PKPK", "MAX", "MIN", "TOP", "BASE", "AMPL", "MEAN", "RMS",
    "PER", "FREQ", "RISE", "FALL", "WID", "DUTY", "OVSN",
    "FPRE", "CMEAN", "CRMS",
)
_HEADER = re.compile(r"^\*?[A-Z][A-Z0-9_]*(?::[A-Z][A-Z0-9_]*)*\s+")


def scope_responses() -> dict:
    """Plausible CHDR SHORT responses for every query the code issues."""
    r = {
        "*IDN?": IDN,
        "TDIV?": "TDIV 1.00E-03S",
        "TRDL?": "TRDL 0.00E+00S",
        "SARA?": "SARA 1.00E+09Sa/s",
        "MSIZ?": "MSIZ 14M",
        "AVGA?": "AVGA 16",
        "TRMD?": "TRMD AUTO",
        "TRSE?": "TRSE EDGE,SR,C1,HT,OFF",
        "TRSR?": "TRSR C1",
        "TRLV?": "C1:TRLV 1.50E+00V",
        "TRCP?": "C1:TRCP DC",
        "SAST?": "SAST Trig'd",
        "SYSTem:ERRor?": '0,"No error"',
        "*TST?": "*TST 0",
        "*CAL?": "*CAL 0",
        "FCNT?": "FCNT STATE,ON,FRQ,1.00000E+03Hz",
        "C1:BSWV?": "C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,4V,OFST,0V,HLEV,2V,LLEV,-2V,PHSE,0",
        "C1:OUTP?": "C1:OUTP OFF,LOAD,HZ,PLRT,NOR",
        "C1:MDWV?": "C1:MDWV STATE,OFF",
        "C1:SYNC?": "C1:SYNC OFF",
        "C1:BTWV?": "C1:BTWV STATE,OFF,PRD,0.01S,NCYC,1",
        "C1:SWWV?": "C1:SWWV STATE,OFF,TIME,1S,START,100HZ,STOP,1000HZ,DIR,UP",
        "C1:ARWV?": "C1:ARWV INDEX,2,NAME,StairUp",
        "MATH:FUNC?": "MATH:FUNC ADD",
        "MATH:OFST?": "MATH:OFST 0.00E+00V",
        "MATH:SCALE?": "MATH:SCALE 1.00E+00V",
        "GRDS?": "GRDS FULL",
        "INTS?": "INTS GRID,50,TRACE,60",
        "MENU?": "MENU ON",
        "CRMS?": "CRMS OFF",
    }
    for n in (1, 2, 3, 4):
        c = f"C{n}"
        r[f"{c}:TRA?"] = f"{c}:TRA {'ON' if n <= 2 else 'OFF'}"
        r[f"{c}:VDIV?"] = f"{c}:VDIV 5.00E-01V"
        r[f"{c}:OFST?"] = f"{c}:OFST 0.00E+00V"
        r[f"{c}:CPL?"] = f"{c}:CPL D1M"
        r[f"{c}:BWL?"] = f"{c}:BWL OFF"
        r[f"{c}:ATTN?"] = f"{c}:ATTN 1.00E+01"
        r[f"{c}:INVT?"] = f"{c}:INVT OFF"
        r[f"{c}:UNIT?"] = f"{c}:UNIT V"
        r[f"{c}:SKEW?"] = f"{c}:SKEW 0.00E+00S"
        r[f"SANU? {c}"] = "SANU 1.40E+06pts"
        for p in MEASURE_PARAMS:
            r[f"{c}:PAVA? {p}"] = f"{c}:PAVA {p},1.00E+00V"
        r[f"{c}:PAVA? FREQ"] = f"{c}:PAVA FREQ,1.00E+03Hz"
        r[f"{c}:PAVA? PER"] = f"{c}:PAVA PER,1.00E-03S"
        r[f"{c}:PAVA? DUTY"] = f"{c}:PAVA DUTY,5.00E+01%"
    return r


def without_headers(responses: dict) -> dict:
    """The same responses as the scope sends them with CHDR OFF."""
    return {k: _HEADER.sub("", v) if isinstance(v, str) else v for k, v in responses.items()}


class FakeOscilloscope:
    """Stands in for osc_cli.device.Oscilloscope and records every command."""

    def __init__(self, responses: dict | None = None):
        self.responses = scope_responses() if responses is None else dict(responses)
        self.log: list[tuple] = []
        self.fail_writes: dict[str, Exception] = {}
        self.raw: dict[str, bytes] = {}
        self.blocks: dict[str, bytes] = {}
        self.honor_sparsing = False
        self.timeout_ms = 5000
        self.last_retries: int | None = None
        self.closed = False

    @property
    def writes(self) -> list[str]:
        return [entry[1] for entry in self.log if entry[0] == "w"]

    def write(self, cmd: str) -> None:
        self.log.append(("w", cmd))
        if cmd in self.fail_writes:
            raise self.fail_writes[cmd]

    def query(self, cmd: str, retries: int = 3) -> str:
        self.log.append(("q", cmd))
        self.last_retries = retries
        if cmd not in self.responses:
            raise OscError(f"FakeOscilloscope: no response for {cmd!r}")
        r = self.responses[cmd]
        if isinstance(r, list):
            r = r.pop(0) if len(r) > 1 else r[0]
        if isinstance(r, BaseException):
            raise r
        return r

    def query_float(self, cmd: str) -> float:
        return parse_float(self.query(cmd))

    def idn(self) -> str:
        return self.query("*IDN?")

    def reset(self) -> None:
        self.write("*RST")

    def query_raw(self, cmd: str) -> bytes:
        self.log.append(("raw", cmd))
        return self.raw[cmd]

    @contextmanager
    def timeout(self, ms: int):
        old, self.timeout_ms = self.timeout_ms, ms
        try:
            yield
        finally:
            self.timeout_ms = old

    def close(self) -> None:
        self.closed = True


def run_cli(monkeypatch, fake, *args):
    """Invoke the `osc` CLI with `fake` in place of the real device."""
    from osc_cli import cli as cli_module

    monkeypatch.setattr(cli_module, "get_device", lambda *a, **k: fake)
    return CliRunner().invoke(cli_module.cli, list(args), catch_exceptions=False)
```

- [ ] **Step 4: Escribir `tests/test_cli_system.py` (caracterización del CLI actual)**

```python
import pytest

from tests.fakes import IDN, FakeOscilloscope, run_cli

CASES = [
    (["system", "idn"], [("q", "*IDN?")], IDN + "\n"),
    (["system", "reset", "-y"], [("w", "*RST")], "Reset complete.\n"),
    (["system", "error"], [("q", "SYSTem:ERRor?")], '0,"No error"\n'),
    (["system", "trigger"], [("w", "*TRG")], ""),
    (["system", "selftest"], [("q", "*TST?")], "*TST 0\n"),
    (["system", "calibrate", "-y"], [("q", "*CAL?")], "*CAL 0\n"),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_system_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log
```

- [ ] **Step 5: Ejecutar toda la suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 6 tests de `test_cli_system.py` + los 9 de `test_decoders.py`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/conftest.py tests/fakes.py tests/test_cli_system.py
git commit -m "Add pytest setup, oscilloscope fake and CLI characterization tests"
```

---

### Task 2: Correcciones de la capa de dispositivo

**Files:**
- Modify: `osc_cli/device.py` (reemplazo completo)
- Modify: `tests/fakes.py` (añadir soporte de formas de onda, BMP y `FakeInstrument`)
- Create: `tests/test_device.py`

**Interfaces:**
- Consumes: `tests.fakes.FakeOscilloscope` (Task 1).
- Produces (en `osc_cli.device`):
  - `class OscError(Exception)`, `class OscTransportError(OscError)` (atributo `retried: bool = False`), `class OscNotFoundError(OscError)`.
  - `@dataclass(frozen=True) class WaveformRaw: codes: bytes; vdiv: float; offset: float; horz_interval: float; horz_offset: float; wave_count: int; first_valid: int; last_valid: int`.
  - `Oscilloscope(resource=None, timeout_ms=5000, *, instrument=None)`; métodos `write(cmd)`, `query(cmd, retries=3) -> str`, `query_raw(cmd) -> bytes`, `read_binary_block(deadline_s=60.0) -> bytes`, `read_bmp(cmd="SCDP", deadline_s=30.0) -> bytes`, `timeout(ms)` (context manager), `get_waveform_raw(channel="C1", sparsing=1, deadline_s=60.0) -> WaveformRaw`, `get_waveform(channel="C1", points=0) -> dict` (formato legado).
  - `parse_wavedesc(block: bytes, sparsing: int = 1) -> WaveformRaw`, `waveform_dict(raw: WaveformRaw) -> dict`, `parse_float(s) -> float`, `get_device(resource=None, timeout_ms=5000) -> Oscilloscope`.
- Produces (en `tests.fakes`): `make_wavedesc_block(codes, vdiv=0.5, offset=0.0, interval=1e-6, horz_offset=0.0) -> bytes`, `ieee_block(payload, prefix=b"ALL,") -> bytes`, `codes_from_volts(volts, vdiv) -> bytes`, `FakeInstrument`, y en `FakeOscilloscope`: `get_waveform_raw(channel="C1", sparsing=1, deadline_s=60.0)`, `get_waveform(channel="C1", points=0)`, `read_bmp(cmd="SCDP", deadline_s=30.0)`.

- [ ] **Step 1: Añadir a `tests/fakes.py` los helpers de forma de onda y `FakeInstrument`**

Añadir a los imports: `import struct` y `from dataclasses import replace`, y cambiar el import de device por:

```python
from osc_cli.device import OscError, parse_float, parse_wavedesc, waveform_dict
```

Añadir al final del archivo:

```python
def make_wavedesc_block(codes, vdiv=0.5, offset=0.0, interval=1e-6, horz_offset=0.0) -> bytes:
    """A WAVEDESC (346 bytes) followed by the int8 ADC codes, as C<n>:WF? ALL sends it."""
    codes = bytes(codes)
    desc = bytearray(346)
    struct.pack_into("<i", desc, 36, 346)
    struct.pack_into("<i", desc, 60, len(codes))
    struct.pack_into("<i", desc, 116, len(codes))
    struct.pack_into("<i", desc, 124, 0)
    struct.pack_into("<i", desc, 128, max(len(codes) - 1, 0))
    struct.pack_into("<f", desc, 156, vdiv)
    struct.pack_into("<f", desc, 160, offset)
    struct.pack_into("<f", desc, 176, interval)
    struct.pack_into("<d", desc, 180, horz_offset)
    return bytes(desc) + codes


def ieee_block(payload: bytes, prefix: bytes = b"ALL,") -> bytes:
    return prefix + b"#9" + f"{len(payload):09d}".encode() + payload + b"\n"


def codes_from_volts(volts, vdiv: float) -> bytes:
    """Quantize volts to the scope's int8 codes (32 codes per division)."""
    out = bytearray()
    for v in volts:
        code = max(-128, min(127, round(v * 32 / vdiv)))
        out.append(code & 0xFF)
    return bytes(out)


class FakeInstrument:
    """Stands in for a pyvisa resource, below osc_cli.device.Oscilloscope."""

    def __init__(self, chunks=(), query_responses=None, query_errors=0):
        self.timeout = 0
        self.write_termination = None
        self.read_termination = "\n"
        self.chunks = list(chunks)
        self.query_responses = dict(query_responses or {})
        self.query_errors = query_errors
        self.writes: list[str] = []
        self.clears = 0
        self.terminations_seen: list = []

    def write(self, cmd):
        self.writes.append(cmd)

    def read_raw(self):
        self.terminations_seen.append(self.read_termination)
        if not self.chunks:
            raise TimeoutError("VI_ERROR_TMO (-1073807339): Timeout expired")
        return self.chunks.pop(0)

    def query(self, cmd):
        self.writes.append(cmd)
        if self.query_errors:
            self.query_errors -= 1
            raise OSError("[Errno 32] Pipe error")
        return self.query_responses[cmd]

    def clear(self):
        self.clears += 1

    def close(self):
        pass
```

Y añadir estos métodos a `FakeOscilloscope`:

```python
    def get_waveform_raw(self, channel="C1", sparsing=1, deadline_s=60.0):
        self.log.append(("wf", channel, sparsing))
        raw = parse_wavedesc(self.blocks[channel])
        if sparsing > 1 and self.honor_sparsing:
            codes = raw.codes[::sparsing]
            raw = replace(raw, codes=codes, wave_count=len(codes),
                          horz_interval=raw.horz_interval * sparsing)
        return raw

    def get_waveform(self, channel="C1", points=0):
        return waveform_dict(self.get_waveform_raw(channel))

    def read_bmp(self, cmd="SCDP", deadline_s=30.0):
        self.log.append(("raw", cmd))
        return self.raw[cmd]
```

- [ ] **Step 2: Escribir los tests que fallan, `tests/test_device.py`**

```python
import struct

import pytest

from osc_cli import device
from osc_cli.device import OscError, OscNotFoundError, OscTransportError, Oscilloscope
from tests.fakes import FakeInstrument, ieee_block, make_wavedesc_block


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(device.time, "sleep", lambda s: None)


def scope(inst):
    return Oscilloscope(instrument=inst)


def test_read_binary_block_survives_more_than_10000_chunks():
    payload = bytes(range(256)) * 47  # 12032 bytes
    data = ieee_block(payload)
    inst = FakeInstrument(chunks=[data[i:i + 1] for i in range(len(data))])
    assert scope(inst).read_binary_block() == payload


def test_read_binary_block_short_read_is_transport_error():
    data = ieee_block(b"x" * 100)[:60]
    inst = FakeInstrument(chunks=[data])
    with pytest.raises(OscTransportError, match="after"):
        scope(inst).read_binary_block()


def test_read_binary_block_accepts_other_digit_counts_and_restores_termination():
    inst = FakeInstrument(chunks=[b"#210", b"0123456789\n"])
    o = scope(inst)
    assert o.read_binary_block() == b"0123456789"
    assert inst.terminations_seen == [None, None]
    assert inst.read_termination == "\n"


def test_read_binary_block_rejects_bad_header():
    inst = FakeInstrument(chunks=[b"#Z123"])
    with pytest.raises(OscError, match="block header"):
        scope(inst).read_binary_block()


def test_query_retries_zero_does_not_retry():
    inst = FakeInstrument(query_responses={"*CAL?": "*CAL 0"}, query_errors=1)
    with pytest.raises(OscTransportError):
        scope(inst).query("*CAL?", retries=0)
    assert inst.clears == 0


def test_query_default_retries_recover():
    inst = FakeInstrument(query_responses={"TDIV?": "TDIV 1.00E-03S\n"}, query_errors=2)
    assert scope(inst).query("TDIV?") == "TDIV 1.00E-03S"
    assert inst.clears == 2


def test_get_waveform_raw_parses_descriptor_and_restores_header():
    block = make_wavedesc_block(bytes([0, 16, 32, 255]), vdiv=0.5, offset=0.1, interval=1e-6)
    inst = FakeInstrument(chunks=[ieee_block(block)])
    raw = scope(inst).get_waveform_raw("C2")
    assert raw.codes == bytes([0, 16, 32, 255])
    assert raw.vdiv == pytest.approx(0.5)
    assert raw.offset == pytest.approx(0.1)
    assert raw.horz_interval == pytest.approx(1e-6)
    assert inst.writes == ["CHDR OFF", "WFSU SP,0,NP,0,FP,0", "C2:WF? ALL", "CHDR SHORT"]


def test_get_waveform_raw_with_sparsing_scales_interval_and_resets_wfsu():
    block = make_wavedesc_block(bytes(10), interval=1e-6)
    inst = FakeInstrument(chunks=[ieee_block(block)])
    raw = scope(inst).get_waveform_raw("C1", sparsing=4)
    assert raw.horz_interval == pytest.approx(4e-6)
    assert inst.writes == ["CHDR OFF", "WFSU SP,4,NP,0,FP,0", "C1:WF? ALL",
                           "WFSU SP,0,NP,0,FP,0", "CHDR SHORT"]


def test_get_waveform_raw_restores_header_when_transfer_fails():
    inst = FakeInstrument(chunks=[])
    with pytest.raises(OscTransportError):
        scope(inst).get_waveform_raw("C1")
    assert inst.writes[-1] == "CHDR SHORT"


def test_legacy_get_waveform_dict_matches_original_math():
    block = make_wavedesc_block(bytes([0, 16, 224]), vdiv=0.5, offset=0.0, interval=1e-6)
    inst = FakeInstrument(chunks=[ieee_block(block)])
    data = scope(inst).get_waveform("C1")
    assert data["samples"] == pytest.approx([0.0, 0.25, -0.5])
    assert data["times"] == pytest.approx([0.0, 1e-6, 2e-6])
    assert data["wave_count"] == 3


def make_bmp_bytes(size: int) -> bytes:
    body = bytearray(b"\n" * size)  # 0x0A everywhere: must not end the read
    body[0:2] = b"BM"
    struct.pack_into("<I", body, 2, size)
    return bytes(body)


def test_read_bmp_reads_declared_size_ignoring_newlines():
    bmp = make_bmp_bytes(3000)
    inst = FakeInstrument(chunks=[bmp[:7], bmp[7:1500], bmp[1500:]])
    o = scope(inst)
    assert o.read_bmp() == bmp
    assert inst.writes == ["SCDP"]
    assert set(inst.terminations_seen) == {None}
    assert inst.read_termination == "\n"


def test_read_bmp_rejects_non_bmp():
    inst = FakeInstrument(chunks=[b"GIF89a....."])
    with pytest.raises(OscError, match="not a BMP"):
        scope(inst).read_bmp()


def test_read_bmp_truncated_is_transport_error():
    bmp = make_bmp_bytes(3000)
    inst = FakeInstrument(chunks=[bmp[:1000]])
    with pytest.raises(OscTransportError, match="1000 of 3000"):
        scope(inst).read_bmp()


def test_timeout_context_restores_previous_value():
    inst = FakeInstrument()
    o = scope(inst)
    with o.timeout(120000):
        assert inst.timeout == 120000
    assert inst.timeout == 5000


def test_write_failure_is_transport_error():
    class Broken(FakeInstrument):
        def write(self, cmd):
            raise OSError("pipe")

    with pytest.raises(OscTransportError):
        scope(Broken()).write("STOP")


def test_no_device_raises_not_found(monkeypatch):
    class EmptyRM:
        def __init__(self, *a):
            pass

        def list_resources(self):
            return ()

    monkeypatch.setattr(device.pyvisa, "ResourceManager", EmptyRM)
    with pytest.raises(OscNotFoundError):
        device.get_device()
```

- [ ] **Step 3: Ejecutar para verificar que fallan**

Run: `.venv/bin/python -m pytest tests/test_device.py -q`
Expected: FAIL con `ImportError: cannot import name 'OscNotFoundError'` (o `parse_wavedesc` desde `tests/fakes.py`).

- [ ] **Step 4: Reemplazar `osc_cli/device.py` completo**

```python
"""Low-level connection layer for the SDS1104X-E oscilloscope over USBTMC.

The SDS1104X-E speaks a LeCroy X-Stream style command set (NOT standard Siglent
SCPI). This module uses pyvisa with the pyvisa-py backend (no NI-VISA needed)
and auto-detects the device by USB VID/PID (Siglent f4ec:ee38).

Key protocol details discovered from the live device:
- Responses echo a short header (e.g. "C1:VDIV 1.00E+00V") unless CHDR OFF.
- Binary waveform data uses IEEE 488.2 definite-length blocks "#9<9digits><data>".
- Screen dumps (SCDP) return raw BMP bytes (no block framing); the length
  comes from the BMP header itself.
"""

from __future__ import annotations

import struct
import time
from contextlib import contextmanager
from dataclasses import dataclass

try:
    import pyvisa
except ImportError:  # pragma: no cover
    pyvisa = None

SIGLENT_VID = 0xF4EC
SIGLENT_PID = 0xEE38
WAVEDESC_LEN = 346


class OscError(Exception):
    """Raised on oscilloscope communication or protocol errors."""


class OscTransportError(OscError):
    """The USB/VISA transport failed (timeout, pipe error, short read).

    Unlike protocol errors, the same request may succeed on a new connection.
    """

    retried = False


class OscNotFoundError(OscError):
    """No oscilloscope could be opened."""


@dataclass(frozen=True)
class WaveformRaw:
    """One channel's capture as raw 8-bit ADC codes plus its scaling."""

    codes: bytes  # signed int8 ADC codes, one per returned sample
    vdiv: float  # volts/div (VERTICAL_GAIN on this firmware)
    offset: float  # vertical offset (V)
    horz_interval: float  # seconds between returned samples
    horz_offset: float  # time of the first sample (s)
    wave_count: int
    first_valid: int
    last_valid: int


class Oscilloscope:
    """Connection wrapper exposing query/write/binary helpers."""

    def __init__(self, resource: str | None = None, timeout_ms: int = 5000, *, instrument=None):
        self.timeout_ms = timeout_ms
        self.resource_name = resource
        self._rm = None
        if instrument is not None:
            self._inst = instrument
        else:
            if pyvisa is None:
                raise OscError(
                    "pyvisa is not installed. Run: pip install pyvisa pyvisa-py pyusb"
                )
            self._rm = pyvisa.ResourceManager("@py")
            self._inst = self._open_resource()
        self._inst.timeout = self.timeout_ms
        self._inst.write_termination = "\n"
        self._inst.read_termination = "\n"

    def _open_resource(self):
        if self.resource_name:
            try:
                return self._rm.open_resource(self.resource_name)
            except Exception as e:  # noqa: BLE001
                raise OscNotFoundError(
                    f"Cannot open resource '{self.resource_name}': {e}"
                ) from e
        return self._find_siglent()

    def _find_siglent(self):
        resources = self._rm.list_resources()
        usb_resources = [r for r in resources if r.upper().startswith("USB")]
        if not usb_resources:
            raise OscNotFoundError(
                "No USBTMC device found. Is the oscilloscope connected and "
                "powered on? Check permissions (see README 'udev' section)."
            )

        for r in usb_resources:
            try:
                if self._is_siglent(r):
                    return self._rm.open_resource(r)
            except Exception:  # noqa: BLE001
                continue

        inst = self._rm.open_resource(usb_resources[0])
        try:
            inst.query("*IDN?")
        except Exception as e:  # noqa: BLE001
            raise OscNotFoundError(
                f"Found USB device {usb_resources[0]} but could not query *IDN?: {e}"
            ) from e
        return inst

    @staticmethod
    def _is_siglent(resource: str) -> bool:
        norm = resource.upper()
        vid = f"{SIGLENT_VID:X}"
        pid = f"{SIGLENT_PID:X}"
        return vid in norm and pid in norm

    # ---- low level SCPI -------------------------------------------------
    def write(self, cmd: str) -> None:
        """Send a command (no response expected)."""
        try:
            self._inst.write(cmd)
        except Exception as e:  # noqa: BLE001
            raise OscTransportError(f"Write '{cmd}' failed: {e}") from e

    def query(self, cmd: str, retries: int = 3) -> str:
        """Send a query and return the stripped response.

        The AWG firmware occasionally leaves the USBTMC pipe in a transient
        error state after bursts of writes, causing a spurious USBError on the
        next read. We retry transparently `retries` times to absorb this. Use
        retries=0 for queries that must not run twice (*CAL?, *TST?).
        """
        last_exc = None
        for attempt in range(retries + 1):
            try:
                return self._inst.query(cmd).strip()
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt == retries:
                    break
                # Clear any pending status before retrying.
                try:
                    self._inst.clear()
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.1 * (attempt + 1))
        raise OscTransportError(
            f"Query '{cmd}' failed after {retries + 1} attempt(s): {last_exc}"
        ) from last_exc

    def query_raw(self, cmd: str) -> bytes:
        """Send a query and return the raw bytes (for binary responses)."""
        self.write(cmd)
        try:
            return self._inst.read_raw()
        except Exception as e:  # noqa: BLE001
            raise OscTransportError(f"Read after '{cmd}' failed: {e}") from e

    def _read_chunk(self, got: int, expected) -> bytes:
        try:
            chunk = self._inst.read_raw()
        except Exception as e:  # noqa: BLE001
            raise OscTransportError(
                f"Read failed after {got} of {expected} bytes: {e}"
            ) from e
        if not chunk:
            raise OscTransportError(f"Empty read after {got} of {expected} bytes")
        return chunk

    def read_binary_block(self, deadline_s: float = 60.0) -> bytes:
        """Read an IEEE 488.2 definite-length block (#<n><n digits><data>).

        USBTMC delivers the payload in small transfers and binary data may
        contain 0x0A bytes, so newline termination is disabled and reads are
        accumulated until the declared byte count arrives or `deadline_s`
        passes.
        """
        old_term = self._inst.read_termination
        self._inst.read_termination = None
        start = time.monotonic()
        try:
            data = bytearray()
            header_end = declared = None
            while True:
                if time.monotonic() - start > deadline_s:
                    raise OscTransportError(
                        f"Block transfer timed out after {len(data)} of "
                        f"{declared if declared is not None else '?'} bytes"
                    )
                data += self._read_chunk(len(data), declared if declared is not None else "?")
                if declared is None:
                    i = data.find(b"#")
                    if i < 0:
                        if len(data) > 64:
                            raise OscError(f"No block header in {bytes(data[:32])!r}")
                        continue
                    if len(data) < i + 2:
                        continue
                    ndigits = data[i + 1] - 0x30
                    if not 1 <= ndigits <= 9:
                        raise OscError(f"Unexpected block header: {bytes(data[i:i + 3])!r}")
                    if len(data) < i + 2 + ndigits:
                        continue
                    declared = int(data[i + 2 : i + 2 + ndigits])
                    header_end = i + 2 + ndigits
                if len(data) >= header_end + declared:
                    return bytes(data[header_end : header_end + declared])
        finally:
            self._inst.read_termination = old_term

    def read_bmp(self, cmd: str = "SCDP", deadline_s: float = 30.0) -> bytes:
        """Send `cmd` and read a raw BMP whose length comes from its own header."""
        self.write(cmd)
        old_term = self._inst.read_termination
        self._inst.read_termination = None
        start = time.monotonic()
        try:
            data = bytearray()
            size = None
            while size is None or len(data) < size:
                if time.monotonic() - start > deadline_s:
                    raise OscTransportError(
                        f"Screen dump timed out after {len(data)} of {size or '?'} bytes"
                    )
                data += self._read_chunk(len(data), size or "?")
                if size is None and len(data) >= 6:
                    if data[:2] != b"BM":
                        raise OscError(
                            f"Screen dump is not a BMP (starts with {bytes(data[:8])!r})"
                        )
                    size = struct.unpack_from("<I", data, 2)[0]
            return bytes(data[:size])
        finally:
            self._inst.read_termination = old_term

    def query_float(self, cmd: str) -> float:
        # LeCroy responses embed units; extract the leading numeric token.
        return parse_float(self.query(cmd))

    def query_int(self, cmd: str) -> int:
        return int(parse_float(self.query(cmd)))

    def idn(self) -> str:
        return self.query("*IDN?")

    @contextmanager
    def timeout(self, ms: int):
        """Temporarily use a different I/O timeout (e.g. for *CAL?)."""
        old = self._inst.timeout
        self._inst.timeout = ms
        try:
            yield
        finally:
            self._inst.timeout = old

    def close(self) -> None:
        if self._inst is not None:
            try:
                self._inst.close()
            except Exception:  # noqa: BLE001
                pass
            self._inst = None

    def __enter__(self) -> "Oscilloscope":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- convenience ----------------------------------------------------
    def reset(self) -> None:
        self.write("*RST")

    def opc_wait(self, timeout_s: float = 5.0) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < timeout_s:
            if self.query("*OPC?") == "1":
                return True
            time.sleep(0.05)
        return False

    # ---- waveform data --------------------------------------------------
    def get_waveform_raw(
        self, channel: str = "C1", sparsing: int = 1, deadline_s: float = 60.0
    ) -> WaveformRaw:
        """Fetch one channel's capture as raw ADC codes.

        `sparsing` > 1 asks the scope to send every k-th point (WFSU SP). The
        firmware ignores NP, so without sparsing the full memory is returned.
        """
        self.write("CHDR OFF")
        try:
            self.write(f"WFSU SP,{sparsing if sparsing > 1 else 0},NP,0,FP,0")
            self.write(f"{channel}:WF? ALL")
            block = self.read_binary_block(deadline_s)
        finally:
            try:
                if sparsing > 1:
                    self.write("WFSU SP,0,NP,0,FP,0")
                self.write("CHDR SHORT")
            except OscError:
                pass
        return parse_wavedesc(block, sparsing)

    def get_waveform(self, channel: str = "C1", points: int = 0) -> dict:
        """Fetch a full waveform as the legacy dict (lists of volts and seconds).

        `points` is accepted for compatibility; the firmware ignores NP.
        """
        return waveform_dict(self.get_waveform_raw(channel))


def parse_wavedesc(block: bytes, sparsing: int = 1) -> WaveformRaw:
    """Split a WF? ALL block into its WAVEDESC scaling and int8 codes."""
    if len(block) < WAVEDESC_LEN:
        raise OscError(f"Waveform block too short ({len(block)} bytes)")

    def f32(off):
        return struct.unpack_from("<f", block, off)[0]

    def i32(off):
        return struct.unpack_from("<i", block, off)[0]

    desc_len = i32(36)
    array1_len = i32(60)
    return WaveformRaw(
        codes=bytes(block[desc_len : desc_len + array1_len]),
        vdiv=f32(156),  # VERTICAL_GAIN stores volts/div on this firmware
        offset=f32(160),
        horz_interval=f32(176) * max(sparsing, 1),
        horz_offset=struct.unpack_from("<d", block, 180)[0],
        wave_count=i32(116),
        first_valid=i32(124),
        last_valid=i32(128),
    )


def waveform_dict(raw: WaveformRaw) -> dict:
    """Legacy representation: volts and times as Python lists."""
    # 8-bit signed ADC codes span the 8-division grid: 256 codes / 8 div
    # = 32 codes per division, so volts = code * vdiv / 32.
    scale = raw.vdiv / 32.0
    samples = [scale * (b if b < 128 else b - 256) - raw.offset for b in raw.codes]
    times = [raw.horz_interval * k + raw.horz_offset for k in range(raw.wave_count)]
    return {
        "vdiv": raw.vdiv,
        "offset": raw.offset,
        "horz_interval": raw.horz_interval,
        "horz_offset": raw.horz_offset,
        "wave_count": raw.wave_count,
        "first_valid": raw.first_valid,
        "last_valid": raw.last_valid,
        "samples": samples,
        "times": times,
    }


def parse_float(s: str) -> float:
    """Extract a numeric value from a LeCroy-style response like 'C1:VDIV 1.00E+00V'."""
    import re

    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    if not m:
        raise ValueError(f"No numeric value in {s!r}")
    return float(m.group())


def get_device(resource: str | None = None, timeout_ms: int = 5000) -> Oscilloscope:
    """Factory: connect to the oscilloscope, raising a helpful error on failure."""
    try:
        return Oscilloscope(resource, timeout_ms)
    except OscError:
        raise
    except Exception as e:  # noqa: BLE001
        raise OscNotFoundError(
            f"Could not connect to the oscilloscope: {e}\n"
            "Check that it is powered on, connected via USB, and that the udev "
            "rule granting access is installed (see README)."
        ) from e
```

- [ ] **Step 5: Ejecutar los tests**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (todos, incluidos los de Task 1).

- [ ] **Step 6: Commit**

```bash
git add osc_cli/device.py tests/fakes.py tests/test_device.py
git commit -m "Fix block/BMP reads, typed transport errors and per-query retries in device layer"
```

---

### Task 3: Conversión BMP → PNG

**Files:**
- Create: `osc_cli/imaging.py`, `tests/bmp_util.py`, `tests/test_imaging.py`

**Interfaces:**
- Produces: `osc_cli.imaging.bmp_to_png(data: bytes) -> bytes` (lanza `ValueError` con BMP inválido/truncado/no soportado); `osc_cli.imaging.PNG_SIGNATURE`.
- Produces (tests): `tests.bmp_util.make_bmp(pixels, bpp=24, top_down=False, masks=None) -> bytes` y `tests.bmp_util.read_png(data) -> (width, height, rows)` donde `rows` es una lista de filas de tuplas `(r, g, b)`.

- [ ] **Step 1: Crear `tests/bmp_util.py`**

```python
"""Build BMPs and decode PNGs for tests (stdlib only)."""

from __future__ import annotations

import struct
import zlib


def _pack(value8: int, mask: int) -> int:
    shift = (mask & -mask).bit_length() - 1
    maxv = mask >> shift
    return ((value8 * maxv // 255) << shift) & mask


def make_bmp(pixels, bpp=24, top_down=False, masks=None) -> bytes:
    """pixels: rows top-to-bottom of (r, g, b). masks => BI_BITFIELDS."""
    height, width = len(pixels), len(pixels[0])
    row_size = (bpp * width + 31) // 32 * 4
    rows = []
    for row in pixels:
        b = bytearray()
        for r, g, bl in row:
            if bpp == 24:
                b += bytes((bl, g, r))
            elif masks:
                value = _pack(r, masks[0]) | _pack(g, masks[1]) | _pack(bl, masks[2])
                b += struct.pack("<H" if bpp == 16 else "<I", value)
            elif bpp == 32:
                b += bytes((bl, g, r, 0))
            else:  # 16 bpp default RGB555
                value = _pack(r, 0x7C00) | _pack(g, 0x03E0) | _pack(bl, 0x001F)
                b += struct.pack("<H", value)
        b += b"\0" * (row_size - len(b))
        rows.append(bytes(b))
    if not top_down:
        rows.reverse()
    pixel_data = b"".join(rows)
    extra = struct.pack("<III", *masks) if masks else b""
    pixel_offset = 14 + 40 + len(extra)
    info = struct.pack(
        "<IiiHHIIiiII", 40, width, -height if top_down else height, 1, bpp,
        3 if masks else 0, len(pixel_data), 2835, 2835, 0, 0,
    )
    header = b"BM" + struct.pack("<IHHI", pixel_offset + len(pixel_data), 0, 0, pixel_offset)
    return header + info + extra + pixel_data


def read_png(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, width = 8, b"", None
    while pos < len(data):
        (length,) = struct.unpack_from(">I", data, pos)
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack_from(">I", data, pos + 8 + length)
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            assert (depth, color) == (8, 2)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 3 + 1
    rows = []
    for y in range(height):
        line = raw[y * stride : (y + 1) * stride]
        assert line[0] == 0
        rows.append([tuple(line[1 + 3 * x : 4 + 3 * x]) for x in range(width)])
    return width, height, rows
```

- [ ] **Step 2: Escribir los tests que fallan, `tests/test_imaging.py`**

```python
import pytest

from osc_cli.imaging import bmp_to_png
from tests.bmp_util import make_bmp, read_png

PIXELS = [
    [(255, 0, 0), (0, 255, 0), (0, 0, 255)],
    [(255, 255, 255), (0, 0, 0), (255, 255, 0)],
]


@pytest.mark.parametrize("bpp", [24, 32])
@pytest.mark.parametrize("top_down", [False, True])
def test_converts_truecolor(bpp, top_down):
    png = bmp_to_png(make_bmp(PIXELS, bpp=bpp, top_down=top_down))
    assert read_png(png) == (3, 2, PIXELS)


@pytest.mark.parametrize("masks", [None, (0xF800, 0x07E0, 0x001F)])
def test_converts_16_bit(masks):
    png = bmp_to_png(make_bmp(PIXELS, bpp=16, masks=masks))
    assert read_png(png) == (3, 2, PIXELS)


def test_converts_32_bit_bitfields():
    masks = (0x00FF0000, 0x0000FF00, 0x000000FF)
    png = bmp_to_png(make_bmp(PIXELS, bpp=32, masks=masks))
    assert read_png(png)[2] == PIXELS


def test_rejects_non_bmp():
    with pytest.raises(ValueError, match="BM"):
        bmp_to_png(b"\x89PNG" + bytes(100))


def test_rejects_truncated():
    data = make_bmp(PIXELS)
    with pytest.raises(ValueError, match="Truncated"):
        bmp_to_png(data[:-4])


def test_rejects_unsupported_depth():
    data = bytearray(make_bmp(PIXELS))
    data[28] = 8  # biBitCount
    with pytest.raises(ValueError, match="8 bits"):
        bmp_to_png(bytes(data))
```

- [ ] **Step 3: Ejecutar para verificar que fallan**

Run: `.venv/bin/python -m pytest tests/test_imaging.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'osc_cli.imaging'`.

- [ ] **Step 4: Crear `osc_cli/imaging.py`**

```python
"""Convert the scope's BMP screen dumps to PNG using only the standard library."""

from __future__ import annotations

import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_DEFAULT_MASKS = {
    16: (0x7C00, 0x03E0, 0x001F),  # RGB555
    32: (0x00FF0000, 0x0000FF00, 0x000000FF),  # BGRX
}


def bmp_to_png(data: bytes) -> bytes:
    """Convert an uncompressed 16/24/32-bit BMP to an RGB PNG."""
    width, height, rows = _decode_bmp(data)
    return _encode_png(width, height, rows)


def _decode_bmp(data: bytes):
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("Not a BMP image (missing 'BM' signature)")
    file_size = struct.unpack_from("<I", data, 2)[0]
    if len(data) < file_size:
        raise ValueError(f"Truncated BMP: header declares {file_size} bytes, got {len(data)}")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height, _planes, bpp, compression = struct.unpack_from("<iiHHI", data, 18)
    if bpp not in (16, 24, 32):
        raise ValueError(f"Unsupported BMP depth: {bpp} bits per pixel")
    if compression not in (0, 3) or (compression == 3 and bpp == 24):
        raise ValueError(f"Unsupported BMP compression: {compression}")
    if width <= 0 or height == 0:
        raise ValueError(f"Invalid BMP size {width}x{height}")
    top_down = height < 0
    height = abs(height)
    row_size = (bpp * width + 31) // 32 * 4
    if pixel_offset + row_size * height > len(data):
        raise ValueError("Truncated BMP pixel data")
    # BI_BITFIELDS masks follow the 40-byte info header (offset 54); V4/V5
    # headers store them at the same offset.
    masks = struct.unpack_from("<III", data, 54) if compression == 3 else _DEFAULT_MASKS.get(bpp)
    rows = []
    for y in range(height):
        src = y if top_down else height - 1 - y
        start = pixel_offset + src * row_size
        rows.append(_row_to_rgb(data[start : start + row_size], width, bpp, masks))
    return width, height, rows


def _row_to_rgb(row: bytes, width: int, bpp: int, masks) -> bytes:
    if bpp == 24:
        src = row[: width * 3]
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = src[2::3], src[1::3], src[0::3]
        return bytes(rgb)
    if bpp == 32 and tuple(masks) == _DEFAULT_MASKS[32]:
        src = row[: width * 4]
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = src[2::4], src[1::4], src[0::4]
        return bytes(rgb)
    fmt, size = ("<H", 2) if bpp == 16 else ("<I", 4)
    channels = [_channel(mask) for mask in masks]
    out = bytearray()
    for x in range(width):
        px = struct.unpack_from(fmt, row, x * size)[0]
        for shift, maxv, mask in channels:
            out.append(((px & mask) >> shift) * 255 // maxv if maxv else 0)
    return bytes(out)


def _channel(mask: int):
    if mask == 0:
        return 0, 0, 0
    shift = (mask & -mask).bit_length() - 1
    return shift, mask >> shift, mask


def _chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def _encode_png(width: int, height: int, rows) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rows)
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 6))
        + _chunk(b"IEND", b"")
    )
```

- [ ] **Step 5: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/test_imaging.py -q`
Expected: PASS (10 tests).

- [ ] **Step 6: Commit**

```bash
git add osc_cli/imaging.py tests/bmp_util.py tests/test_imaging.py
git commit -m "Add stdlib BMP to PNG conversion for screen dumps"
```

---

### Task 4: Capa `ops` — helpers de parseo y canales

**Files:**
- Modify: `pyproject.toml` (añadir `"osc_cli.ops"` a `packages`)
- Create: `osc_cli/ops/__init__.py`, `osc_cli/ops/_parse.py`, `osc_cli/ops/channel.py`
- Modify: `osc_cli/commands/channel.py` (reemplazo completo)
- Test: `tests/test_cli_channel.py`, `tests/test_ops_parse.py`, `tests/test_ops_channel.py`

**Interfaces:**
- Consumes: `FakeOscilloscope`, `scope_responses`, `without_headers`, `run_cli` (Task 1).
- Produces: `osc_cli.ops._parse.value_of(response) -> str`, `split_number(text) -> (float|None, str)`, `to_float(text) -> float|None`, `to_bool(text) -> bool`, `pairs(text) -> dict[str, str]`.
- Produces: `osc_cli.ops.channel.CHANNELS = (1,2,3,4)`, `COUPLINGS`, `BW_LIMITS`, `UNITS`, `FIELDS`, `query_field(o, channel: int, field) -> str`, `write_field(o, channel, field, value)`, `read(o, channel) -> dict` (claves `channel, enabled, probe, coupling, bw_limit, unit, invert, vdiv, offset, skew`), `apply(o, channel, **values) -> dict`.

- [ ] **Step 1: Tests de caracterización del CLI actual**

`tests/test_cli_channel.py`:

```python
import pytest

from tests.fakes import FakeOscilloscope, run_cli

LIST_LOG = [
    ("q", f"C{n}:{m}?") for n in (1, 2, 3, 4) for m in ("TRA", "VDIV", "OFST", "CPL")
]
LIST_OUT = "".join(
    f"C{n}: trace={'ON' if n <= 2 else 'OFF'}  v/div=5.00E-01V  offset=0.00E+00V  coupling=D1M\n"
    for n in (1, 2, 3, 4)
)

CASES = [
    (["channel", "list"], LIST_LOG, LIST_OUT),
    (["channel", "on", "-c", "3"], [("w", "C3:TRA ON")], "C3 trace enabled.\n"),
    (["channel", "off"], [("w", "C1:TRA OFF")], "C1 trace disabled.\n"),
    (["channel", "vdiv", "-c", "2"], [("q", "C2:VDIV?")], "C2:VDIV 5.00E-01V\n"),
    (["channel", "vdiv", "-c", "2", "0.2"], [("w", "C2:VDIV 0.2")], "C2 v/div = 0.2 V\n"),
    (["channel", "offset", "0.5"], [("w", "C1:OFST 0.5")], "C1 offset = 0.5 V\n"),
    (["channel", "coupling", "-c", "4", "A50"], [("w", "C4:CPL A50")], "C4 coupling = A50\n"),
    (["channel", "bwlimit"], [("q", "C1:BWL?")], "C1:BWL OFF\n"),
    (["channel", "probe", "10"], [("w", "C1:ATTN 10.0")], "C1 probe attenuation = 10.0\n"),
    (["channel", "invert", "ON"], [("w", "C1:INVT ON")], "C1 invert = ON\n"),
    (["channel", "unit", "-c", "2", "A"], [("w", "C2:UNIT A")], "C2 unit = A\n"),
    (["channel", "skew", "-c", "2"], [("q", "C2:SKEW?")], "C2:SKEW 0.00E+00S\n"),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_channel_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log
```

- [ ] **Step 2: Verificar que pasan con el código actual**

Run: `.venv/bin/python -m pytest tests/test_cli_channel.py -q`
Expected: PASS (12). Fijan la salida antes del refactor.

- [ ] **Step 3: Tests de las ops que fallan**

`tests/test_ops_parse.py`:

```python
import pytest

from osc_cli.ops._parse import pairs, split_number, to_bool, to_float, value_of


@pytest.mark.parametrize("response,value", [
    ("C1:VDIV 5.00E-01V", "5.00E-01V"),
    ("5.00E-01V", "5.00E-01V"),
    ("*IDN SIGLENT,SDS1104X-E,X,1", "SIGLENT,SDS1104X-E,X,1"),
    ("SAST Trig'd", "Trig'd"),
    ('0,"No error"', '0,"No error"'),
    ("OFF\n", "OFF"),
    ("C1:PAVA FREQ,****", "FREQ,****"),
])
def test_value_of(response, value):
    assert value_of(response) == value


@pytest.mark.parametrize("text,expected", [
    ("1.00E+03Hz", (1000.0, "Hz")),
    ("-2.5V", (-2.5, "V")),
    ("5.00E+01%", (50.0, "%")),
    (".5", (0.5, "")),
    ("****", (None, "")),
    ("", (None, "")),
])
def test_split_number(text, expected):
    assert split_number(text) == expected


def test_to_float_and_bool():
    assert to_float("1.40E+06pts") == 1.4e6
    assert to_float("") is None
    assert to_bool("ON") and to_bool(" on ") and not to_bool("OFF")


def test_pairs_ignores_trailing_token():
    assert pairs("WVTP,SINE,FRQ,1000HZ,ODD") == {"WVTP": "SINE", "FRQ": "1000HZ"}
    assert pairs("") == {}
```

`tests/test_ops_channel.py`:

```python
import pytest

from osc_cli.ops import channel
from tests.fakes import FakeOscilloscope, scope_responses, without_headers

C1 = {
    "channel": 1, "enabled": True, "probe": 10.0, "coupling": "D1M", "bw_limit": "OFF",
    "unit": "V", "invert": False, "vdiv": 0.5, "offset": 0.0, "skew": 0.0,
}


def test_read_parses_short_headers():
    assert channel.read(FakeOscilloscope(), 1) == C1


def test_read_parses_without_headers():
    fake = FakeOscilloscope(without_headers(scope_responses()))
    assert channel.read(fake, 1) == C1
    assert channel.read(fake, 3)["enabled"] is False


def test_apply_writes_only_given_fields_in_fixed_order():
    fake = FakeOscilloscope()
    state = channel.apply(fake, 2, vdiv=0.2, probe=1, enabled=True, offset=None)
    assert fake.writes == ["C2:TRA ON", "C2:ATTN 1", "C2:VDIV 0.2"]
    assert state["channel"] == 2


def test_apply_rejects_unknown_setting():
    with pytest.raises(ValueError, match="volts"):
        channel.apply(FakeOscilloscope(), 1, volts=1)


def test_rejects_bad_channel():
    with pytest.raises(ValueError, match="1-4"):
        channel.read(FakeOscilloscope(), 5)
```

Run: `.venv/bin/python -m pytest tests/test_ops_parse.py tests/test_ops_channel.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'osc_cli.ops'`.

- [ ] **Step 4: Implementar el paquete `ops`, `_parse` y `channel`**

En `pyproject.toml`: `packages = ["osc_cli", "osc_cli.commands", "osc_cli.ops"]`.

`osc_cli/ops/__init__.py`:

```python
"""Instrument operations shared by the `osc` CLI and the MCP server.

Each function takes an Oscilloscope and returns plain data (dicts, numbers,
bytes). This is the only place that knows the LeCroy X-Stream command strings.
"""
```

`osc_cli/ops/_parse.py`:

```python
"""Parsing helpers for LeCroy-style responses, with or without headers."""

from __future__ import annotations

import re

# "C1:VDIV 5.00E-01V" / "*IDN SIGLENT,..." / "SAST Trig'd" -> header + value.
_HEADER = re.compile(r"^\*?[A-Z][A-Z0-9_]*(?::[A-Z][A-Z0-9_]*)*\s+(.*)$", re.S)
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def value_of(response: str) -> str:
    """Strip the command echo (CHDR SHORT/LONG) and return only the value."""
    text = response.strip()
    m = _HEADER.match(text)
    return (m.group(1) if m else text).strip()


def split_number(text: str) -> tuple[float | None, str]:
    """'1.00E+03Hz' -> (1000.0, 'Hz'); '****' -> (None, '')."""
    m = _NUMBER.search(text or "")
    if not m:
        return None, ""
    return float(m.group()), text[m.end():].strip()


def to_float(text: str) -> float | None:
    return split_number(text)[0]


def to_bool(text: str) -> bool:
    return (text or "").strip().upper() in ("ON", "1", "TRUE")


def pairs(text: str) -> dict[str, str]:
    """'WVTP,SINE,FRQ,1000HZ' -> {'WVTP': 'SINE', 'FRQ': '1000HZ'}."""
    tokens = [t.strip() for t in (text or "").split(",")]
    return dict(zip(tokens[0::2], tokens[1::2]))
```

`osc_cli/ops/channel.py`:

```python
"""Vertical channel settings: C<n>:TRA/ATTN/CPL/BWL/UNIT/INVT/VDIV/OFST/SKEW."""

from __future__ import annotations

from ._parse import to_bool, to_float, value_of

CHANNELS = (1, 2, 3, 4)
COUPLINGS = ("A1M", "D1M", "A50", "D50", "GND")
BW_LIMITS = ("OFF", "20M", "200M")
UNITS = ("V", "A")
# Write order matters: the probe factor rescales v/div, so it goes first.
FIELDS = {
    "enabled": "TRA",
    "probe": "ATTN",
    "coupling": "CPL",
    "bw_limit": "BWL",
    "unit": "UNIT",
    "invert": "INVT",
    "vdiv": "VDIV",
    "offset": "OFST",
    "skew": "SKEW",
}
_NUMERIC = {"probe", "vdiv", "offset", "skew"}
_BOOLEAN = {"enabled", "invert"}


def _check(channel: int) -> None:
    if channel not in CHANNELS:
        raise ValueError(f"channel must be 1-4, got {channel!r}")


def query_field(o, channel: int, field: str) -> str:
    """Raw response for one setting, e.g. 'C1:VDIV 5.00E-01V'."""
    _check(channel)
    return o.query(f"C{channel}:{FIELDS[field]}?")


def write_field(o, channel: int, field: str, value) -> None:
    _check(channel)
    if isinstance(value, bool):
        value = "ON" if value else "OFF"
    o.write(f"C{channel}:{FIELDS[field]} {value}")


def read(o, channel: int) -> dict:
    state = {"channel": channel}
    for field in FIELDS:
        text = value_of(query_field(o, channel, field))
        if field in _NUMERIC:
            state[field] = to_float(text)
        elif field in _BOOLEAN:
            state[field] = to_bool(text)
        else:
            state[field] = text
    return state


def apply(o, channel: int, **values) -> dict:
    """Write the settings that are not None, then return the channel state."""
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown channel setting(s): {', '.join(sorted(unknown))}")
    _check(channel)
    for field in FIELDS:
        if values.get(field) is not None:
            write_field(o, channel, field, values[field])
    return read(o, channel)
```

Run: `.venv/bin/python -m pytest tests/test_ops_parse.py tests/test_ops_channel.py -q`
Expected: PASS.

- [ ] **Step 5: Refactorizar `osc_cli/commands/channel.py` sobre las ops**

`osc_cli/commands/channel.py`:

```python
"""Channel (vertical) control commands (LeCroy X-Stream dialect).

Channels are C1..C4. The command strings live in osc_cli.ops.channel.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import channel as ops_channel

CHANNELS = ("1", "2", "3", "4")


def _chan_option():
    return click.option(
        "--channel",
        "-c",
        type=click.Choice(CHANNELS),
        default="1",
        show_default=True,
        help="Channel number (1-4).",
    )


def _get_or_set(ctx, channel, field, value, message):
    o = osc(ctx)
    n = int(channel)
    if value is None:
        click.echo(ops_channel.query_field(o, n, field))
    else:
        ops_channel.write_field(o, n, field, value)
        click.echo(message.format(ch=f"C{channel}", value=value))


@click.group(name="channel")
def channel_group():
    """Vertical channel control (CH1..CH4)."""


@channel_group.command("list")
@click.pass_context
def channel_list(ctx):
    """Show the state of all channels."""
    o = osc(ctx)
    for n in ops_channel.CHANNELS:
        trace = ops_channel.query_field(o, n, "enabled")
        vdiv = ops_channel.query_field(o, n, "vdiv")
        ofst = ops_channel.query_field(o, n, "offset")
        coup = ops_channel.query_field(o, n, "coupling")
        click.echo(f"C{n}: trace={trace.split()[-1]}  v/div={vdiv.split()[-1]}  "
                   f"offset={ofst.split()[-1]}  coupling={coup.split()[-1]}")


@channel_group.command("on")
@_chan_option()
@click.pass_context
def channel_on(ctx, channel):
    """Turn a channel trace on."""
    ops_channel.write_field(osc(ctx), int(channel), "enabled", True)
    click.echo(f"C{channel} trace enabled.")


@channel_group.command("off")
@_chan_option()
@click.pass_context
def channel_off(ctx, channel):
    """Turn a channel trace off."""
    ops_channel.write_field(osc(ctx), int(channel), "enabled", False)
    click.echo(f"C{channel} trace disabled.")


@channel_group.command("vdiv")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def vdiv(ctx, channel, value):
    """Get/set vertical scale (volts/div)."""
    _get_or_set(ctx, channel, "vdiv", value, "{ch} v/div = {value} V")


@channel_group.command("offset")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, channel, value):
    """Get/set vertical offset (V)."""
    _get_or_set(ctx, channel, "offset", value, "{ch} offset = {value} V")


@channel_group.command("coupling")
@_chan_option()
@click.argument("value", type=click.Choice(ops_channel.COUPLINGS), required=False)
@click.pass_context
def coupling(ctx, channel, value):
    """Get/set input coupling (A=AC, D=DC; 1M/50 ohm; GND)."""
    _get_or_set(ctx, channel, "coupling", value, "{ch} coupling = {value}")


@channel_group.command("bwlimit")
@_chan_option()
@click.argument("value", type=click.Choice(ops_channel.BW_LIMITS), required=False)
@click.pass_context
def bwlimit(ctx, channel, value):
    """Get/set bandwidth limit (OFF/20M/200M)."""
    _get_or_set(ctx, channel, "bw_limit", value, "{ch} bandwidth limit = {value}")


@channel_group.command("probe")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def probe(ctx, channel, value):
    """Get/set probe attenuation factor (e.g. 1, 10, 100)."""
    _get_or_set(ctx, channel, "probe", value, "{ch} probe attenuation = {value}")


@channel_group.command("invert")
@_chan_option()
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def invert(ctx, channel, value):
    """Get/set channel inversion (INVT)."""
    _get_or_set(ctx, channel, "invert", value, "{ch} invert = {value}")


@channel_group.command("unit")
@_chan_option()
@click.argument("value", type=click.Choice(ops_channel.UNITS), required=False)
@click.pass_context
def unit(ctx, channel, value):
    """Get/set channel unit (V/A)."""
    _get_or_set(ctx, channel, "unit", value, "{ch} unit = {value}")


@channel_group.command("skew")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def skew(ctx, channel, value):
    """Get/set channel deskew (seconds)."""
    _get_or_set(ctx, channel, "skew", value, "{ch} skew = {value} s")
```

- [ ] **Step 6: Suite completa**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (los 12 de caracterización siguen idénticos).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml osc_cli/ops osc_cli/commands/channel.py tests/test_cli_channel.py tests/test_ops_parse.py tests/test_ops_channel.py
git commit -m "Extract channel operations into osc_cli.ops"
```

---

### Task 5: Ops de timebase, trigger y adquisición (`run` deja de usar ARM)

**Files:**
- Create: `osc_cli/ops/timebase.py`, `osc_cli/ops/trigger.py`, `osc_cli/ops/acquisition.py`
- Modify: `osc_cli/commands/timebase.py`, `osc_cli/commands/trigger.py` (reemplazo completo)
- Test: `tests/test_cli_timebase_trigger.py`, `tests/test_ops_timebase_trigger.py`

**Interfaces:**
- Consumes: `_parse` (Task 4), `OscError` (Task 2).
- Produces: `timebase.MEMORY_SIZES`, `query_field(o, field)`, `write_field(o, field, value)`, `read(o) -> {tdiv, delay, sample_rate, memory, averages}`, `apply(o, tdiv=None, delay=None, memory=None, averages=None) -> dict`.
- Produces: `trigger.MODES/TYPES/SOURCES/COUPLINGS`, `query_field(o, field, retries=3)`, `write_field`, `read(o) -> {mode, type, source, level, coupling}` (los tres últimos pueden ser `None`), `apply(o, **values) -> dict`.
- Produces: `acquisition.CONTINUOUS_MODES = ("AUTO","NORM")`, `resume(o, preferred=None) -> str`, `stop(o)`, `single(o)`, `force(o)`, `state(o) -> str`, `wait(poll, timeout_s, interval_s=0.05, sleep=time.sleep, clock=time.monotonic) -> {triggered, state, waited_s}`.

- [ ] **Step 1: Tests de caracterización (más el nuevo comportamiento de `run`)**

`tests/test_cli_timebase_trigger.py`:

```python
import pytest

from osc_cli.device import OscTransportError
from tests.fakes import FakeOscilloscope, run_cli

TB_STATUS = (
    "Time/div   : TDIV 1.00E-03S\nDelay      : TRDL 0.00E+00S\n"
    "Sample rate: SARA 1.00E+09Sa/s\nMemory     : MSIZ 14M\nAverages   : AVGA 16\n"
)
TRIG_STATUS = (
    "Mode    : TRMD AUTO\nSetup   : TRSE EDGE,SR,C1,HT,OFF\nSource  : TRSR C1\n"
    "Level   : C1:TRLV 1.50E+00V\nCoupling: C1:TRCP DC\n"
)

CASES = [
    (["timebase", "tdiv"], [("q", "TDIV?")], "TDIV 1.00E-03S\n"),
    (["timebase", "tdiv", "0.001"], [("w", "TDIV 0.001")], "Time/div = 0.001 s\n"),
    (["timebase", "delay", "0.0005"], [("w", "TRDL 0.0005")], "Delay = 0.0005 s\n"),
    (["timebase", "samplerate"], [("q", "SARA?")], "SARA 1.00E+09Sa/s\n"),
    (["timebase", "memory", "14M"], [("w", "MSIZ 14M")], "Memory size = 14M\n"),
    (["timebase", "averages", "16"], [("w", "AVGA 16")], "Averages = 16\n"),
    (["timebase", "stop"], [("w", "STOP")], "Acquisition stopped.\n"),
    (["timebase", "status"],
     [("q", "TDIV?"), ("q", "TRDL?"), ("q", "SARA?"), ("q", "MSIZ?"), ("q", "AVGA?")], TB_STATUS),
    (["trigger", "mode", "NORM"], [("w", "TRMD NORM")], "Trigger mode = NORM\n"),
    (["trigger", "type"], [("q", "TRSE?")], "TRSE EDGE,SR,C1,HT,OFF\n"),
    (["trigger", "source", "C2"], [("w", "TRSR C2")], "Trigger source = C2\n"),
    (["trigger", "level"], [("q", "TRLV?")], "C1:TRLV 1.50E+00V\n"),
    (["trigger", "level", "1.2"], [("w", "TRLV 1.2")], "Trigger level = 1.2 V\n"),
    (["trigger", "coupling", "AC"], [("w", "TRCP AC")], "Trigger coupling = AC\n"),
    (["trigger", "status"],
     [("q", "TRMD?"), ("q", "TRSE?"), ("q", "TRSR?"), ("q", "TRLV?"), ("q", "TRCP?")], TRIG_STATUS),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_timebase_trigger_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log


def test_trigger_status_skips_queries_the_scope_rejects(monkeypatch):
    fake = FakeOscilloscope()
    fake.responses["TRSR?"] = OscTransportError("timeout")
    result = run_cli(monkeypatch, fake, "trigger", "status")
    assert "Source" not in result.output
    assert "Level   : C1:TRLV 1.50E+00V" in result.output


def test_timebase_run_resumes_trigger_mode_instead_of_arm(monkeypatch):
    fake = FakeOscilloscope()
    fake.responses["TRMD?"] = "TRMD NORM"
    result = run_cli(monkeypatch, fake, "timebase", "run")
    assert result.output == "Acquisition running.\n"
    assert fake.log == [("q", "TRMD?"), ("w", "TRMD NORM")]
```

Run: `.venv/bin/python -m pytest tests/test_cli_timebase_trigger.py -q`
Expected: FAIL solo `test_timebase_run_resumes_trigger_mode_instead_of_arm` (hoy envía `ARM`); los otros 16 pasan.

- [ ] **Step 2: Tests de las ops que fallan**

`tests/test_ops_timebase_trigger.py`:

```python
import pytest

from osc_cli.device import OscTransportError
from osc_cli.ops import acquisition, timebase, trigger
from tests.fakes import FakeOscilloscope


def test_timebase_read():
    assert timebase.read(FakeOscilloscope()) == {
        "tdiv": 0.001, "delay": 0.0, "sample_rate": 1e9, "memory": "14M", "averages": 16,
    }


def test_timebase_apply_writes_memory_first():
    fake = FakeOscilloscope()
    timebase.apply(fake, tdiv=0.002, memory="1.4M")
    assert fake.writes == ["MSIZ 1.4M", "TDIV 0.002"]


def test_timebase_rejects_unknown_memory():
    with pytest.raises(ValueError, match="memory"):
        timebase.apply(FakeOscilloscope(), memory="3M")


def test_trigger_read():
    assert trigger.read(FakeOscilloscope()) == {
        "mode": "AUTO", "type": "EDGE", "source": "C1", "level": 1.5, "coupling": "DC",
    }


def test_trigger_read_tolerates_unanswered_optional_queries():
    fake = FakeOscilloscope()
    fake.responses["TRSR?"] = OscTransportError("timeout")
    state = trigger.read(fake)
    assert state["source"] is None
    assert fake.last_retries == 0  # last query (TRCP?) is optional too


def test_trigger_apply_arms_last():
    fake = FakeOscilloscope()
    trigger.apply(fake, mode="SINGLE", level=1.0, type="EDGE", source="C2")
    assert fake.writes == ["TRSE EDGE", "TRSR C2", "TRLV 1.0", "TRMD SINGLE"]


def test_trigger_apply_rejects_unknown():
    with pytest.raises(ValueError, match="slope"):
        trigger.apply(FakeOscilloscope(), slope="RISE")


@pytest.mark.parametrize("current,preferred,expected", [
    ("TRMD NORM", None, "NORM"),
    ("TRMD STOP", "NORM", "NORM"),
    ("TRMD STOP", None, "AUTO"),
    ("TRMD SINGLE", "SINGLE", "AUTO"),
])
def test_resume(current, preferred, expected):
    fake = FakeOscilloscope()
    fake.responses["TRMD?"] = current
    assert acquisition.resume(fake, preferred) == expected
    assert fake.writes == [f"TRMD {expected}"]


def test_stop_single_force_and_state():
    fake = FakeOscilloscope()
    acquisition.stop(fake)
    acquisition.single(fake)
    acquisition.force(fake)
    assert fake.writes == ["STOP", "TRMD SINGLE", "*TRG"]
    assert acquisition.state(fake) == "Trig'd"


def fake_clock():
    now = [0.0]

    def sleep(s):
        now[0] += s

    return sleep, (lambda: now[0])


def test_wait_returns_when_capture_completes():
    sleep, clock = fake_clock()
    states = iter(["Ready", "Arm", "Stop"])
    result = acquisition.wait(lambda: next(states), 5, sleep=sleep, clock=clock)
    assert result == {"triggered": True, "state": "Stop", "waited_s": 0.1}


def test_wait_times_out():
    sleep, clock = fake_clock()
    result = acquisition.wait(lambda: "Ready", 0.2, sleep=sleep, clock=clock)
    assert result["triggered"] is False
    assert result["waited_s"] >= 0.2
```

Run: `.venv/bin/python -m pytest tests/test_ops_timebase_trigger.py -q`
Expected: FAIL con `ImportError: cannot import name 'acquisition'`.

- [ ] **Step 3: Implementar las ops**

`osc_cli/ops/timebase.py`:

```python
"""Horizontal timebase and acquisition memory: TDIV, TRDL, SARA, MSIZ, AVGA."""

from __future__ import annotations

from ._parse import to_float, value_of

MEMORY_SIZES = ("7K", "70K", "700K", "7M", "14K", "140K", "1.4M", "14M")
FIELDS = {"tdiv": "TDIV", "delay": "TRDL", "memory": "MSIZ", "averages": "AVGA"}
QUERY_FIELDS = {
    "tdiv": "TDIV",
    "delay": "TRDL",
    "sample_rate": "SARA",
    "memory": "MSIZ",
    "averages": "AVGA",
}


def query_field(o, field: str) -> str:
    return o.query(f"{QUERY_FIELDS[field]}?")


def write_field(o, field: str, value) -> None:
    if field not in FIELDS:
        raise ValueError(f"{field} cannot be set")
    o.write(f"{FIELDS[field]} {value}")


def read(o) -> dict:
    v = {field: value_of(query_field(o, field)) for field in QUERY_FIELDS}
    averages = to_float(v["averages"])
    return {
        "tdiv": to_float(v["tdiv"]),
        "delay": to_float(v["delay"]),
        "sample_rate": to_float(v["sample_rate"]),
        "memory": v["memory"],
        "averages": int(averages) if averages is not None else None,
    }


def apply(o, tdiv=None, delay=None, memory=None, averages=None) -> dict:
    """Write the settings that are not None (memory first), then read back."""
    if memory is not None and memory not in MEMORY_SIZES:
        raise ValueError(f"memory must be one of {', '.join(MEMORY_SIZES)}")
    for field, value in (("memory", memory), ("tdiv", tdiv), ("delay", delay), ("averages", averages)):
        if value is not None:
            write_field(o, field, value)
    return read(o)
```

`osc_cli/ops/trigger.py`:

```python
"""Trigger settings: TRMD (mode), TRSE (type), TRSR, TRLV, TRCP."""

from __future__ import annotations

from ..device import OscError
from ._parse import to_float, value_of

MODES = ("AUTO", "NORM", "SINGLE", "STOP")
TYPES = ("EDGE", "SERIAL", "PULSE", "VIDEO", "SLOPE", "PATTERN", "DROP", "INTV", "RUNT")
SOURCES = ("C1", "C2", "C3", "C4", "EXT", "LINE")
COUPLINGS = ("DC", "AC", "HFREJ", "LFREJ")
FIELDS = {"mode": "TRMD", "type": "TRSE", "source": "TRSR", "level": "TRLV", "coupling": "TRCP"}
# The scope does not answer these for every trigger type; read them as None.
OPTIONAL = ("source", "level", "coupling")
# Configure first, arm last.
_WRITE_ORDER = ("type", "source", "coupling", "level", "mode")


def query_field(o, field: str, retries: int = 3) -> str:
    return o.query(f"{FIELDS[field]}?", retries=retries)


def write_field(o, field: str, value) -> None:
    o.write(f"{FIELDS[field]} {value}")


def read(o) -> dict:
    state = {}
    for field in FIELDS:
        optional = field in OPTIONAL
        try:
            text = value_of(query_field(o, field, retries=0 if optional else 3))
        except OscError:
            if not optional:
                raise
            state[field] = None
            continue
        if field == "type":
            text = text.split(",")[0]
        state[field] = to_float(text) if field == "level" else text
    return state


def apply(o, **values) -> dict:
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown trigger setting(s): {', '.join(sorted(unknown))}")
    for field in _WRITE_ORDER:
        if values.get(field) is not None:
            write_field(o, field, values[field])
    return read(o)
```

`osc_cli/ops/acquisition.py`:

```python
"""Run/stop/single/force acquisition control and completion polling."""

from __future__ import annotations

import time

from ._parse import value_of

CONTINUOUS_MODES = ("AUTO", "NORM")
# SAST? states that mean a capture is complete and frozen or just triggered.
DONE_STATES = ("stop", "trig'd")


def resume(o, preferred: str | None = None) -> str:
    """Return to continuous acquisition and return the mode used.

    Keeps AUTO/NORM if the scope is already in one; otherwise uses
    `preferred` (the last continuous mode seen) or AUTO. ARM is not used: on
    this dialect it arms a single capture.
    """
    current = value_of(o.query("TRMD?")).upper()
    if current in CONTINUOUS_MODES:
        mode = current
    elif preferred in CONTINUOUS_MODES:
        mode = preferred
    else:
        mode = "AUTO"
    o.write(f"TRMD {mode}")
    return mode


def stop(o) -> None:
    o.write("STOP")


def single(o) -> None:
    o.write("TRMD SINGLE")


def force(o) -> None:
    o.write("*TRG")


def state(o) -> str:
    """Acquisition state as reported by SAST? (e.g. 'Ready', "Trig'd", 'Stop')."""
    return value_of(o.query("SAST?"))


def wait(poll, timeout_s: float, interval_s: float = 0.05,
         sleep=time.sleep, clock=time.monotonic) -> dict:
    """Call poll() until it returns a done state or timeout_s elapses.

    `poll` takes no arguments, so callers can release the instrument lock
    between polls.
    """
    start = clock()
    while True:
        current = poll()
        waited = round(clock() - start, 3)
        if current.strip().lower() in DONE_STATES:
            return {"triggered": True, "state": current, "waited_s": waited}
        if waited >= timeout_s:
            return {"triggered": False, "state": current, "waited_s": waited}
        sleep(interval_s)
```

- [ ] **Step 4: Refactorizar los comandos**

`osc_cli/commands/timebase.py`:

```python
"""Timebase (horizontal) and acquisition commands (LeCroy dialect).

The command strings live in osc_cli.ops.timebase and osc_cli.ops.acquisition.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import acquisition as ops_acq
from ..ops import timebase as ops_tb


@click.group(name="timebase")
def timebase_group():
    """Horizontal timebase and acquisition control."""


@timebase_group.command("tdiv")
@click.argument("value", type=float, required=False)
@click.pass_context
def tdiv(ctx, value):
    """Get/set horizontal scale (s/div) via TDIV."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_tb.query_field(o, "tdiv"))
    else:
        ops_tb.write_field(o, "tdiv", value)
        click.echo(f"Time/div = {value} s")


@timebase_group.command("delay")
@click.argument("value", type=float, required=False)
@click.pass_context
def delay(ctx, value):
    """Get/set horizontal trigger delay (s) via TRDL."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_tb.query_field(o, "delay"))
    else:
        ops_tb.write_field(o, "delay", value)
        click.echo(f"Delay = {value} s")


@timebase_group.command("samplerate")
@click.pass_context
def samplerate(ctx):
    """Query the current sample rate (Sa/s) via SARA."""
    click.echo(ops_tb.query_field(osc(ctx), "sample_rate"))


@timebase_group.command("memory")
@click.argument("value", required=False)
@click.pass_context
def memory(ctx, value):
    """Get/set memory size (e.g. 14M, 1.4M) via MSIZ."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_tb.query_field(o, "memory"))
    else:
        ops_tb.write_field(o, "memory", value)
        click.echo(f"Memory size = {value}")


@timebase_group.command("averages")
@click.argument("value", type=int, required=False)
@click.pass_context
def averages(ctx, value):
    """Get/set acquisition averages via AVGA."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_tb.query_field(o, "averages"))
    else:
        ops_tb.write_field(o, "averages", value)
        click.echo(f"Averages = {value}")


@timebase_group.command("run")
@click.pass_context
def run(ctx):
    """Resume continuous acquisition (TRMD AUTO/NORM)."""
    ops_acq.resume(osc(ctx))
    click.echo("Acquisition running.")


@timebase_group.command("stop")
@click.pass_context
def stop(ctx):
    """Stop acquisition (STOP)."""
    ops_acq.stop(osc(ctx))
    click.echo("Acquisition stopped.")


@timebase_group.command("status")
@click.pass_context
def status(ctx):
    """Show timebase/acquisition settings."""
    o = osc(ctx)
    labels = {"tdiv": "Time/div", "delay": "Delay", "sample_rate": "Sample rate",
              "memory": "Memory", "averages": "Averages"}
    for field, label in labels.items():
        click.echo(f"{label:11s}: {ops_tb.query_field(o, field)}")
```

`osc_cli/commands/trigger.py`:

```python
"""Trigger control commands (LeCroy dialect).

The command strings live in osc_cli.ops.trigger. Serial decode triggers are in
the decode group.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import trigger as ops_trig


@click.group(name="trigger")
def trigger_group():
    """Trigger configuration."""


@trigger_group.command("mode")
@click.argument("value", type=click.Choice(ops_trig.MODES), required=False)
@click.pass_context
def mode(ctx, value):
    """Get/set trigger mode via TRMD."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "mode"))
    else:
        ops_trig.write_field(o, "mode", value)
        click.echo(f"Trigger mode = {value}")


@trigger_group.command("type")
@click.argument(
    "value",
    type=click.Choice(ops_trig.TYPES),
    required=False,
)
@click.pass_context
def type_(ctx, value):
    """Get/set trigger type via TRSE."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "type"))
    else:
        ops_trig.write_field(o, "type", value)
        click.echo(f"Trigger type = {value}")


@trigger_group.command("source")
@click.argument("value", type=click.Choice(ops_trig.SOURCES), required=False)
@click.pass_context
def source(ctx, value):
    """Get/set trigger source via TRSR."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "source"))
    else:
        ops_trig.write_field(o, "source", value)
        click.echo(f"Trigger source = {value}")


@trigger_group.command("level")
@click.argument("value", type=float, required=False)
@click.pass_context
def level(ctx, value):
    """Get/set trigger level (V) via TRLV."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "level"))
    else:
        ops_trig.write_field(o, "level", value)
        click.echo(f"Trigger level = {value} V")


@trigger_group.command("coupling")
@click.argument("value", type=click.Choice(ops_trig.COUPLINGS), required=False)
@click.pass_context
def coupling(ctx, value):
    """Get/set trigger coupling via TRCP."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "coupling"))
    else:
        ops_trig.write_field(o, "coupling", value)
        click.echo(f"Trigger coupling = {value}")


@trigger_group.command("status")
@click.pass_context
def status(ctx):
    """Show current trigger settings."""
    o = osc(ctx)
    click.echo(f"Mode    : {ops_trig.query_field(o, 'mode')}")
    click.echo(f"Setup   : {ops_trig.query_field(o, 'type')}")
    for label, field in [("Source", "source"), ("Level", "level"), ("Coupling", "coupling")]:
        try:
            click.echo(f"{label:8s}: {ops_trig.query_field(o, field, retries=0)}")
        except Exception:  # noqa: BLE001
            pass
```

- [ ] **Step 5: Suite completa**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, incluido el test de `run`.

- [ ] **Step 6: Commit**

```bash
git add osc_cli/ops/timebase.py osc_cli/ops/trigger.py osc_cli/ops/acquisition.py osc_cli/commands/timebase.py osc_cli/commands/trigger.py tests/test_cli_timebase_trigger.py tests/test_ops_timebase_trigger.py
git commit -m "Extract timebase/trigger/acquisition ops; resume with TRMD instead of ARM"
```

---

### Task 6: Ops de mediciones, sistema y misceláneos

**Files:**
- Create: `osc_cli/ops/measure.py`, `osc_cli/ops/system.py`, `osc_cli/ops/misc.py`
- Modify (reemplazo completo): `osc_cli/commands/measure.py`, `osc_cli/commands/system.py`, `osc_cli/commands/math.py`, `osc_cli/commands/advanced.py`
- Test: `tests/test_cli_measure_misc.py`, `tests/test_ops_measure_system_misc.py`

**Interfaces:**
- Consumes: `_parse` (Task 4), `acquisition.force` (Task 5).
- Produces: `measure.PARAMS` (18), `DEFAULT_ITEMS` (8), `SOURCES`, `INVALID_NOTE`, `query_item(o, source, item) -> str`, `measure(o, source, items=None) -> {item: {value, unit, note?}}`.
- Produces: `system.identify(o) -> {manufacturer, model, serial, firmware, raw}`, `last_error(o) -> {code, message}`, `reset(o)`, `selftest(o) -> str`, `calibrate(o) -> str` (ambas con `retries=0`), `raw_command(o, command, expect_response) -> str | None`.
- Produces: `misc.MATH_FUNCTIONS/GRIDS/CURSOR_MODES`, `query(o, mnemonic) -> str`, `set_math_function/offset/scale`, `read_math(o)`, `apply_math(o, function=None, offset=None, scale=None)`, `set_grid/set_intensity/set_menu/set_cursor_mode`, `read_display(o)`, `apply_display(o, grid=None, intensity=None, menu=None, cursor_mode=None)`, `set_counter(o, enabled)`, `read_counter(o) -> {enabled, frequency_hz, raw}`, `save_setup(o, path)`, `recall_setup(o, path)`.
- Nota: los comandos de `system` que solo existen en el CLI (`error`, `clear`, `opc`, `version`, `scopeid`, `date`, `time`, `header`) siguen hablando directamente con el dispositivo; el MCP no los usa.

- [ ] **Step 1: Tests de caracterización**

`tests/test_cli_measure_misc.py`:

```python
import pytest

from tests.fakes import FakeOscilloscope, run_cli

ALL_ITEMS = ["PKPK", "MAX", "MIN", "MEAN", "RMS", "PER", "FREQ", "DUTY", "RISE", "FALL"]


def pava(src, item):
    return FakeOscilloscope().responses[f"{src}:PAVA? {item}"]


CASES = [
    (["measure", "item", "-i", "FREQ", "-s", "C2"], [("q", "C2:PAVA? FREQ")], pava("C2", "FREQ") + "\n"),
    (["measure", "all"], [("q", f"C1:PAVA? {i}") for i in ALL_ITEMS],
     "".join(pava("C1", i) + "\n" for i in ALL_ITEMS)),
    (["measure", "vpp"], [("q", "C1:PAVA? PKPK")], pava("C1", "PKPK") + "\n"),
    (["measure", "period", "-s", "C3"], [("q", "C3:PAVA? PER")], pava("C3", "PER") + "\n"),
    (["math", "function"], [("q", "MATH:FUNC?")], "MATH:FUNC ADD\n"),
    (["math", "function", "FFT"], [("w", "MATH:FUNC FFT")], "Math function = FFT\n"),
    (["math", "scale", "2"], [("w", "MATH:SCALE 2.0")], "Math scale = 2.0\n"),
    (["display", "grid", "HALF"], [("w", "GRDS HALF")], "Grid = HALF\n"),
    (["display", "intensity", "60"], [("w", "INTS TRACE,60")], "Trace intensity = 60\n"),
    (["display", "menu"], [("q", "MENU?")], "MENU ON\n"),
    (["cursor", "mode", "TRACK"], [("w", "CRMS TRACK")], "Cursor mode = TRACK\n"),
    (["counter", "on"], [("w", "FCNT STATE,ON")], "Counter enabled.\n"),
    (["counter", "status"], [("q", "FCNT?")], "FCNT STATE,ON,FRQ,1.00000E+03Hz\n"),
    (["save", "setup", "/usb/a.xml"], [("w", 'STORE_SETUP FILE,"/usb/a.xml"')], "Setup saved to /usb/a.xml\n"),
    (["save", "recall-setup", "/usb/a.xml"], [("w", 'RECALL_SETUP FILE,"/usb/a.xml"')],
     "Setup recalled from /usb/a.xml\n"),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_measure_and_misc_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log
```

Run: `.venv/bin/python -m pytest tests/test_cli_measure_misc.py tests/test_cli_system.py -q`
Expected: PASS (15 + 6).

- [ ] **Step 2: Tests de las ops que fallan**

`tests/test_ops_measure_system_misc.py`:

```python
import pytest

from osc_cli.ops import measure, misc, system
from tests.fakes import FakeOscilloscope


def test_measure_default_items_with_units():
    result = measure.measure(FakeOscilloscope(), "C1")
    assert list(result) == list(measure.DEFAULT_ITEMS)
    assert result["FREQ"] == {"value": 1000.0, "unit": "Hz"}
    assert result["DUTY"] == {"value": 50.0, "unit": "%"}


def test_measure_invalid_reading_is_null_with_note():
    fake = FakeOscilloscope()
    fake.responses["C2:PAVA? FREQ"] = "C2:PAVA FREQ,****"
    entry = measure.measure(fake, "C2", ["FREQ"])["FREQ"]
    assert entry["value"] is None
    assert "v/div" in entry["note"]


def test_measure_rejects_unknown_item_and_source():
    with pytest.raises(ValueError, match="VOLTS"):
        measure.measure(FakeOscilloscope(), "C1", ["VOLTS"])
    with pytest.raises(ValueError, match="source"):
        measure.measure(FakeOscilloscope(), "C5")


def test_identify():
    assert system.identify(FakeOscilloscope()) == {
        "manufacturer": "SIGLENT", "model": "SDS1104X-E", "serial": "SDSMMEBQ3R1234",
        "firmware": "8.1.6.1.37R2", "raw": "SIGLENT,SDS1104X-E,SDSMMEBQ3R1234,8.1.6.1.37R2",
    }


def test_last_error():
    assert system.last_error(FakeOscilloscope()) == {"code": 0, "message": "No error"}
    fake = FakeOscilloscope()
    fake.responses["SYSTem:ERRor?"] = "garbled"
    assert system.last_error(fake) == {"code": None, "message": "garbled"}


def test_selftest_and_calibrate_are_not_retried():
    fake = FakeOscilloscope()
    assert system.selftest(fake) == "*TST 0"
    assert fake.last_retries == 0
    assert system.calibrate(fake) == "*CAL 0"
    assert fake.last_retries == 0


def test_raw_command_query_and_write():
    fake = FakeOscilloscope()
    assert system.raw_command(fake, "TDIV?", True) == "TDIV 1.00E-03S"
    assert system.raw_command(fake, "TDIV 1E-3", False) is None
    assert fake.writes == ["TDIV 1E-3"]


def test_math_read_and_apply():
    fake = FakeOscilloscope()
    state = misc.apply_math(fake, function="FFT", scale=2.0)
    assert fake.writes == ["MATH:FUNC FFT", "MATH:SCALE 2.0"]
    assert state == {"function": "ADD", "offset": 0.0, "scale": 1.0}  # fake read-back


def test_display_read_and_apply():
    fake = FakeOscilloscope()
    state = misc.apply_display(fake, menu=False, intensity=60, cursor_mode="TRACK")
    assert fake.writes == ["INTS TRACE,60", "MENU OFF", "CRMS TRACK"]
    assert state == {"grid": "FULL", "intensity": 60, "menu": True, "cursor_mode": "OFF"}


def test_display_rejects_bad_grid():
    with pytest.raises(ValueError, match="grid"):
        misc.apply_display(FakeOscilloscope(), grid="DOTS")


def test_counter():
    fake = FakeOscilloscope()
    misc.set_counter(fake, True)
    assert fake.writes == ["FCNT STATE,ON"]
    assert misc.read_counter(fake) == {
        "enabled": True, "frequency_hz": 1000.0, "raw": "FCNT STATE,ON,FRQ,1.00000E+03Hz",
    }


def test_setup_paths_are_quoted_and_validated():
    fake = FakeOscilloscope()
    misc.save_setup(fake, "/usb/a.xml")
    misc.recall_setup(fake, "/usb/a.xml")
    assert fake.writes == ['STORE_SETUP FILE,"/usb/a.xml"', 'RECALL_SETUP FILE,"/usb/a.xml"']
    with pytest.raises(ValueError, match="quotes"):
        misc.save_setup(fake, 'a"b')
```

Run: `.venv/bin/python -m pytest tests/test_ops_measure_system_misc.py -q`
Expected: FAIL con `ImportError`.

- [ ] **Step 3: Implementar las ops**

`osc_cli/ops/measure.py`:

```python
"""Automatic measurements via the LeCroy PAVA readout: C<n>:PAVA? <param>."""

from __future__ import annotations

from ._parse import split_number, value_of

PARAMS = (
    "PKPK", "MAX", "MIN", "TOP", "BASE", "AMPL", "MEAN", "RMS",
    "PER", "FREQ", "RISE", "FALL", "WID", "DUTY", "OVSN",
    "FPRE", "CMEAN", "CRMS",
)
DEFAULT_ITEMS = ("PKPK", "FREQ", "PER", "MEAN", "RMS", "MIN", "MAX", "DUTY")
SOURCES = ("C1", "C2", "C3", "C4")
INVALID_NOTE = (
    "The scope could not measure this (****): make the signal fill the screen "
    "by adjusting v/div, time/div or the trigger level."
)


def query_item(o, source: str, item: str) -> str:
    """Raw response, e.g. 'C1:PAVA FREQ,1.00E+03Hz'."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}")
    if item not in PARAMS:
        raise ValueError(f"Unknown measurement {item!r}; use one of {', '.join(PARAMS)}")
    return o.query(f"{source}:PAVA? {item}")


def measure(o, source: str, items=None) -> dict:
    """{item: {"value": float | None, "unit": str, "note"?: str}}."""
    out = {}
    for item in items or DEFAULT_ITEMS:
        text = value_of(query_item(o, source, item))
        reading = text.split(",", 1)[1] if "," in text else text
        value, unit = split_number(reading)
        entry = {"value": value, "unit": unit}
        if value is None:
            entry["note"] = INVALID_NOTE
        out[item] = entry
    return out
```

`osc_cli/ops/system.py`:

```python
"""Identity, error queue, reset, self-test, calibration and raw commands."""

from __future__ import annotations

from ._parse import value_of


def identify(o) -> dict:
    raw = value_of(o.idn())
    parts = [p.strip() for p in raw.split(",")] + ["", "", "", ""]
    return {
        "manufacturer": parts[0],
        "model": parts[1],
        "serial": parts[2],
        "firmware": parts[3],
        "raw": raw,
    }


def last_error(o) -> dict:
    text = value_of(o.query("SYSTem:ERRor?"))
    code_text, _, message = text.partition(",")
    try:
        code = int(code_text)
    except ValueError:
        return {"code": None, "message": text}
    return {"code": code, "message": message.strip().strip('"')}


def reset(o) -> None:
    o.write("*RST")


def selftest(o) -> str:
    """Raw *TST? response. Not retried: it must not run twice."""
    return o.query("*TST?", retries=0)


def calibrate(o) -> str:
    """Raw *CAL? response. Not retried: it must not run twice."""
    return o.query("*CAL?", retries=0)


def raw_command(o, command: str, expect_response: bool) -> str | None:
    if expect_response:
        return o.query(command, retries=0)
    o.write(command)
    return None
```

`osc_cli/ops/misc.py`:

```python
"""Math channel, display, cursors, frequency counter and setup files."""

from __future__ import annotations

from ._parse import pairs, to_bool, to_float, value_of

MATH_FUNCTIONS = ("FX", "FY", "FZ", "ADD", "SUB", "MUL", "DIV", "FFT")
GRIDS = ("FULL", "HALF", "OFF")
CURSOR_MODES = ("OFF", "TRACK", "HABS", "HREL", "VABS", "VREL")


def query(o, mnemonic: str) -> str:
    """Raw response for a plain query such as 'MATH:FUNC' or 'GRDS'."""
    return o.query(f"{mnemonic}?")


# ---- math ---------------------------------------------------------------
def set_math_function(o, function: str) -> None:
    if function not in MATH_FUNCTIONS:
        raise ValueError(f"function must be one of {', '.join(MATH_FUNCTIONS)}")
    o.write(f"MATH:FUNC {function}")


def set_math_offset(o, offset: float) -> None:
    o.write(f"MATH:OFST {offset}")


def set_math_scale(o, scale: float) -> None:
    o.write(f"MATH:SCALE {scale}")


def read_math(o) -> dict:
    return {
        "function": value_of(query(o, "MATH:FUNC")),
        "offset": to_float(value_of(query(o, "MATH:OFST"))),
        "scale": to_float(value_of(query(o, "MATH:SCALE"))),
    }


def apply_math(o, function=None, offset=None, scale=None) -> dict:
    if function is not None:
        set_math_function(o, function)
    if offset is not None:
        set_math_offset(o, offset)
    if scale is not None:
        set_math_scale(o, scale)
    return read_math(o)


# ---- display and cursors -------------------------------------------------
def set_grid(o, grid: str) -> None:
    if grid not in GRIDS:
        raise ValueError(f"grid must be one of {', '.join(GRIDS)}")
    o.write(f"GRDS {grid}")


def set_intensity(o, intensity: int) -> None:
    o.write(f"INTS TRACE,{intensity}")


def set_menu(o, value) -> None:
    if isinstance(value, bool):
        value = "ON" if value else "OFF"
    o.write(f"MENU {value}")


def set_cursor_mode(o, mode: str) -> None:
    if mode not in CURSOR_MODES:
        raise ValueError(f"cursor_mode must be one of {', '.join(CURSOR_MODES)}")
    o.write(f"CRMS {mode}")


def read_display(o) -> dict:
    trace = to_float(pairs(value_of(query(o, "INTS"))).get("TRACE", ""))
    return {
        "grid": value_of(query(o, "GRDS")),
        "intensity": int(trace) if trace is not None else None,
        "menu": to_bool(value_of(query(o, "MENU"))),
        "cursor_mode": value_of(query(o, "CRMS")),
    }


def apply_display(o, grid=None, intensity=None, menu=None, cursor_mode=None) -> dict:
    if grid is not None:
        set_grid(o, grid)
    if intensity is not None:
        set_intensity(o, intensity)
    if menu is not None:
        set_menu(o, menu)
    if cursor_mode is not None:
        set_cursor_mode(o, cursor_mode)
    return read_display(o)


# ---- frequency counter -----------------------------------------------------
def set_counter(o, enabled: bool) -> None:
    o.write(f"FCNT STATE,{'ON' if enabled else 'OFF'}")


def read_counter(o) -> dict:
    raw = query(o, "FCNT")
    fields = pairs(value_of(raw))
    return {
        "enabled": fields["STATE"].upper() == "ON" if "STATE" in fields else None,
        "frequency_hz": to_float(fields.get("FRQ", "")),
        "raw": raw,
    }


# ---- setup files stored on the scope ---------------------------------------
def _check_path(path: str) -> None:
    if not path or '"' in path:
        raise ValueError("Setup path must be non-empty and contain no double quotes")


def save_setup(o, path: str) -> None:
    _check_path(path)
    o.write(f'STORE_SETUP FILE,"{path}"')


def recall_setup(o, path: str) -> None:
    _check_path(path)
    o.write(f'RECALL_SETUP FILE,"{path}"')
```

- [ ] **Step 4: Refactorizar los comandos**

`osc_cli/commands/measure.py`:

```python
"""Automatic measurements via the LeCroy PAVA parameter readout.

Syntax: C<n>:PAVA? <param>  ->  "C<n>:PAVA <param>,<value><unit>"
The command strings live in osc_cli.ops.measure.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import measure as ops_measure

PARAMS = ops_measure.PARAMS
SOURCES = ops_measure.SOURCES


@click.group(name="measure")
def measure_group():
    """Automatic measurements (PAVA readout)."""


@measure_group.command("item")
@click.option("--item", "-i", type=click.Choice(PARAMS), required=True, help="Measurement type.")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True, help="Source channel.")
@click.pass_context
def item(ctx, item, source):
    """Query a single measurement (e.g. --item VPP --source C1)."""
    click.echo(ops_measure.query_item(osc(ctx), source, item))


@measure_group.command("all")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def all_(ctx, source):
    """Query all common measurements for a channel."""
    o = osc(ctx)
    for p in ["PKPK", "MAX", "MIN", "MEAN", "RMS", "PER", "FREQ", "DUTY", "RISE", "FALL"]:
        try:
            val = ops_measure.query_item(o, source, p)
            click.echo(val)
        except Exception as e:  # noqa: BLE001
            click.echo(f"{p}: (error: {e})")


@measure_group.command("vpp")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def vpp(ctx, source):
    click.echo(ops_measure.query_item(osc(ctx), source, "PKPK"))


@measure_group.command("freq")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def freq(ctx, source):
    click.echo(ops_measure.query_item(osc(ctx), source, "FREQ"))


@measure_group.command("rms")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def rms(ctx, source):
    click.echo(ops_measure.query_item(osc(ctx), source, "RMS"))


@measure_group.command("mean")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def mean(ctx, source):
    click.echo(ops_measure.query_item(osc(ctx), source, "MEAN"))


@measure_group.command("period")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def period(ctx, source):
    click.echo(ops_measure.query_item(osc(ctx), source, "PER"))
```

`osc_cli/commands/system.py`:

```python
"""System, utility, and IEEE-488.2 common commands (LeCroy X-Stream dialect)."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import acquisition as ops_acq
from ..ops import system as ops_system


@click.group(name="system")
def system_group():
    """System identity, status, clock, and common commands."""


@system_group.command("idn")
@click.pass_context
def idn(ctx):
    """Return the instrument identification string (*IDN?)."""
    click.echo(osc(ctx).idn())


@system_group.command("reset")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def reset(ctx, yes):
    """Reset the oscilloscope to factory defaults (*RST)."""
    if not yes:
        click.confirm("This resets the oscilloscope to factory defaults. Continue?", abort=True)
    ops_system.reset(osc(ctx))
    click.echo("Reset complete.")


@system_group.command("error")
@click.pass_context
def error(ctx):
    """Query the next error in the error queue (SYST:ERR?)."""
    click.echo(osc(ctx).query("SYSTem:ERRor?"))


@system_group.command("clear")
@click.pass_context
def clear(ctx):
    """Clear the status registers and error queue (*CLS)."""
    osc(ctx).write("*CLS")


@system_group.command("opc")
@click.pass_context
def opc(ctx):
    """Wait for pending operations to complete (*OPC?)."""
    click.echo(osc(ctx).query("*OPC?"))


@system_group.command("trigger")
@click.pass_context
def trigger(ctx):
    """Send a software trigger (*TRG)."""
    ops_acq.force(osc(ctx))


@system_group.command("selftest")
@click.pass_context
def selftest(ctx):
    """Run self-test and report the status (*TST?)."""
    click.echo(ops_system.selftest(osc(ctx)))


@system_group.command("calibrate")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def calibrate(ctx, yes):
    """Run internal self-calibration (*CAL?)."""
    if not yes:
        click.confirm("Self-calibration will run on the oscilloscope. Continue?", abort=True)
    click.echo(ops_system.calibrate(osc(ctx)))


@system_group.command("version")
@click.pass_context
def version(ctx):
    """Query the SCPI version (SYST:VERS?)."""
    click.echo(osc(ctx).query("SYSTem:VERSion?"))


@system_group.command("scopeid")
@click.pass_context
def scopeid(ctx):
    """Query the unique scope ID (SCOPEID?)."""
    click.echo(osc(ctx).query("SCOPEID?"))


@system_group.command("date")
@click.argument("value", required=False)
@click.pass_context
def date(ctx, value):
    """Get/set the date (YYYYMMDD)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("SYSTem:DATE?"))
    else:
        o.write(f"SYSTem:DATE {value}")
        click.echo(f"Date set to {value}")


@system_group.command("time")
@click.argument("value", required=False)
@click.pass_context
def time_(ctx, value):
    """Get/set the time (HHMMSS)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("SYSTem:TIME?"))
    else:
        o.write(f"SYSTem:TIME {value}")
        click.echo(f"Time set to {value}")


@system_group.command("header")
@click.argument("value", type=click.Choice(["SHORT", "LONG", "OFF"]), required=False)
@click.pass_context
def header(ctx, value):
    """Get/set response header mode (CHDR)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("CHDR?"))
    else:
        o.write(f"CHDR {value}")
        click.echo(f"Header mode = {value}")
```

`osc_cli/commands/math.py`:

```python
"""Math channel, display, and cursor commands (LeCroy dialect)."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import misc as ops_misc


@click.group(name="math")
def math_group():
    """Math channel control (MATH:...)."""


@math_group.command("function")
@click.argument("value", type=click.Choice(ops_misc.MATH_FUNCTIONS), required=False)
@click.pass_context
def function(ctx, value):
    """Get/set the math function via MATH:FUNC."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "MATH:FUNC"))
    else:
        ops_misc.set_math_function(o, value)
        click.echo(f"Math function = {value}")


@math_group.command("offset")
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, value):
    """Get/set math vertical offset via MATH:OFST."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "MATH:OFST"))
    else:
        ops_misc.set_math_offset(o, value)
        click.echo(f"Math offset = {value}")


@math_group.command("scale")
@click.argument("value", type=float, required=False)
@click.pass_context
def scale(ctx, value):
    """Get/set math vertical scale via MATH:SCALE."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "MATH:SCALE"))
    else:
        ops_misc.set_math_scale(o, value)
        click.echo(f"Math scale = {value}")


@click.group(name="display")
def display_group():
    """Display and rendering control."""


@display_group.command("grid")
@click.argument("value", type=click.Choice(ops_misc.GRIDS), required=False)
@click.pass_context
def grid(ctx, value):
    """Get/set grid display via GRDS."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "GRDS"))
    else:
        ops_misc.set_grid(o, value)
        click.echo(f"Grid = {value}")


@display_group.command("intensity")
@click.argument("value", type=int, required=False)
@click.pass_context
def intensity(ctx, value):
    """Get/set trace intensity via INTS."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "INTS"))
    else:
        ops_misc.set_intensity(o, value)
        click.echo(f"Trace intensity = {value}")


@display_group.command("menu")
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def menu(ctx, value):
    """Get/set menu display via MENU."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "MENU"))
    else:
        ops_misc.set_menu(o, value)
        click.echo(f"Menu = {value}")


@click.group(name="cursor")
def cursor_group():
    """Cursor control."""


@cursor_group.command("mode")
@click.argument("value", type=click.Choice(ops_misc.CURSOR_MODES), required=False)
@click.pass_context
def mode(ctx, value):
    """Get/set cursor mode via CRMS."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "CRMS"))
    else:
        ops_misc.set_cursor_mode(o, value)
        click.echo(f"Cursor mode = {value}")
```

`osc_cli/commands/advanced.py`:

```python
"""Counter (FCNT), save/recall, and miscellaneous commands (LeCroy dialect)."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import misc as ops_misc


@click.group(name="counter")
def counter_group():
    """Frequency counter (FCNT)."""


@counter_group.command("on")
@click.pass_context
def counter_on(ctx):
    """Enable the frequency counter."""
    ops_misc.set_counter(osc(ctx), True)
    click.echo("Counter enabled.")


@counter_group.command("off")
@click.pass_context
def counter_off(ctx):
    """Disable the frequency counter."""
    ops_misc.set_counter(osc(ctx), False)
    click.echo("Counter disabled.")


@counter_group.command("status")
@click.pass_context
def counter_status(ctx):
    """Show counter status and values."""
    click.echo(ops_misc.query(osc(ctx), "FCNT"))


@counter_group.command("freq")
@click.pass_context
def counter_freq(ctx):
    """Query the measured frequency (Hz)."""
    # FCNT? returns a list of KEY,VALUE pairs; extract FRQ.
    o = osc(ctx)
    resp = ops_misc.query(o, "FCNT")
    for part in resp.split(","):
        if part.startswith("FRQ"):
            click.echo(part)
            return
    click.echo(resp)


@click.group(name="save")
def save_group():
    """Save/recall setups and waveforms."""


@save_group.command("setup")
@click.argument("path", required=False)
@click.pass_context
def setup(ctx, path):
    """Save the current setup to a file on the scope."""
    o = osc(ctx)
    if path is None:
        click.echo("Usage: osc save setup <path>")
    else:
        ops_misc.save_setup(o, path)
        click.echo(f"Setup saved to {path}")


@save_group.command("recall-setup")
@click.argument("path")
@click.pass_context
def recall_setup(ctx, path):
    """Recall a saved setup."""
    ops_misc.recall_setup(osc(ctx), path)
    click.echo(f"Setup recalled from {path}")
```

- [ ] **Step 5: Suite completa**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add osc_cli/ops/measure.py osc_cli/ops/system.py osc_cli/ops/misc.py osc_cli/commands/measure.py osc_cli/commands/system.py osc_cli/commands/math.py osc_cli/commands/advanced.py tests/test_cli_measure_misc.py tests/test_ops_measure_system_misc.py
git commit -m "Extract measure, system and misc ops"
```

---

### Task 7: Ops del generador AWG

**Files:**
- Create: `osc_cli/ops/awg.py`
- Modify: `osc_cli/commands/awg.py` (reemplazo completo)
- Test: `tests/test_cli_awg.py`, `tests/test_ops_awg.py`

**Interfaces:**
- Consumes: `_parse` (Task 4), `OscError` (Task 2).
- Produces: `awg.WAVE_TYPES`, `LOADS`, `ARB_WAVEFORMS`, `SWEEP_DIRECTIONS`; consultas crudas `query_basic/query_output/query_arb/query_modulation/query_sync/query_burst/query_sweep(o, retries=3) -> str`; escrituras `write_basic(o, key, value)`, `set_output(o, enabled)`, `set_load(o, load)`, `set_arb(o, name)`, `set_modulation(o, enabled)`, `set_sync(o, enabled)`, `write_burst(o, enabled=None, cycles=None, period=None)`, `write_sweep(o, enabled=None, start=None, stop=None, time=None, direction=None)`; lecturas `read(o) -> dict` (claves `enabled, load, wave, freq_hz, amp_vpp, offset_v, phase_deg, duty_pct, arb, modulation, sync, burst, sweep`), `read_burst(o) -> {enabled, cycles, period_s}`, `read_sweep(o) -> {enabled, start_hz, stop_hz, time_s, direction}`; `apply(o, enabled=None, wave=None, freq=None, amp=None, offset=None, phase=None, duty=None, load=None, arb=None, modulation=None, sync=None) -> dict`, `apply_burst(...) -> dict`, `apply_sweep(...) -> dict`.

- [ ] **Step 1: Tests de caracterización**

`tests/test_cli_awg.py`:

```python
import pytest

from tests.fakes import FakeOscilloscope, run_cli

R = FakeOscilloscope().responses

CASES = [
    (["awg", "status"], [("q", "C1:OUTP?"), ("q", "C1:BSWV?"), ("q", "C1:MDWV?")],
     f"Output : {R['C1:OUTP?']}\nWave   : {R['C1:BSWV?']}\nMod    : {R['C1:MDWV?']}\n"),
    (["awg", "on"], [("w", "C1:OUTP ON")], "AWG output enabled.\n"),
    (["awg", "off"], [("w", "C1:OUTP OFF")], "AWG output disabled.\n"),
    (["awg", "wave", "SQUARE"], [("w", "C1:BSWV WVTP,SQUARE")], "Waveform type = SQUARE\n"),
    (["awg", "freq", "5000"], [("w", "C1:BSWV FRQ,5000.0")], "Frequency = 5000.0 Hz\n"),
    (["awg", "amp", "2"], [("w", "C1:BSWV AMP,2.0")], "Amplitude = 2.0 Vpp\n"),
    (["awg", "duty", "25"], [("w", "C1:BSWV DUTY,25.0")], "Duty cycle = 25.0%\n"),
    (["awg", "load", "50"], [("w", "C1:OUTP LOAD,50")], "Load = 50\n"),
    (["awg", "set", "--wave", "SQUARE", "--freq", "5000", "--on"],
     [("w", "C1:BSWV WVTP,SQUARE"), ("w", "C1:BSWV FRQ,5000.0"), ("w", "C1:OUTP ON"), ("q", "C1:BSWV?")],
     f"AWG configured.\n{R['C1:BSWV?']}\n"),
    (["awg", "arb"], [("q", "C1:ARWV?")], f"{R['C1:ARWV?']}\n"),
    (["awg", "arb", "StairUp"], [("w", "C1:ARWV INDEX,StairUp"), ("w", "C1:BSWV WVTP,ARB")],
     "Arbitrary waveform = StairUp\n"),
    (["awg", "burst", "--on", "--cycles", "10"],
     [("w", "C1:BTWV STATE,ON"), ("w", "C1:BTWV NCYC,10"), ("q", "C1:BTWV?")], f"{R['C1:BTWV?']}\n"),
    (["awg", "sweep", "--start", "100", "--stop", "1000"],
     [("w", "C1:SWWV START,100.0"), ("w", "C1:SWWV STOP,1000.0"), ("q", "C1:SWWV?")], f"{R['C1:SWWV?']}\n"),
    (["awg", "modulate", "--on"], [("w", "C1:MDWV STATE,ON"), ("q", "C1:MDWV?")], f"{R['C1:MDWV?']}\n"),
    (["awg", "sync", "ON"], [("w", "C1:SYNC ON")], "Sync output = ON\n"),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_awg_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log
```

Run: `.venv/bin/python -m pytest tests/test_cli_awg.py -q`
Expected: PASS (15).

- [ ] **Step 2: Tests de las ops que fallan**

`tests/test_ops_awg.py`:

```python
import pytest

from osc_cli.ops import awg
from tests.fakes import FakeOscilloscope

STATE = {
    "enabled": False, "load": "HZ", "wave": "SINE", "freq_hz": 1000.0, "amp_vpp": 4.0,
    "offset_v": 0.0, "phase_deg": 0.0, "duty_pct": None, "arb": "StairUp",
    "modulation": False, "sync": False,
    "burst": {"enabled": False, "cycles": 1, "period_s": 0.01},
    "sweep": {"enabled": False, "start_hz": 100.0, "stop_hz": 1000.0, "time_s": 1.0, "direction": "UP"},
}


def test_read():
    assert awg.read(FakeOscilloscope()) == STATE


def test_read_tolerates_unsupported_queries():
    fake = FakeOscilloscope()
    del fake.responses["C1:SYNC?"]
    del fake.responses["C1:SWWV?"]
    state = awg.read(fake)
    assert state["sync"] is None and state["sweep"] is None


def test_apply_turns_output_on_last():
    fake = FakeOscilloscope()
    awg.apply(fake, enabled=True, wave="SQUARE", freq=5000, load="50")
    assert fake.writes == ["C1:BSWV WVTP,SQUARE", "C1:BSWV FRQ,5000", "C1:OUTP LOAD,50", "C1:OUTP ON"]


def test_apply_turns_output_off_first():
    fake = FakeOscilloscope()
    awg.apply(fake, enabled=False, amp=1)
    assert fake.writes == ["C1:OUTP OFF", "C1:BSWV AMP,1"]


def test_apply_arb_selects_arb_wave():
    fake = FakeOscilloscope()
    awg.apply(fake, arb="Upramp", modulation=True, sync=False)
    assert fake.writes == ["C1:ARWV INDEX,Upramp", "C1:BSWV WVTP,ARB", "C1:MDWV STATE,ON", "C1:SYNC OFF"]


@pytest.mark.parametrize("kwargs,match", [
    ({"arb": "StairUp", "wave": "SINE"}, "arb"),
    ({"wave": "TRIANGLE"}, "wave"),
    ({"load": "75"}, "load"),
    ({"arb": "Nope"}, "arb"),
])
def test_apply_validates(kwargs, match):
    with pytest.raises(ValueError, match=match):
        awg.apply(FakeOscilloscope(), **kwargs)


def test_burst_and_sweep():
    fake = FakeOscilloscope()
    assert awg.apply_burst(fake, enabled=True, cycles=5)["cycles"] == 1  # fake read-back
    assert awg.apply_sweep(fake, start=10, direction="DOWN")["direction"] == "UP"
    assert fake.writes == ["C1:BTWV STATE,ON", "C1:BTWV NCYC,5", "C1:SWWV START,10", "C1:SWWV DIR,DOWN"]
    with pytest.raises(ValueError, match="direction"):
        awg.apply_sweep(fake, direction="SIDEWAYS")
```

Run: `.venv/bin/python -m pytest tests/test_ops_awg.py -q`
Expected: FAIL con `ImportError`.

- [ ] **Step 3: Implementar `osc_cli/ops/awg.py`**

`osc_cli/ops/awg.py`:

```python
"""Built-in function/arbitrary waveform generator (Siglent-style C1: commands).

Unlike the rest of the scope, the AWG uses Siglent SCPI: C1:BSWV (basic wave),
C1:OUTP (output/load), C1:ARWV (arbitrary), C1:MDWV (modulation), C1:SYNC,
C1:BTWV (burst) and C1:SWWV (sweep).
"""

from __future__ import annotations

from ..device import OscError
from ._parse import pairs, to_float, value_of

WAVE_TYPES = ("SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC")
LOADS = ("HZ", "50")
# Arbitrary waveform names discovered on the device (via C1:ARWV INDEX,n).
ARB_WAVEFORMS = (
    "StairUp", "StairDn", "StairUD", "Ppulse", "Npulse", "Trapezia",
    "Upramp", "Dnramp", "ExpFal", "ExpRise",
)
SWEEP_DIRECTIONS = ("UP", "DOWN")


def _on_off(enabled: bool) -> str:
    return "ON" if enabled else "OFF"


# ---- raw queries (the CLI prints these verbatim) ------------------------------
def query_basic(o, retries: int = 3) -> str:
    return o.query("C1:BSWV?", retries=retries)


def query_output(o, retries: int = 3) -> str:
    return o.query("C1:OUTP?", retries=retries)


def query_arb(o, retries: int = 3) -> str:
    return o.query("C1:ARWV?", retries=retries)


def query_modulation(o, retries: int = 3) -> str:
    return o.query("C1:MDWV?", retries=retries)


def query_sync(o, retries: int = 3) -> str:
    return o.query("C1:SYNC?", retries=retries)


def query_burst(o, retries: int = 3) -> str:
    return o.query("C1:BTWV?", retries=retries)


def query_sweep(o, retries: int = 3) -> str:
    return o.query("C1:SWWV?", retries=retries)


# ---- writes -------------------------------------------------------------------
def write_basic(o, key: str, value) -> None:
    """One C1:BSWV parameter, e.g. write_basic(o, "FRQ", 1000)."""
    if key == "WVTP" and value not in WAVE_TYPES:
        raise ValueError(f"wave must be one of {', '.join(WAVE_TYPES)}")
    o.write(f"C1:BSWV {key},{value}")


def set_output(o, enabled: bool) -> None:
    o.write(f"C1:OUTP {_on_off(enabled)}")


def set_load(o, load: str) -> None:
    if load not in LOADS:
        raise ValueError(f"load must be one of {', '.join(LOADS)}")
    o.write(f"C1:OUTP LOAD,{load}")


def set_arb(o, name: str) -> None:
    if name not in ARB_WAVEFORMS:
        raise ValueError(f"arb must be one of {', '.join(ARB_WAVEFORMS)}")
    o.write(f"C1:ARWV INDEX,{name}")
    o.write("C1:BSWV WVTP,ARB")


def set_modulation(o, enabled: bool) -> None:
    o.write(f"C1:MDWV STATE,{_on_off(enabled)}")


def set_sync(o, enabled) -> None:
    value = _on_off(enabled) if isinstance(enabled, bool) else enabled
    o.write(f"C1:SYNC {value}")


def write_burst(o, enabled=None, cycles=None, period=None) -> None:
    if enabled is not None:
        o.write(f"C1:BTWV STATE,{_on_off(enabled)}")
    if cycles is not None:
        o.write(f"C1:BTWV NCYC,{cycles}")
    if period is not None:
        o.write(f"C1:BTWV PRD,{period}")


def write_sweep(o, enabled=None, start=None, stop=None, time=None, direction=None) -> None:
    if direction is not None and direction not in SWEEP_DIRECTIONS:
        raise ValueError("direction must be UP or DOWN")
    if enabled is not None:
        o.write(f"C1:SWWV STATE,{_on_off(enabled)}")
    for key, value in (("START", start), ("STOP", stop), ("TIME", time), ("DIR", direction)):
        if value is not None:
            o.write(f"C1:SWWV {key},{value}")


# ---- structured reads -----------------------------------------------------------
def _num(fields: dict, key: str):
    return to_float(fields.get(key, ""))


def read_burst(o, retries: int = 3) -> dict:
    p = pairs(value_of(query_burst(o, retries)))
    cycles = _num(p, "NCYC")
    return {
        "enabled": p.get("STATE", "").upper() == "ON",
        "cycles": int(cycles) if cycles is not None else None,
        "period_s": _num(p, "PRD"),
    }


def read_sweep(o, retries: int = 3) -> dict:
    p = pairs(value_of(query_sweep(o, retries)))
    return {
        "enabled": p.get("STATE", "").upper() == "ON",
        "start_hz": _num(p, "START"),
        "stop_hz": _num(p, "STOP"),
        "time_s": _num(p, "TIME"),
        "direction": p.get("DIR"),
    }


def _optional(fn, o):
    """Read something the firmware may not support; None instead of an error."""
    try:
        return fn(o, retries=0)
    except OscError:
        return None


def read(o) -> dict:
    basic = pairs(value_of(query_basic(o)))
    out_tokens = value_of(query_output(o)).split(",")
    output = pairs(",".join(out_tokens[1:]))
    arb = _optional(query_arb, o)
    modulation = _optional(query_modulation, o)
    sync = _optional(query_sync, o)
    return {
        "enabled": out_tokens[0].strip().upper() == "ON",
        "load": output.get("LOAD"),
        "wave": basic.get("WVTP"),
        "freq_hz": _num(basic, "FRQ"),
        "amp_vpp": _num(basic, "AMP"),
        "offset_v": _num(basic, "OFST"),
        "phase_deg": _num(basic, "PHSE"),
        "duty_pct": _num(basic, "DUTY"),
        "arb": pairs(value_of(arb)).get("NAME") if arb else None,
        "modulation": pairs(value_of(modulation)).get("STATE", "").upper() == "ON" if modulation else None,
        "sync": value_of(sync).upper() == "ON" if sync else None,
        "burst": _optional(read_burst, o),
        "sweep": _optional(read_sweep, o),
    }


def apply(o, enabled=None, wave=None, freq=None, amp=None, offset=None, phase=None,
          duty=None, load=None, arb=None, modulation=None, sync=None) -> dict:
    """Configure the generator. The output is switched off first and on last."""
    if arb is not None and wave not in (None, "ARB"):
        raise ValueError("arb selects wave=ARB; omit wave or set it to ARB")
    if enabled is False:
        set_output(o, False)
    if arb is not None:
        set_arb(o, arb)
    elif wave is not None:
        write_basic(o, "WVTP", wave)
    for key, value in (("FRQ", freq), ("AMP", amp), ("OFST", offset), ("PHSE", phase), ("DUTY", duty)):
        if value is not None:
            write_basic(o, key, value)
    if load is not None:
        set_load(o, load)
    if modulation is not None:
        set_modulation(o, modulation)
    if sync is not None:
        set_sync(o, sync)
    if enabled is True:
        set_output(o, True)
    return read(o)


def apply_burst(o, enabled=None, cycles=None, period=None) -> dict:
    write_burst(o, enabled, cycles, period)
    return read_burst(o)


def apply_sweep(o, enabled=None, start=None, stop=None, time=None, direction=None) -> dict:
    write_sweep(o, enabled, start, stop, time, direction)
    return read_sweep(o)
```

- [ ] **Step 4: Refactorizar `osc_cli/commands/awg.py`**

`osc_cli/commands/awg.py`:

```python
"""AWG (arbitrary waveform generator) control commands.

The SDS1104X-E has an integrated function/AWG generator controlled via a
Siglent-style command set (NOT the LeCroy X-Stream dialect used by the rest
of the scope). The command strings live in osc_cli.ops.awg.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import awg as ops_awg

WAVE_TYPES = ops_awg.WAVE_TYPES
LOADS = ops_awg.LOADS
ARB_WAVEFORMS = ops_awg.ARB_WAVEFORMS


@click.group(name="awg")
def awg_group():
    """Waveform generator (AWG) control."""


def _echo_part(full: str, prefix: str, fallback: bool = False) -> None:
    for part in full.split(","):
        if part.startswith(prefix):
            click.echo(part)
            return
    if fallback:
        click.echo(full)


def _basic_get_or_set(ctx, key, prefix, value, message):
    o = osc(ctx)
    if value is None:
        _echo_part(ops_awg.query_basic(o), prefix)
    else:
        ops_awg.write_basic(o, key, value)
        click.echo(message.format(value=value))


@awg_group.command("status")
@click.pass_context
def status(ctx):
    """Show the full AWG configuration."""
    o = osc(ctx)
    click.echo(f"Output : {ops_awg.query_output(o)}")
    click.echo(f"Wave   : {ops_awg.query_basic(o)}")
    click.echo(f"Mod    : {ops_awg.query_modulation(o)}")


@awg_group.command("on")
@click.pass_context
def on(ctx):
    """Turn the AWG output on."""
    ops_awg.set_output(osc(ctx), True)
    click.echo("AWG output enabled.")


@awg_group.command("off")
@click.pass_context
def off(ctx):
    """Turn the AWG output off."""
    ops_awg.set_output(osc(ctx), False)
    click.echo("AWG output disabled.")


@awg_group.command("wave")
@click.argument("value", type=click.Choice(WAVE_TYPES), required=False)
@click.pass_context
def wave(ctx, value):
    """Get/set the waveform type (SINE/SQUARE/RAMP/PULSE/NOISE/ARB/DC)."""
    o = osc(ctx)
    if value is None:
        _echo_part(ops_awg.query_basic(o), "WVTP", fallback=True)
    else:
        ops_awg.write_basic(o, "WVTP", value)
        click.echo(f"Waveform type = {value}")


@awg_group.command("freq")
@click.argument("value", type=float, required=False)
@click.pass_context
def freq(ctx, value):
    """Get/set the output frequency (Hz)."""
    _basic_get_or_set(ctx, "FRQ", "FRQ", value, "Frequency = {value} Hz")


@awg_group.command("amp")
@click.argument("value", type=float, required=False)
@click.pass_context
def amp(ctx, value):
    """Get/set the amplitude (Vpp)."""
    _basic_get_or_set(ctx, "AMP", "AMP,", value, "Amplitude = {value} Vpp")


@awg_group.command("offset")
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, value):
    """Get/set the DC offset (V)."""
    _basic_get_or_set(ctx, "OFST", "OFST", value, "Offset = {value} V")


@awg_group.command("phase")
@click.argument("value", type=float, required=False)
@click.pass_context
def phase(ctx, value):
    """Get/set the phase (degrees)."""
    _basic_get_or_set(ctx, "PHSE", "PHSE", value, "Phase = {value} deg")


@awg_group.command("duty")
@click.argument("value", type=float, required=False)
@click.pass_context
def duty(ctx, value):
    """Get/set the square-wave duty cycle (%)."""
    _basic_get_or_set(ctx, "DUTY", "DUTY", value, "Duty cycle = {value}%")


@awg_group.command("load")
@click.argument("value", type=click.Choice(LOADS), required=False)
@click.pass_context
def load(ctx, value):
    """Get/set output load (HZ = high-impedance, 50 = 50 ohm)."""
    o = osc(ctx)
    if value is None:
        _echo_part(ops_awg.query_output(o), "LOAD")
    else:
        ops_awg.set_load(o, value)
        click.echo(f"Load = {value}")


@awg_group.command("set")
@click.option("--wave", "-w", type=click.Choice(WAVE_TYPES), help="Waveform type.")
@click.option("--freq", "-f", type=float, help="Frequency (Hz).")
@click.option("--amp", "-a", type=float, help="Amplitude (Vpp).")
@click.option("--offset", "-o", type=float, help="DC offset (V).")
@click.option("--phase", "-p", type=float, help="Phase (degrees).")
@click.option("--duty", "-d", type=float, help="Duty cycle (%).")
@click.option("--on", "enable", is_flag=True, help="Turn output on.")
@click.option("--off", "disable", is_flag=True, help="Turn output off.")
@click.pass_context
def set_(ctx, wave, freq, amp, offset, phase, duty, enable, disable):
    """Configure multiple AWG parameters at once."""
    o = osc(ctx)
    pairs = [
        (k, v)
        for k, v in (("WVTP", wave), ("FRQ", freq), ("AMP", amp),
                     ("OFST", offset), ("PHSE", phase), ("DUTY", duty))
        if v is not None
    ]
    for k, v in pairs:
        ops_awg.write_basic(o, k, v)
    if enable:
        ops_awg.set_output(o, True)
    if disable:
        ops_awg.set_output(o, False)
    if pairs or enable or disable:
        click.echo("AWG configured.")
        if pairs:
            click.echo(ops_awg.query_basic(o))
    else:
        click.echo(ops_awg.query_basic(o))


@awg_group.command("arb")
@click.argument("name", type=click.Choice(ARB_WAVEFORMS), required=False)
@click.pass_context
def arb(ctx, name):
    """Get/set the arbitrary waveform (built-in shapes)."""
    o = osc(ctx)
    if name is None:
        click.echo(ops_awg.query_arb(o))
    else:
        ops_awg.set_arb(o, name)
        click.echo(f"Arbitrary waveform = {name}")


@awg_group.command("burst")
@click.option("--on", "enable", is_flag=True, help="Enable burst mode.")
@click.option("--off", "disable", is_flag=True, help="Disable burst mode.")
@click.option("--cycles", "-c", type=int, default=None, help="Number of cycles per burst (NCYC).")
@click.option("--period", type=float, default=None, help="Burst period (s).")
@click.pass_context
def burst(ctx, enable, disable, cycles, period):
    """Configure burst mode (C1:BTWV)."""
    o = osc(ctx)
    if enable:
        ops_awg.write_burst(o, enabled=True)
    if disable:
        ops_awg.write_burst(o, enabled=False)
    ops_awg.write_burst(o, cycles=cycles, period=period)
    click.echo(ops_awg.query_burst(o))


@awg_group.command("sweep")
@click.option("--on", "enable", is_flag=True, help="Enable sweep mode.")
@click.option("--off", "disable", is_flag=True, help="Disable sweep mode.")
@click.option("--start", type=float, default=None, help="Start frequency (Hz).")
@click.option("--stop", type=float, default=None, help="Stop frequency (Hz).")
@click.option("--time", "time_", type=float, default=None, help="Sweep time (s).")
@click.option("--direction", type=click.Choice(ops_awg.SWEEP_DIRECTIONS), default=None, help="Sweep direction.")
@click.pass_context
def sweep(ctx, enable, disable, start, stop, time_, direction):
    """Configure frequency sweep (C1:SWWV)."""
    o = osc(ctx)
    if enable:
        ops_awg.write_sweep(o, enabled=True)
    if disable:
        ops_awg.write_sweep(o, enabled=False)
    ops_awg.write_sweep(o, start=start, stop=stop, time=time_, direction=direction)
    click.echo(ops_awg.query_sweep(o))


@awg_group.command("modulate")
@click.option("--on", "enable", is_flag=True, help="Enable modulation.")
@click.option("--off", "disable", is_flag=True, help="Disable modulation.")
@click.pass_context
def modulate(ctx, enable, disable):
    """Enable/disable modulation (C1:MDWV)."""
    o = osc(ctx)
    if enable:
        ops_awg.set_modulation(o, True)
    if disable:
        ops_awg.set_modulation(o, False)
    click.echo(ops_awg.query_modulation(o))


@awg_group.command("sync")
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def sync(ctx, value):
    """Get/set the sync output (C1:SYNC)."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_awg.query_sync(o))
    else:
        ops_awg.set_sync(o, value)
        click.echo(f"Sync output = {value}")
```

- [ ] **Step 5: Suite completa**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add osc_cli/ops/awg.py osc_cli/commands/awg.py tests/test_cli_awg.py tests/test_ops_awg.py
git commit -m "Extract AWG ops with structured read/apply"
```

---

### Task 8: Ops de forma de onda (límite, estadísticas, diezmado, CSV)

**Files:**
- Create: `osc_cli/ops/waveform.py`
- Modify: `osc_cli/commands/waveform.py` (reemplazo completo)
- Test: `tests/test_cli_waveform.py`, `tests/test_ops_waveform.py`

**Interfaces:**
- Consumes: `WaveformRaw`, `parse_wavedesc`, `Oscilloscope.get_waveform_raw` (Task 2); `acquisition.stop` (Task 5); `make_wavedesc_block` y `FakeOscilloscope.honor_sparsing` (Task 2).
- Produces: `waveform.SOURCES`, `DEFAULT_MAX_SAMPLES = 2_000_000`, `sample_count(o, source) -> int|None`, `plan_sparsing(count, max_samples) -> int`, `transfer_deadline(points) -> float`, `fetch(o, source, max_samples=None) -> WaveformRaw`, `to_volts(raw) -> array('d')`, `stats(raw) -> dict` (`n, sample_rate, duration, min, max, vpp, mean, rms, vdiv, offset, horz_interval, horz_offset`), `decimate(raw, max_points) -> list[[t, v]]`, `csv_lines(raw, limit=0)`, `write_csv(raw, path)`, `capture(o, sources, max_points=500, max_samples=DEFAULT_MAX_SAMPLES, csv_path_for=None, progress=None) -> {"sources": {src: stats + points (+csv_path)}, "acquisition_stopped": bool}`.

- [ ] **Step 1: Tests de caracterización**

`tests/test_cli_waveform.py`:

```python
from tests.fakes import FakeOscilloscope, make_wavedesc_block, run_cli

CSV = (
    "index,voltage,time\n"
    "0,0.000000,0.000000000\n"
    "1,0.250000,0.000001000\n"
    "2,0.500000,0.000002000\n"
    "3,-0.015625,0.000003000\n"
    "4,-0.500000,0.000004000\n"
)


def fake_with_wave():
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(bytes([0, 16, 32, 255, 224]), vdiv=0.5, interval=1e-6)
    return fake


def test_capture_prints_csv(monkeypatch):
    result = run_cli(monkeypatch, fake_with_wave(), "waveform", "capture")
    assert result.output == CSV + "\n"


def test_capture_trims_points(monkeypatch):
    result = run_cli(monkeypatch, fake_with_wave(), "waveform", "capture", "-n", "2")
    assert result.output == "".join(CSV.splitlines(keepends=True)[:3]) + "\n"


def test_capture_to_file(monkeypatch, tmp_path):
    out = tmp_path / "w.csv"
    result = run_cli(monkeypatch, fake_with_wave(), "waveform", "capture", "-o", str(out))
    assert result.output == f"Saved 5 samples to {out} (vdiv=0.5, interval=1e-06s)\n"
    assert out.read_text() == CSV


def test_info(monkeypatch):
    result = run_cli(monkeypatch, fake_with_wave(), "waveform", "info")
    assert result.output == (
        "Source        : C1\nPoints        : 5\nVertical div  : 0.5 V/div\n"
        "Vertical off. : 0\nHoriz interval: 1e-06 s\nHoriz offset  : 0 s\n"
        "First valid   : 0\nLast valid    : 4\n"
    )
```

Run: `.venv/bin/python -m pytest tests/test_cli_waveform.py -q`
Expected: PASS (4).

- [ ] **Step 2: Tests de las ops que fallan**

`tests/test_ops_waveform.py`:

```python
import math

import pytest

from osc_cli.device import OscError, parse_wavedesc
from osc_cli.ops import waveform
from tests.fakes import FakeOscilloscope, make_wavedesc_block

CODES = bytes([0, 16, 32, 255, 224])  # 0, 16, 32, -1, -32


def raw_of(codes, **kw):
    return parse_wavedesc(make_wavedesc_block(codes, **kw))


def test_stats_match_direct_computation():
    raw = raw_of(CODES, vdiv=0.5, offset=0.1, interval=1e-6)
    volts = [0.5 / 32 * c - 0.1 for c in (0, 16, 32, -1, -32)]
    s = waveform.stats(raw)
    assert s["n"] == 5
    assert s["min"] == pytest.approx(min(volts))
    assert s["max"] == pytest.approx(max(volts))
    assert s["vpp"] == pytest.approx(max(volts) - min(volts))
    assert s["mean"] == pytest.approx(sum(volts) / 5)
    assert s["rms"] == pytest.approx(math.sqrt(sum(v * v for v in volts) / 5))
    assert s["sample_rate"] == pytest.approx(1e6)
    assert s["duration"] == pytest.approx(5e-6)


def test_stats_rejects_empty():
    with pytest.raises(OscError, match="empty"):
        waveform.stats(raw_of(b""))


def test_decimate_keeps_single_sample_glitch():
    codes = bytearray(10000)
    codes[5003] = 100
    points = waveform.decimate(raw_of(bytes(codes), vdiv=0.32), 100)
    assert len(points) <= 100
    assert max(v for _, v in points) == pytest.approx(1.0)  # 100 * 0.32 / 32


def test_decimate_odd_length_and_two_points():
    codes = bytes(range(0, 127)) + bytes(range(0, 74))  # 201 samples, peak at 126
    points = waveform.decimate(raw_of(codes, vdiv=3.2), 2)
    assert [round(v, 6) for _, v in points] == [0.0, 12.6]


def test_decimate_returns_everything_when_small():
    assert len(waveform.decimate(raw_of(CODES), 500)) == 5


def test_csv_lines_and_limit():
    raw = raw_of(CODES, vdiv=0.5, interval=1e-6)
    lines = list(waveform.csv_lines(raw))
    assert lines[0] == "index,voltage,time"
    assert lines[4] == "3,-0.015625,0.000003000"
    assert len(list(waveform.csv_lines(raw, limit=2))) == 3


def fake_with(codes=CODES, count=None):
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(codes)
    fake.blocks["C2"] = make_wavedesc_block(codes)
    if count is not None:
        fake.responses["SANU? C1"] = f"SANU {count:.2E}pts"
    return fake


def test_fetch_without_limit_skips_sample_count():
    fake = fake_with()
    waveform.fetch(fake, "C1")
    assert fake.log == [("wf", "C1", 1)]


def test_fetch_requests_sparsing_above_limit():
    fake = fake_with(bytes(5000), count=5000)
    fake.honor_sparsing = True
    raw = waveform.fetch(fake, "C1", max_samples=1000)
    assert ("wf", "C1", 5) in fake.log
    assert len(raw.codes) == 1000


def test_fetch_refuses_when_scope_ignores_sparsing():
    fake = fake_with(bytes(5000), count=5000)
    with pytest.raises(OscError, match="OSC_MAX_SAMPLES"):
        waveform.fetch(fake, "C1", max_samples=1000)


def test_capture_multiple_sources_stops_and_writes_csv(tmp_path):
    fake = fake_with()
    seen = []
    result = waveform.capture(
        fake, ["C1", "C2", "C1"], max_points=4,
        csv_path_for=lambda s: tmp_path / f"{s}.csv",
        progress=lambda done, total, msg: seen.append((done, total)),
    )
    assert fake.writes[0] == "STOP"
    assert result["acquisition_stopped"] is True
    assert list(result["sources"]) == ["C1", "C2"]
    assert (tmp_path / "C1.csv").read_text().startswith("index,voltage,time\n0,")
    assert len(result["sources"]["C2"]["points"]) <= 4
    assert seen == [(1, 2), (2, 2)]


def test_capture_single_source_does_not_stop():
    fake = fake_with()
    result = waveform.capture(fake, ["C1"])
    assert "STOP" not in fake.writes
    assert result["acquisition_stopped"] is False
    assert "csv_path" not in result["sources"]["C1"]
```

Run: `.venv/bin/python -m pytest tests/test_ops_waveform.py -q`
Expected: FAIL con `ImportError`.

- [ ] **Step 3: Implementar `osc_cli/ops/waveform.py`**

`osc_cli/ops/waveform.py`:

```python
"""Waveform capture: bounded transfer, statistics, decimation and CSV export.

Samples stay as int8 ADC codes (bytes/array) until they are written out, so a
2M-point capture never becomes millions of Python floats.
"""

from __future__ import annotations

import math
from array import array
from collections import Counter

from ..device import OscError, WaveformRaw
from . import acquisition
from ._parse import to_float, value_of

SOURCES = ("C1", "C2", "C3", "C4")
DEFAULT_MAX_SAMPLES = 2_000_000


def _scale(raw: WaveformRaw) -> float:
    # 8-bit codes span the 8-division grid: 32 codes per division.
    return raw.vdiv / 32.0


def sample_count(o, source: str) -> int | None:
    """Points in the current acquisition (SANU?), or None if unknown."""
    try:
        n = to_float(value_of(o.query(f"SANU? {source}", retries=0)))
    except OscError:
        return None
    return int(n) if n else None


def plan_sparsing(count: int | None, max_samples: int | None) -> int:
    if max_samples is None or count is None or count <= max_samples:
        return 1
    return math.ceil(count / max_samples)


def transfer_deadline(points: int | None) -> float:
    """Seconds allowed for a transfer: 5 s + 2 s per million points."""
    if points is None:
        return 600.0
    return 5.0 + 2.0 * points / 1e6


def fetch(o, source: str, max_samples: int | None = None) -> WaveformRaw:
    """Transfer one channel, asking the scope to sparse it above max_samples.

    max_samples=None transfers everything (CLI behaviour).
    """
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}")
    count = sample_count(o, source) if max_samples is not None else None
    k = plan_sparsing(count, max_samples)
    expected = math.ceil(count / k) if count else None
    raw = o.get_waveform_raw(source, sparsing=k, deadline_s=transfer_deadline(expected))
    if max_samples is not None and len(raw.codes) > max_samples * 1.05:
        ignored = " and the scope ignored sparsing" if k > 1 else ""
        raise OscError(
            f"{source}: the capture holds {len(raw.codes)} points, above the limit of "
            f"{max_samples}{ignored}. Reduce the memory depth with "
            "siglent_set_timebase(memory=...) or raise OSC_MAX_SAMPLES."
        )
    return raw


def to_volts(raw: WaveformRaw) -> array:
    scale = _scale(raw)
    return array("d", (scale * c - raw.offset for c in array("b", raw.codes)))


def stats(raw: WaveformRaw) -> dict:
    """Summary statistics from a 256-bin histogram of the ADC codes."""
    n = len(raw.codes)
    if n == 0:
        raise OscError("The scope returned an empty waveform.")
    scale = _scale(raw)
    total = total_sq = 0.0
    lo, hi = 127, -128
    for code, count in Counter(raw.codes).items():
        signed = code - 256 if code >= 128 else code
        v = scale * signed - raw.offset
        total += v * count
        total_sq += v * v * count
        lo, hi = min(lo, signed), max(hi, signed)
    dt = raw.horz_interval
    vmin, vmax = scale * lo - raw.offset, scale * hi - raw.offset
    return {
        "n": n,
        "sample_rate": 1.0 / dt if dt > 0 else None,
        "duration": n * dt,
        "min": vmin,
        "max": vmax,
        "vpp": vmax - vmin,
        "mean": total / n,
        "rms": math.sqrt(total_sq / n),
        "vdiv": raw.vdiv,
        "offset": raw.offset,
        "horz_interval": dt,
        "horz_offset": raw.horz_offset,
    }


def decimate(raw: WaveformRaw, max_points: int) -> list[list[float]]:
    """At most max_points [time, volts] pairs keeping each bucket's min and max.

    A plain every-k-th-sample decimation would drop narrow glitches; min/max
    buckets keep them.
    """
    if max_points < 2:
        raise ValueError("max_points must be at least 2")
    codes = array("b", raw.codes)
    n = len(codes)
    scale = _scale(raw)

    def point(i):
        return [raw.horz_interval * i + raw.horz_offset, scale * codes[i] - raw.offset]

    if n <= max_points:
        return [point(i) for i in range(n)]
    buckets = max_points // 2
    out = []
    for b in range(buckets):
        lo, hi = b * n // buckets, (b + 1) * n // buckets
        segment = codes[lo:hi]
        i_min = lo + segment.index(min(segment))
        i_max = lo + segment.index(max(segment))
        for i in sorted({i_min, i_max}):
            out.append(point(i))
    return out


def csv_lines(raw: WaveformRaw, limit: int = 0):
    """'index,voltage,time' header plus one line per sample (CLI format)."""
    yield "index,voltage,time"
    codes = array("b", raw.codes)
    n = min(len(codes), raw.wave_count) if raw.wave_count > 0 else len(codes)
    if limit > 0:
        n = min(n, limit)
    scale = _scale(raw)
    for i in range(n):
        v = scale * codes[i] - raw.offset
        t = raw.horz_interval * i + raw.horz_offset
        yield f"{i},{v:.6f},{t:.9f}"


def write_csv(raw: WaveformRaw, path) -> None:
    with open(path, "w") as f:
        for line in csv_lines(raw):
            f.write(line + "\n")


def capture(o, sources, max_points: int = 500, max_samples: int | None = DEFAULT_MAX_SAMPLES,
            csv_path_for=None, progress=None) -> dict:
    """Capture one or more channels.

    With more than one source the acquisition is stopped first so every
    channel comes from the same trigger. csv_path_for(source) -> path enables
    CSV export; progress(done, total, message) reports per-channel progress.
    """
    sources = list(dict.fromkeys(sources))
    if not sources:
        raise ValueError("Give at least one source channel.")
    stopped = len(sources) > 1
    if stopped:
        acquisition.stop(o)
    result = {}
    for i, source in enumerate(sources, start=1):
        raw = fetch(o, source, max_samples)
        entry = stats(raw)
        entry["points"] = decimate(raw, max_points)
        if csv_path_for is not None:
            path = csv_path_for(source)
            write_csv(raw, path)
            entry["csv_path"] = str(path)
        result[source] = entry
        if progress is not None:
            progress(i, len(sources), f"{source} captured")
    return {"sources": result, "acquisition_stopped": stopped}
```

- [ ] **Step 4: Refactorizar `osc_cli/commands/waveform.py`**

`osc_cli/commands/waveform.py`:

```python
"""Waveform data capture commands (LeCroy block format)."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import waveform as ops_wave


@click.group(name="waveform")
def waveform_group():
    """Capture waveform sample data."""


@waveform_group.command("capture")
@click.option("--source", "-s", type=click.Choice(ops_wave.SOURCES), default="C1", show_default=True)
@click.option("--output", "-o", default=None, help="Output CSV file. Prints to stdout if omitted.")
@click.option("--points", "-n", type=int, default=0, help="Max points to keep, trimmed client-side (0 = all).")
@click.pass_context
def capture(ctx, source, output, points):
    """Capture waveform samples and save/print as CSV (index,voltage,time)."""
    raw = ops_wave.fetch(osc(ctx), source)
    # The firmware ignores NP and returns the full memory; trim client-side.
    rows = list(ops_wave.csv_lines(raw, limit=max(points, 0)))
    text = "\n".join(rows) + "\n"
    n = len(rows) - 1
    if output:
        with open(output, "w") as f:
            f.write(text)
        click.echo(
            f"Saved {n} samples to {output} "
            f"(vdiv={raw.vdiv:.4g}, interval={raw.horz_interval:.3g}s)"
        )
    else:
        click.echo(text)


@waveform_group.command("info")
@click.option("--source", "-s", type=click.Choice(ops_wave.SOURCES), default="C1", show_default=True)
@click.pass_context
def info(ctx, source):
    """Show waveform descriptor info (scaling) for a channel."""
    raw = ops_wave.fetch(osc(ctx), source)
    click.echo(f"Source        : {source}")
    click.echo(f"Points        : {raw.wave_count}")
    click.echo(f"Vertical div  : {raw.vdiv:.6g} V/div")
    click.echo(f"Vertical off. : {raw.offset:.6g}")
    click.echo(f"Horiz interval: {raw.horz_interval:.6g} s")
    click.echo(f"Horiz offset  : {raw.horz_offset:.6g} s")
    click.echo(f"First valid   : {raw.first_valid}")
    click.echo(f"Last valid    : {raw.last_valid}")
```

- [ ] **Step 5: Suite completa**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add osc_cli/ops/waveform.py osc_cli/commands/waveform.py tests/test_cli_waveform.py tests/test_ops_waveform.py
git commit -m "Add bounded waveform capture with histogram stats and min/max decimation"
```

---

### Task 9: Ops de pantalla y decodificación serie

**Files:**
- Create: `osc_cli/ops/screen.py`, `osc_cli/ops/decode.py`
- Modify: `osc_cli/commands/screen.py` (reemplazo completo), `osc_cli/commands/decode.py` (reemplazo completo)
- Test: `tests/test_cli_screen_decode.py`, `tests/test_ops_screen_decode.py`

**Interfaces:**
- Consumes: `bmp_to_png` (Task 3), `Oscilloscope.read_bmp` (Task 2), `waveform.fetch/to_volts/write_csv` (Task 8), `acquisition.stop` (Task 5), `osc_cli.decoders`.
- Produces: `screen.capture_bmp(o) -> bytes`, `screen.capture_png(o) -> bytes` (BMP inválido → `OscError`).
- Produces: `decode.configure_uart_trigger(o, rx="C1", tx=None, baud=115200, parity="NONE", stop_bits=1.0, polarity="HIGH") -> dict`, `configure_i2c_trigger(o, scl="C1", sda="C2") -> dict`, `configure_spi_trigger(o, clk="C1", miso="C2", mosi="C3", cs="C4") -> dict`, `load_csv(path) -> (list[float], dt)`, `capture_lines(o, sources, freeze, max_samples) -> (dict[src, list[float]], dt, stopped)`, `with_ascii(frames)`, `paginate(items, limit, offset) -> {items, total, count, offset, has_more, next_offset}`, `diagnose(samples, threshold) -> {min_v, max_v, threshold_v, hint}`.

- [ ] **Step 1: Tests de caracterización**

`tests/test_cli_screen_decode.py`:

```python
import json

import pytest

from tests.bmp_util import make_bmp
from tests.fakes import FakeOscilloscope, codes_from_volts, make_wavedesc_block, run_cli
from tests.test_decoders import DT, uart_wave

MSG = b"Hola"


def uart_fake():
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(codes_from_volts(uart_wave(MSG, 9600), 1.0), vdiv=1.0, interval=DT)
    return fake


def test_screen_capture(monkeypatch, tmp_path):
    fake = FakeOscilloscope()
    bmp = make_bmp([[(1, 2, 3)] * 4] * 2)
    fake.raw["SCDP"] = bmp
    out = tmp_path / "s.bmp"
    result = run_cli(monkeypatch, fake, "screen", "capture", "-o", str(out))
    assert result.output == f"Screen saved to {out} ({len(bmp)} bytes, BMP).\n"
    assert out.read_bytes() == bmp


CONFIG_CASES = [
    (["decode", "uart", "--rx", "C2", "--baud", "9600"],
     ["TRSE SERIAL", "TRIG_UART:RX C2", "TRIG_UART:BAUD 9600", "TRIG_UART:PARITY NONE",
      "TRIG_UART:STOP 1.0", "TRIG_UART:POLARITY HIGH"],
     "UART decode: RX=C2 baud=9600 parity=NONE stop=1.0\n"),
    (["decode", "i2c"], ["TRSE SERIAL", "TRIG_IIC:SCL C1", "TRIG_IIC:SDA C2"],
     "I2C decode: SCL=C1 SDA=C2\n"),
    (["decode", "spi"], ["TRSE SERIAL", "TRIG_SPI:CLK C1", "TRIG_SPI:MISO C2", "TRIG_SPI:MOSI C3",
                         "TRIG_SPI:CS C4"],
     "SPI decode: CLK=C1 MISO=C2 MOSI=C3 CS=C4\n"),
]


@pytest.mark.parametrize("args,writes,output", CONFIG_CASES)
def test_decode_trigger_config(monkeypatch, args, writes, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.output == output
    assert fake.writes == writes


def test_uart_bytes_live_json(monkeypatch):
    fake = uart_fake()
    result = run_cli(monkeypatch, fake, "decode", "uart-bytes", "--baud", "9600", "--json")
    frames = json.loads(result.output)
    assert bytes(f["value"] for f in frames) == MSG
    assert fake.writes[0] == "STOP"


def test_uart_bytes_from_file_text(monkeypatch, tmp_path):
    path = tmp_path / "rx.csv"
    wave = uart_wave(MSG, 9600)
    path.write_text("index,voltage,time\n" + "".join(f"{i},{v},{i * DT}\n" for i, v in enumerate(wave)))
    result = run_cli(monkeypatch, FakeOscilloscope(), "decode", "uart-bytes", "--file", str(path), "--baud", "9600")
    assert result.output.endswith("\n4 bytes: Hola\n")
    assert result.output.splitlines()[0].split()[2:] == ["0x48", "H"]


def test_csv_with_one_sample_is_rejected(monkeypatch, tmp_path):
    path = tmp_path / "short.csv"
    path.write_text("index,voltage,time\n0,0.0,0.0\n")
    from click.testing import CliRunner

    from osc_cli import cli as cli_module
    result = CliRunner().invoke(cli_module.cli, ["decode", "uart-bytes", "--file", str(path)])
    assert result.exit_code != 0
    assert "not enough samples" in result.output


def test_spi_bytes_needs_a_data_line(monkeypatch):
    from click.testing import CliRunner

    from osc_cli import cli as cli_module
    fake = uart_fake()
    monkeypatch.setattr(cli_module, "get_device", lambda *a, **k: fake)
    result = CliRunner().invoke(cli_module.cli, ["decode", "spi-bytes"])
    assert "Give at least one of --mosi / --miso." in result.output


def test_i2c_bytes_live(monkeypatch):
    from tests.test_decoders import i2c_wave
    scl, sda = i2c_wave([(0x50, False, [0xAB])])
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(codes_from_volts(scl, 1.0), vdiv=1.0, interval=DT)
    fake.blocks["C2"] = make_wavedesc_block(codes_from_volts(sda, 1.0), vdiv=1.0, interval=DT)
    result = run_cli(monkeypatch, fake, "decode", "i2c-bytes", "--json")
    txns = json.loads(result.output)
    assert txns[0]["address"] == 0x50 and txns[0]["data"] == [0xAB]
```

Run: `.venv/bin/python -m pytest tests/test_cli_screen_decode.py -q`
Expected: PASS (9) con el código actual (usa `query_raw` y `get_waveform` del fake).

- [ ] **Step 2: Tests de las ops que fallan**

`tests/test_ops_screen_decode.py`:

```python
import pytest

from osc_cli.device import OscError, parse_wavedesc
from osc_cli.ops import decode, screen, waveform
from tests.bmp_util import make_bmp, read_png
from tests.fakes import FakeOscilloscope, codes_from_volts, make_wavedesc_block
from tests.test_decoders import DT, uart_wave


def test_capture_png():
    fake = FakeOscilloscope()
    fake.raw["SCDP"] = make_bmp([[(255, 0, 0), (0, 0, 255)]])
    assert read_png(screen.capture_png(fake)) == (2, 1, [[(255, 0, 0), (0, 0, 255)]])


def test_capture_png_wraps_bad_bmp():
    fake = FakeOscilloscope()
    fake.raw["SCDP"] = make_bmp([[(0, 0, 0)]])[:-2]
    with pytest.raises(OscError, match="PNG"):
        screen.capture_png(fake)


def test_configure_triggers():
    fake = FakeOscilloscope()
    decode.configure_uart_trigger(fake, rx="C2", tx="C3", baud=9600)
    decode.configure_i2c_trigger(fake)
    decode.configure_spi_trigger(fake, cs="C1")
    assert fake.writes == [
        "TRSE SERIAL", "TRIG_UART:RX C2", "TRIG_UART:BAUD 9600", "TRIG_UART:PARITY NONE",
        "TRIG_UART:STOP 1.0", "TRIG_UART:POLARITY HIGH", "TRIG_UART:TX C3",
        "TRSE SERIAL", "TRIG_IIC:SCL C1", "TRIG_IIC:SDA C2",
        "TRSE SERIAL", "TRIG_SPI:CLK C1", "TRIG_SPI:MISO C2", "TRIG_SPI:MOSI C3", "TRIG_SPI:CS C1",
    ]


def test_capture_csv_round_trips_through_load_csv(tmp_path):
    codes = codes_from_volts(uart_wave(b"OK", 9600), 1.0)
    raw = parse_wavedesc(make_wavedesc_block(codes, vdiv=1.0, interval=DT))
    path = tmp_path / "rx.csv"
    waveform.write_csv(raw, path)
    volts, dt = decode.load_csv(path)
    assert dt == pytest.approx(DT, rel=1e-6)
    assert volts == pytest.approx(list(waveform.to_volts(raw)), abs=1e-6)


def test_capture_lines_freezes_once():
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(bytes(10), interval=2e-6)
    fake.blocks["C2"] = make_wavedesc_block(bytes(10), interval=2e-6)
    lines, dt, stopped = decode.capture_lines(fake, ["C1", "C2"], True, None)
    assert fake.writes == ["STOP"]
    assert set(lines) == {"C1", "C2"} and stopped is True
    assert dt == pytest.approx(2e-6)


def test_with_ascii():
    frames = decode.with_ascii([{"value": 0x41}, {"value": 0x0A}])
    assert [f["ascii"] for f in frames] == ["A", "."]


def test_paginate():
    page = decode.paginate(list(range(5)), limit=2, offset=2)
    assert page == {"items": [2, 3], "total": 5, "count": 2, "offset": 2,
                    "has_more": True, "next_offset": 4}


def test_paginate_offset_past_end():
    page = decode.paginate(list(range(5)), limit=2, offset=10)
    assert page["items"] == [] and page["has_more"] is False and page["next_offset"] is None


def test_diagnose():
    flat = decode.diagnose([0.0, 0.05, 0.1], None)
    assert flat["threshold_v"] == pytest.approx(0.05) and "barely moves" in flat["hint"]
    busy = decode.diagnose([0.0, 3.3], 1.2)
    assert busy["threshold_v"] == 1.2 and "baud" in busy["hint"]
```

Run: `.venv/bin/python -m pytest tests/test_ops_screen_decode.py -q`
Expected: FAIL con `ImportError`.

- [ ] **Step 3: Implementar las ops**

`osc_cli/ops/screen.py`:

```python
"""Screen capture (SCDP returns an 800x480 BMP)."""

from __future__ import annotations

from ..device import OscError
from ..imaging import bmp_to_png


def capture_bmp(o) -> bytes:
    return o.read_bmp("SCDP")


def capture_png(o) -> bytes:
    try:
        return bmp_to_png(capture_bmp(o))
    except ValueError as e:
        raise OscError(f"Screen dump could not be converted to PNG: {e}") from e
```

`osc_cli/ops/decode.py`:

```python
"""Serial bus support: scope trigger setup and host-side byte extraction.

The scope's built-in decoder cannot be read back over USBTMC, so bytes are
recovered by capturing the lines and running osc_cli.decoders on the samples.
"""

from __future__ import annotations

from . import acquisition, waveform

SOURCES = ("C1", "C2", "C3", "C4")
PARITIES = ("NONE", "EVEN", "ODD")
POLARITIES = ("HIGH", "LOW")


# ---- trigger configuration on the scope ------------------------------------
def configure_uart_trigger(o, rx="C1", tx=None, baud=115200, parity="NONE",
                           stop_bits=1.0, polarity="HIGH") -> dict:
    o.write("TRSE SERIAL")
    o.write(f"TRIG_UART:RX {rx}")
    o.write(f"TRIG_UART:BAUD {baud}")
    o.write(f"TRIG_UART:PARITY {parity}")
    o.write(f"TRIG_UART:STOP {stop_bits}")
    o.write(f"TRIG_UART:POLARITY {polarity}")
    if tx:
        o.write(f"TRIG_UART:TX {tx}")
    return {"rx": rx, "tx": tx, "baud": baud, "parity": parity,
            "stop_bits": stop_bits, "polarity": polarity}


def configure_i2c_trigger(o, scl="C1", sda="C2") -> dict:
    o.write("TRSE SERIAL")
    o.write(f"TRIG_IIC:SCL {scl}")
    o.write(f"TRIG_IIC:SDA {sda}")
    return {"scl": scl, "sda": sda}


def configure_spi_trigger(o, clk="C1", miso="C2", mosi="C3", cs="C4") -> dict:
    o.write("TRSE SERIAL")
    o.write(f"TRIG_SPI:CLK {clk}")
    o.write(f"TRIG_SPI:MISO {miso}")
    o.write(f"TRIG_SPI:MOSI {mosi}")
    o.write(f"TRIG_SPI:CS {cs}")
    return {"clk": clk, "miso": miso, "mosi": mosi, "cs": cs}


# ---- samples ------------------------------------------------------------------
def load_csv(path) -> tuple[list[float], float]:
    """(volts, dt) from a CSV written by `osc waveform capture` (index,voltage,time)."""
    volts, times = [], []
    with open(path) as f:
        next(f, None)  # header: index,voltage,time
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 3:
                volts.append(float(parts[1]))
                times.append(float(parts[2]))
    if len(volts) < 2:
        raise ValueError(f"{path}: not enough samples.")
    return volts, (times[-1] - times[0]) / (len(times) - 1)


def capture_lines(o, sources, freeze: bool, max_samples: int | None):
    """Capture each source as volts. Returns (lines, dt, stopped).

    freeze=True stops the acquisition first so every line comes from the same
    capture; the scope is left stopped.
    """
    if freeze:
        acquisition.stop(o)
    lines, dt = {}, None
    for source in dict.fromkeys(sources):
        raw = waveform.fetch(o, source, max_samples)
        lines[source] = list(waveform.to_volts(raw))
        dt = dt or raw.horz_interval
    return lines, dt, freeze


# ---- results -----------------------------------------------------------------
def with_ascii(frames: list[dict]) -> list[dict]:
    return [{**f, "ascii": chr(f["value"]) if 32 <= f["value"] < 127 else "."} for f in frames]


def paginate(items: list, limit: int, offset: int) -> dict:
    page = items[offset : offset + limit]
    end = offset + len(page)
    has_more = end < len(items)
    return {
        "items": page,
        "total": len(items),
        "count": len(page),
        "offset": offset,
        "has_more": has_more,
        "next_offset": end if has_more else None,
    }


def diagnose(samples, threshold: float | None) -> dict:
    """Why a decode found nothing: the levels seen and what to try next."""
    lo, hi = min(samples), max(samples)
    if hi - lo < 0.2:
        hint = ("The line barely moves (swing below 0.2 V): check the channel, the probe "
                "and that the bus is active during the capture window.")
    else:
        hint = ("The line toggles but nothing decoded: check the baud rate or SPI mode, "
                "the threshold, and that the capture window (time/div) contains traffic.")
    return {
        "min_v": lo,
        "max_v": hi,
        "threshold_v": threshold if threshold is not None else (lo + hi) / 2.0,
        "hint": hint,
    }
```

- [ ] **Step 4: Refactorizar los comandos**

`osc_cli/commands/screen.py`:

```python
"""Screen capture (SCDP) command - returns raw BMP."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import screen as ops_screen


@click.group(name="screen")
def screen_group():
    """Capture the oscilloscope screen as an image."""


@screen_group.command("capture")
@click.option("--output", "-o", required=True, help="Output image file (e.g. shot.bmp).")
@click.pass_context
def capture(ctx, output):
    """Capture the screen (SCDP) and save as BMP."""
    data = ops_screen.capture_bmp(osc(ctx))
    with open(output, "wb") as f:
        f.write(data)
    click.echo(f"Screen saved to {output} ({len(data)} bytes, BMP).")
```

`osc_cli/commands/decode.py`:

```python
"""Serial decode trigger commands (LeCroy dialect).

The SDS1104X-E exposes serial decode through trigger commands:
TRIG_UART:..., TRIG_IIC:... (I2C), TRIG_SPI:.... The command strings and the
capture/CSV helpers live in osc_cli.ops.decode.
"""

from __future__ import annotations

import json

import click

from .. import decoders
from ..cli import osc
from ..ops import decode as ops_decode

CH = ["C1", "C2", "C3", "C4"]


@click.group(name="decode")
def decode_group():
    """Serial bus decode (UART, I2C, SPI)."""


@decode_group.command("uart")
@click.option("--rx", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--tx", type=click.Choice(CH), default=None, help="TX source (optional).")
@click.option("--baud", type=int, default=115200, show_default=True)
@click.option("--parity", type=click.Choice(["NONE", "EVEN", "ODD"]), default="NONE", show_default=True)
@click.option("--stop", type=float, default=1.0, show_default=True)
@click.option("--polarity", type=click.Choice(["HIGH", "LOW"]), default="HIGH", show_default=True)
@click.pass_context
def uart(ctx, rx, tx, baud, parity, stop, polarity):
    """Configure UART decode trigger."""
    ops_decode.configure_uart_trigger(osc(ctx), rx, tx, baud, parity, stop, polarity)
    click.echo(f"UART decode: RX={rx} baud={baud} parity={parity} stop={stop}")


@decode_group.command("i2c")
@click.option("--scl", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--sda", type=click.Choice(CH), default="C2", show_default=True)
@click.pass_context
def i2c(ctx, scl, sda):
    """Configure I2C decode trigger."""
    ops_decode.configure_i2c_trigger(osc(ctx), scl, sda)
    click.echo(f"I2C decode: SCL={scl} SDA={sda}")


@decode_group.command("spi")
@click.option("--clk", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--miso", type=click.Choice(CH), default="C2", show_default=True)
@click.option("--mosi", type=click.Choice(CH), default="C3", show_default=True)
@click.option("--cs", type=click.Choice(CH), default="C4", show_default=True)
@click.pass_context
def spi(ctx, clk, miso, mosi, cs):
    """Configure SPI decode trigger."""
    ops_decode.configure_spi_trigger(osc(ctx), clk, miso, mosi, cs)
    click.echo(f"SPI decode: CLK={clk} MISO={miso} MOSI={mosi} CS={cs}")


@decode_group.command("status")
@click.pass_context
def status(ctx):
    """Show current serial decode configuration."""
    o = osc(ctx)
    click.echo(f"Trigger setup: {o.query('TRSE?')}")
    for c in ["BAUD", "PARITY", "STOP", "POLARITY", "RX", "TX", "BIT"]:
        try:
            click.echo(f"UART {c:8s}: {o.query(f'TRIG_UART:{c}?')}")
        except Exception:  # noqa: BLE001
            pass


# ---- byte extraction (software decode of captured waveforms) ---------------
#
# The scope's built-in decoder cannot be read back over USBTMC, so these
# commands capture the channels and decode the samples on the host. Use
# --file to decode a CSV saved by `osc waveform capture` without a scope.


def _load(ctx, source, path, stop):
    """Return (samples, dt) from a CSV file or a live capture of `source`."""
    if path:
        try:
            return ops_decode.load_csv(path)
        except ValueError as e:
            raise click.ClickException(str(e))
    # stop=True freezes the acquisition so every channel is the same capture.
    lines, dt, _ = ops_decode.capture_lines(osc(ctx), [source], stop, None)
    return lines[source], dt


def _fmt_options(f):
    for opt in reversed([
        click.option("--json", "as_json", is_flag=True, help="Output JSON."),
        click.option("--no-stop", is_flag=True, help="Do not STOP the acquisition before reading."),
        click.option("--threshold", type=float, default=None, help="Logic threshold in volts (default: midpoint)."),
    ]):
        f = opt(f)
    return f


@decode_group.command("uart-bytes")
@click.option("--rx", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--file", "path", type=click.Path(exists=True), help="Decode a CSV from `waveform capture` instead.")
@click.option("--baud", type=int, default=115200, show_default=True)
@click.option("--bits", type=click.IntRange(5, 9), default=8, show_default=True)
@click.option("--parity", type=click.Choice(["NONE", "EVEN", "ODD"]), default="NONE", show_default=True)
@click.option("--stop", "stop_bits", type=float, default=1.0, show_default=True)
@click.option("--polarity", type=click.Choice(["HIGH", "LOW"]), default="HIGH", show_default=True, help="Idle level.")
@click.option("--msb-first", is_flag=True, help="MSB first (default: LSB first).")
@_fmt_options
@click.pass_context
def uart_bytes(ctx, rx, path, baud, bits, parity, stop_bits, polarity, msb_first, as_json, no_stop, threshold):
    """Capture a channel and extract the UART bytes."""
    samples, dt = _load(ctx, rx, path, not no_stop)
    try:
        frames = decoders.uart_decode(
            samples, dt, baud, bits, parity, stop_bits, polarity, not msb_first, threshold
        )
    except ValueError as e:
        raise click.ClickException(str(e))
    if as_json:
        click.echo(json.dumps(frames))
        return
    for fr in frames:
        err = f"  ! {','.join(fr['errors'])}" if fr["errors"] else ""
        ch = chr(fr["value"]) if 32 <= fr["value"] < 127 else "."
        click.echo(f"{fr['time']*1e3:12.4f} ms  0x{fr['value']:02X}  {ch}{err}")
    text = "".join(chr(f["value"]) if 32 <= f["value"] < 127 else "." for f in frames)
    click.echo(f"\n{len(frames)} bytes: {text}")


@decode_group.command("i2c-bytes")
@click.option("--scl", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--sda", type=click.Choice(CH), default="C2", show_default=True)
@click.option("--scl-file", type=click.Path(exists=True), help="CSV for SCL (offline).")
@click.option("--sda-file", type=click.Path(exists=True), help="CSV for SDA (offline).")
@_fmt_options
@click.pass_context
def i2c_bytes(ctx, scl, sda, scl_file, sda_file, as_json, no_stop, threshold):
    """Capture SCL/SDA and extract I2C transactions."""
    c, dt = _load(ctx, scl, scl_file, not no_stop)
    d, _ = _load(ctx, sda, sda_file, False)
    txns = decoders.i2c_decode(c, d, dt, threshold, threshold)
    if as_json:
        click.echo(json.dumps(txns))
        return
    for t in txns:
        rw = "R" if t["read"] else "W"
        addr = "?" if t["address"] is None else f"0x{t['address']:02X}"
        data = " ".join(f"{b:02X}" for b in t["data"])
        nack = " NACK" if t["acks"] and not all(t["acks"]) else ""
        rs = "Sr" if t["repeated_start"] else "S"
        click.echo(f"{t['time']*1e3:12.4f} ms  {rs} {addr} {rw}  {data}{nack}")
    click.echo(f"\n{len(txns)} transactions")


@decode_group.command("spi-bytes")
@click.option("--clk", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--mosi", type=click.Choice(CH), default=None)
@click.option("--miso", type=click.Choice(CH), default=None)
@click.option("--cs", type=click.Choice(CH), default=None, help="Chip select (active low).")
@click.option("--clk-file", type=click.Path(exists=True), help="CSV for CLK (offline).")
@click.option("--mosi-file", type=click.Path(exists=True))
@click.option("--miso-file", type=click.Path(exists=True))
@click.option("--cs-file", type=click.Path(exists=True))
@click.option("--bits", type=click.IntRange(4, 32), default=8, show_default=True)
@click.option("--cpol", type=click.IntRange(0, 1), default=0, show_default=True)
@click.option("--cpha", type=click.IntRange(0, 1), default=0, show_default=True)
@click.option("--lsb-first", is_flag=True, help="LSB first (default: MSB first).")
@_fmt_options
@click.pass_context
def spi_bytes(ctx, clk, mosi, miso, cs, clk_file, mosi_file, miso_file, cs_file,
              bits, cpol, cpha, lsb_first, as_json, no_stop, threshold):
    """Capture the SPI lines and extract MOSI/MISO words."""
    k, dt = _load(ctx, clk, clk_file, not no_stop)

    def side(ch, f):
        return _load(ctx, ch, f, False)[0] if (ch or f) else None

    m, s, c = side(mosi, mosi_file), side(miso, miso_file), side(cs, cs_file)
    if m is None and s is None:
        raise click.ClickException("Give at least one of --mosi / --miso.")
    frames = decoders.spi_decode(k, m, s, c, dt, bits, cpol, cpha, not lsb_first, threshold)
    if as_json:
        click.echo(json.dumps(frames))
        return
    w = (bits + 3) // 4
    for fr in frames:
        click.echo(f"{fr['time']*1e3:12.4f} ms")
        if m is not None:
            click.echo("  MOSI: " + " ".join(f"{b:0{w}X}" for b in fr["mosi"]))
        if s is not None:
            click.echo("  MISO: " + " ".join(f"{b:0{w}X}" for b in fr["miso"]))
    click.echo(f"\n{len(frames)} frames")
```

- [ ] **Step 5: Suite completa**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add osc_cli/ops/screen.py osc_cli/ops/decode.py osc_cli/commands/screen.py osc_cli/commands/decode.py tests/test_cli_screen_decode.py tests/test_ops_screen_decode.py
git commit -m "Extract screen and serial decode ops; read SCDP by BMP length"
```

---

### Task 10: `Session` — conexión persistente, lock y reintentos

**Files:**
- Modify: `pyproject.toml` (añadir `"siglent_mcp"` a `packages`)
- Create: `siglent_mcp/__init__.py`, `siglent_mcp/session.py`
- Test: `tests/test_session.py`

**Interfaces:**
- Consumes: `OscTransportError`, `get_device` (Task 2); `acquisition.CONTINUOUS_MODES` (Task 5).
- Produces: `siglent_mcp.session.ScopeBusy(Exception)`, `default_factory()`, `Session(factory=None, lock_timeout_s=None)` con `run(fn, *args, retry: bool, timeout_ms=None, restore_header=False, **kwargs)`, `remember_mode(mode)`, `close()`, atributo `last_continuous_mode: str | None`. `run` llama `fn(osc, *args, **kwargs)`; al conectar envía `CHDR SHORT`; tras agotar reintentos marca `exc.retried = retry`.

- [ ] **Step 1: Tests que fallan**

`tests/test_session.py`:

```python
import threading
import time

import pytest

from osc_cli.device import OscError, OscNotFoundError, OscTransportError
from siglent_mcp.session import ScopeBusy, Session
from tests.fakes import FakeOscilloscope


class Factory:
    """Hands out a new FakeOscilloscope per connection, optionally failing first."""

    def __init__(self, fail_first: Exception | None = None):
        self.created: list[FakeOscilloscope] = []
        self.fail_first = fail_first

    def __call__(self):
        if self.fail_first is not None:
            exc, self.fail_first = self.fail_first, None
            raise exc
        fake = FakeOscilloscope()
        self.created.append(fake)
        return fake


def flaky(failures: int, exc=OscTransportError("pipe")):
    calls = {"n": 0}

    def fn(o):
        calls["n"] += 1
        if calls["n"] <= failures:
            raise exc
        return "ok"

    return fn, calls


def test_connects_lazily_once_and_sets_short_headers():
    factory = Factory()
    session = Session(factory)
    assert factory.created == []
    session.run(lambda o: o.query("TDIV?"), retry=True)
    session.run(lambda o: o.query("TDIV?"), retry=True)
    assert len(factory.created) == 1
    assert factory.created[0].log[0] == ("w", "CHDR SHORT")


def test_transport_error_retries_on_new_connection():
    factory = Factory()
    fn, calls = flaky(1)
    assert Session(factory).run(fn, retry=True) == "ok"
    assert calls["n"] == 2
    assert len(factory.created) == 2
    assert factory.created[0].closed


def test_no_retry_when_not_idempotent():
    factory = Factory()
    fn, calls = flaky(1)
    with pytest.raises(OscTransportError) as info:
        Session(factory).run(fn, retry=False)
    assert calls["n"] == 1
    assert info.value.retried is False


def test_gives_up_after_one_retry():
    fn, calls = flaky(5)
    with pytest.raises(OscTransportError) as info:
        Session(Factory()).run(fn, retry=True)
    assert calls["n"] == 2
    assert info.value.retried is True


def test_protocol_errors_are_not_retried_and_keep_connection():
    factory = Factory()
    session = Session(factory)
    fn, calls = flaky(1, OscError("bad header"))
    with pytest.raises(OscError):
        session.run(fn, retry=True)
    session.run(lambda o: None, retry=True)
    assert calls["n"] == 1
    assert len(factory.created) == 1


def test_reconnects_on_next_call_after_failed_call():
    factory = Factory(fail_first=OscNotFoundError("No USBTMC device found."))
    session = Session(factory)
    with pytest.raises(OscNotFoundError):
        session.run(lambda o: None, retry=True)
    fn, _ = flaky(1)
    with pytest.raises(OscTransportError):
        session.run(fn, retry=False)  # cable pulled mid-call
    assert session.run(lambda o: "back", retry=True) == "back"
    assert len(factory.created) == 2


def test_restore_header_after_success_and_after_error():
    factory = Factory()
    session = Session(factory)
    session.run(lambda o: o.write("CHDR OFF"), retry=False, restore_header=True)
    assert factory.created[0].writes[-2:] == ["CHDR OFF", "CHDR SHORT"]

    def boom(o):
        o.write("CHDR LONG")
        raise OscError("rejected")

    with pytest.raises(OscError):
        session.run(boom, retry=False, restore_header=True)
    assert factory.created[0].writes[-1] == "CHDR SHORT"


def test_timeout_override_is_scoped_to_the_call():
    factory = Factory()
    session = Session(factory)
    seen = session.run(lambda o: o.timeout_ms, retry=False, timeout_ms=120000)
    assert seen == 120000
    assert factory.created[0].timeout_ms == 5000


def test_busy_when_lock_not_released_in_time():
    session = Session(Factory(), lock_timeout_s=0.05)
    started = threading.Event()

    def slow(o):
        started.set()
        time.sleep(0.3)

    t = threading.Thread(target=session.run, args=(slow,), kwargs={"retry": False})
    t.start()
    started.wait()
    with pytest.raises(ScopeBusy):
        session.run(lambda o: None, retry=True)
    t.join()


def test_concurrent_runs_are_serialized():
    session = Session(Factory())
    events = []

    def work(o, name):
        events.append(("enter", name))
        time.sleep(0.02)
        events.append(("exit", name))

    threads = [threading.Thread(target=session.run, args=(work, n), kwargs={"retry": False})
               for n in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for i in range(0, len(events), 2):
        assert events[i][0] == "enter" and events[i + 1] == ("exit", events[i][1])


def test_remember_mode_only_tracks_continuous_modes():
    session = Session(Factory())
    session.remember_mode("norm")
    session.remember_mode("SINGLE")
    session.remember_mode(None)
    assert session.last_continuous_mode == "NORM"


def test_close_disconnects():
    factory = Factory()
    session = Session(factory)
    session.run(lambda o: None, retry=True)
    session.close()
    assert factory.created[0].closed
```

Run: `.venv/bin/python -m pytest tests/test_session.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'siglent_mcp'`.

- [ ] **Step 2: Implementar**

En `pyproject.toml`: `packages = ["osc_cli", "osc_cli.commands", "osc_cli.ops", "siglent_mcp"]`, luego `.venv/bin/pip install -e ".[dev]"`.

`siglent_mcp/__init__.py`:

```python
"""MCP server for the Siglent SDS1104X-E oscilloscope (USBTMC)."""

__version__ = "1.0.0"
```

`siglent_mcp/session.py`:

```python
"""One persistent, lock-protected connection to the oscilloscope.

USBTMC handles one request at a time, so every tool call goes through
Session.run, which serializes access and reconnects after transport errors.
"""

from __future__ import annotations

import logging
import os
import threading

from osc_cli.device import OscTransportError, get_device
from osc_cli.ops.acquisition import CONTINUOUS_MODES

log = logging.getLogger(__name__)


class ScopeBusy(Exception):
    """Another call held the scope for longer than the lock timeout."""


def default_factory():
    resource = os.environ.get("OSC_RESOURCE") or None
    timeout_ms = int(os.environ.get("OSC_TIMEOUT_MS", "5000"))
    return get_device(resource, timeout_ms)


class Session:
    def __init__(self, factory=None, lock_timeout_s: float | None = None):
        self._factory = factory or default_factory
        if lock_timeout_s is None:
            lock_timeout_s = float(os.environ.get("OSC_LOCK_TIMEOUT_S", "120"))
        self._lock_timeout_s = lock_timeout_s
        self._lock = threading.Lock()
        self._osc = None
        self.last_continuous_mode: str | None = None

    def run(self, fn, *args, retry: bool, timeout_ms: int | None = None,
            restore_header: bool = False, **kwargs):
        """Call fn(osc, *args, **kwargs) holding the instrument lock.

        retry=True: after an OscTransportError, reconnect and call fn once
        more. Only for operations that are safe to repeat.
        restore_header=True: send CHDR SHORT afterwards (for *RST, setup
        recall and raw commands, which may change the header mode).
        """
        if not self._lock.acquire(timeout=self._lock_timeout_s):
            raise ScopeBusy(f"lock not acquired within {self._lock_timeout_s:g} s")
        try:
            attempts = 2 if retry else 1
            for attempt in range(1, attempts + 1):
                osc = None
                try:
                    osc = self._osc if self._osc is not None else self._connect()
                    result = self._call(osc, fn, args, kwargs, timeout_ms)
                except OscTransportError as exc:
                    log.warning("transport error (attempt %d/%d): %s", attempt, attempts, exc)
                    self._disconnect()
                    if attempt == attempts:
                        exc.retried = retry
                        raise
                    continue
                except Exception:
                    if restore_header and osc is not None:
                        self._restore_header(osc)
                    raise
                if restore_header:
                    self._restore_header(osc)
                return result
            raise AssertionError("unreachable")
        finally:
            self._lock.release()

    def remember_mode(self, mode: str | None) -> None:
        """Track the last continuous trigger mode so 'run' can return to it."""
        mode = (mode or "").upper()
        if mode in CONTINUOUS_MODES:
            self.last_continuous_mode = mode

    def close(self) -> None:
        with self._lock:
            self._disconnect()

    # ---- internals ------------------------------------------------------------
    def _connect(self):
        osc = self._factory()
        osc.write("CHDR SHORT")
        self._osc = osc
        return osc

    def _disconnect(self) -> None:
        if self._osc is not None:
            try:
                self._osc.close()
            except Exception:  # noqa: BLE001
                pass
            self._osc = None

    @staticmethod
    def _call(osc, fn, args, kwargs, timeout_ms):
        if timeout_ms:
            with osc.timeout(timeout_ms):
                return fn(osc, *args, **kwargs)
        return fn(osc, *args, **kwargs)

    def _restore_header(self, osc) -> None:
        try:
            osc.write("CHDR SHORT")
        except OscTransportError:
            self._disconnect()  # reconnecting sets CHDR SHORT again
```

- [ ] **Step 3: Verificar**

Run: `.venv/bin/python -m pytest tests/test_session.py -q`
Expected: PASS (12).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml siglent_mcp/__init__.py siglent_mcp/session.py tests/test_session.py
git commit -m "Add MCP session with serialized access and transport-only retries"
```

---

### Task 11: `Storage` y mapeo de errores a `ToolError`

**Files:**
- Create: `siglent_mcp/storage.py`, `siglent_mcp/errors.py`
- Test: `tests/test_storage_errors.py`

**Interfaces:**
- Consumes: `ScopeBusy` (Task 10); `OscError`, `OscNotFoundError`, `OscTransportError` (Task 2).
- Produces: `storage.default_root() -> Path`, `Storage(root=None, keep=None)` con `.root: Path`, `.keep: int`, `output_path(kind, suffix, requested=None) -> Path` (crea el directorio padre; `ValueError` si `requested` escapa de la raíz), `prune(kind)`, `Storage.input_file(path) -> Path` (`ValueError` si no es archivo).
- Produces: `errors.tool_errors` (decorador), `errors.to_tool_error(exc) -> ToolError`, constantes `NOT_FOUND`, `NOT_RESPONDING`, `MAYBE_RAN`, `BUSY`.

- [ ] **Step 1: Tests que fallan**

`tests/test_storage_errors.py`:

```python
import os

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from osc_cli.device import OscError, OscNotFoundError, OscTransportError
from siglent_mcp.errors import tool_errors
from siglent_mcp.session import ScopeBusy
from siglent_mcp.storage import Storage, default_root


def test_auto_named_output_goes_under_kind(tmp_path):
    storage = Storage(root=tmp_path)
    path = storage.output_path("waveforms", "_C1.csv")
    assert path.parent == tmp_path / "waveforms"
    assert path.name.endswith("_C1.csv")


def test_requested_output_must_stay_inside_root(tmp_path):
    storage = Storage(root=tmp_path / "data")
    assert storage.output_path("screens", ".png", "shots/a.png") == tmp_path / "data" / "shots" / "a.png"
    with pytest.raises(ValueError, match="inside"):
        storage.output_path("screens", ".png", "../evil.png")
    with pytest.raises(ValueError, match="inside"):
        storage.output_path("screens", ".png", str(tmp_path / "elsewhere.png"))


def test_prune_keeps_newest(tmp_path):
    storage = Storage(root=tmp_path, keep=2)
    folder = tmp_path / "decodes"
    folder.mkdir()
    for i in range(4):
        f = folder / f"{i}.json"
        f.write_text("{}")
        os.utime(f, (1000 + i, 1000 + i))
    storage.prune("decodes")
    assert sorted(p.name for p in folder.iterdir()) == ["2.json", "3.json"]
    storage.prune("missing")  # no error


def test_input_file(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("index,voltage,time\n")
    assert Storage.input_file(str(f)) == f
    with pytest.raises(ValueError, match="not found"):
        Storage.input_file(str(tmp_path / "nope.csv"))
    with pytest.raises(ValueError, match="not found"):
        Storage.input_file(str(tmp_path))


def test_root_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("OSC_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("OSC_KEEP_FILES", "7")
    storage = Storage()
    assert storage.root == tmp_path / "d" and storage.keep == 7
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert default_root() == tmp_path / "xdg" / "siglent-mcp"


def raising(exc):
    @tool_errors
    def tool():
        raise exc

    return tool


def retried(exc):
    exc.retried = True
    return exc


@pytest.mark.parametrize("exc,fragment", [
    (ScopeBusy("x"), "busy"),
    (OscNotFoundError("No USBTMC device found."), "udev rule"),
    (retried(OscTransportError("timeout")), "power-cycle"),
    (OscTransportError("pipe"), "may or may not have run"),
    (OscError("bad header"), "bad header"),
    (ValueError("samples per bit"), "samples per bit"),
    (FileNotFoundError("x.csv"), "x.csv"),
])
def test_tool_errors_maps_exceptions(exc, fragment):
    with pytest.raises(ToolError, match=fragment):
        raising(exc)()


def test_tool_errors_passes_results_and_tool_errors_through():
    @tool_errors
    def ok(x):
        """Doc."""
        return x * 2

    assert ok(2) == 4 and ok.__doc__ == "Doc."
    with pytest.raises(ToolError, match="as is"):
        raising(ToolError("as is"))()
```

Run: `.venv/bin/python -m pytest tests/test_storage_errors.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'siglent_mcp.errors'`.

- [ ] **Step 2: Implementar**

`siglent_mcp/storage.py`:

```python
"""Where captures, screenshots and decode results are written.

Every output path is confined to one data directory so a tool argument can
never write elsewhere on disk; auto-named files are pruned to the newest N.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def default_root() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "siglent-mcp"


class Storage:
    def __init__(self, root: str | Path | None = None, keep: int | None = None):
        root = root or os.environ.get("OSC_DATA_DIR") or default_root()
        self.root = Path(root).expanduser().resolve()
        self.keep = keep if keep is not None else int(os.environ.get("OSC_KEEP_FILES", "20"))

    def output_path(self, kind: str, suffix: str, requested: str | None = None) -> Path:
        """A path inside the data directory.

        requested: a file name or relative path chosen by the caller; it must
        stay inside the data directory. Without it the file is auto-named
        under <root>/<kind>/ with a timestamp.
        """
        if requested:
            path = (self.root / requested).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError(f"Output path must be inside the data directory {self.root}")
        else:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            path = self.root / kind / f"{stamp}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def prune(self, kind: str) -> None:
        """Keep only the newest `keep` auto-named files of one kind."""
        folder = self.root / kind
        if not folder.is_dir():
            return
        files = sorted((p for p in folder.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
        for old in files[: max(len(files) - self.keep, 0)]:
            old.unlink(missing_ok=True)

    @staticmethod
    def input_file(path: str) -> Path:
        """An existing regular file to read (CSV input for offline decoding)."""
        p = Path(path).expanduser()
        if not p.is_file():
            raise ValueError(f"CSV file not found: {p}")
        return p.resolve()
```

`siglent_mcp/errors.py`:

```python
"""Turn every failure into a ToolError the agent can act on (no tracebacks)."""

from __future__ import annotations

import functools

from mcp.server.mcpserver.exceptions import ToolError

from osc_cli.device import OscError, OscNotFoundError, OscTransportError

from .session import ScopeBusy

NOT_FOUND = (
    "Oscilloscope not found. Check that it is powered on and connected over USB, "
    "and that the udev rule is installed (sudo ./install-udev.sh). Details: {detail}"
)
NOT_RESPONDING = (
    "The scope is not responding ({detail}). If this persists, power-cycle it; "
    "re-plugging the USB cable is not enough."
)
MAYBE_RAN = (
    "Communication failed ({detail}). The operation may or may not have run; "
    "check siglent_get_status before repeating it."
)
BUSY = "The scope is busy with another operation; retry in a few seconds."


def to_tool_error(exc: Exception) -> ToolError:
    if isinstance(exc, ScopeBusy):
        return ToolError(BUSY)
    if isinstance(exc, OscNotFoundError):
        return ToolError(NOT_FOUND.format(detail=exc))
    if isinstance(exc, OscTransportError):
        template = NOT_RESPONDING if getattr(exc, "retried", False) else MAYBE_RAN
        return ToolError(template.format(detail=exc))
    return ToolError(str(exc))


def tool_errors(fn):
    """Decorator for tool functions; place it under @server.tool(...)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except (ScopeBusy, OscError, ValueError, OSError) as exc:
            raise to_tool_error(exc) from exc

    return wrapper
```

- [ ] **Step 3: Verificar**

Run: `.venv/bin/python -m pytest tests/test_storage_errors.py -q`
Expected: PASS (13).

- [ ] **Step 4: Commit**

```bash
git add siglent_mcp/storage.py siglent_mcp/errors.py tests/test_storage_errors.py
git commit -m "Add confined data directory and actionable tool errors"
```

---

### Task 12: Modelos, servidor y tools de lectura (10)

**Files:**
- Modify: `pyproject.toml` (añadir `"siglent_mcp.tools"` a `packages`)
- Create: `siglent_mcp/models.py`, `siglent_mcp/tools/__init__.py`, `siglent_mcp/tools/common.py`, `siglent_mcp/tools/status.py`, `siglent_mcp/server.py`
- Test: `tests/mcp_server/__init__.py` (vacío), `tests/mcp_server/conftest.py`, `tests/mcp_server/test_status_tools.py`

**Interfaces:**
- Consumes: todas las ops (Tasks 4-8), `Session` (Task 10), `Storage`, `tool_errors` (Task 11).
- Produces: `models.*` (TypedDicts: `Identity, ChannelState, ChannelList, TimebaseState, TriggerState, Status, Measurement, MeasureResult, CounterState, BurstState, SweepState, AwgState, ErrorState, WaitResult, AcquisitionResult, SerialTriggerResult, MathState, DisplayState, SetupResult, WaveformChannel, WaveformResult, Diagnostics, UartFrame, I2cTransaction, SpiFrame, DecodePage, UartPage, I2cPage, SpiPage, ResetResult, SelfTestResult, RawResult`).
- Produces: `tools.common.Deps(session, storage, max_samples)`, constantes de annotations `READ, WRITE, WRITE_ONCE, DANGER, DANGER_ONCE`, tipos `Source`, `ChannelNumber`, `STOPPED_NOTE`, `report_progress(ctx, done, total, message)`.
- Produces: `server.SERVER_NAME`, `INSTRUCTIONS`, `TOOL_MODULES`, `create_server(session=None, storage=None, max_samples=None) -> MCPServer`, objeto de módulo `server`, `main()`. Cada módulo de tools expone `register(server, deps)`; las tasks 13-15 añaden su módulo a `TOOL_MODULES` y al import.
- Produces (tests): fixtures `fake`, `storage`, `server`, `client` y helper `call(client, name, **arguments)`.

- [ ] **Step 1: Fixtures y tests que fallan**

`tests/mcp_server/conftest.py`:

```python
import pytest

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from siglent_mcp.server import create_server  # noqa: E402
from siglent_mcp.session import Session  # noqa: E402
from siglent_mcp.storage import Storage  # noqa: E402
from tests.fakes import FakeOscilloscope  # noqa: E402


@pytest.fixture
def fake():
    return FakeOscilloscope()


@pytest.fixture
def storage(tmp_path):
    return Storage(root=tmp_path / "data", keep=3)


@pytest.fixture
def server(fake, storage):
    return create_server(session=Session(lambda: fake), storage=storage, max_samples=2_000_000)


@pytest.fixture
async def client(server):
    async with Client(server) as c:
        yield c


async def call(client, name, **arguments):
    """Call a tool and fail the test with the tool's message if it errored."""
    result = await client.call_tool(name, arguments)
    assert not result.is_error, result.content[0].text
    return result
```

`tests/mcp_server/test_status_tools.py`:

```python
import pytest
from mcp import Client

from osc_cli.device import OscNotFoundError
from siglent_mcp.server import create_server
from siglent_mcp.session import Session
from tests.mcp_server.conftest import call

pytestmark = pytest.mark.anyio


async def test_identify(client, fake):
    result = await call(client, "siglent_identify")
    assert result.structured_content["model"] == "SDS1104X-E"
    assert fake.log[0] == ("w", "CHDR SHORT")


async def test_status_lists_enabled_channels(client):
    s = (await call(client, "siglent_get_status")).structured_content
    assert s["acquisition_state"] == "Trig'd"
    assert [c["channel"] for c in s["channels"]] == [1, 2]
    assert s["trigger"]["mode"] == "AUTO"
    assert s["timebase"]["memory"] == "14M"


async def test_get_channel_one_or_all(client):
    all_four = (await call(client, "siglent_get_channel")).structured_content["channels"]
    assert [c["channel"] for c in all_four] == [1, 2, 3, 4]
    one = (await call(client, "siglent_get_channel", channel=3)).structured_content["channels"]
    assert one[0]["enabled"] is False


async def test_get_channel_rejects_out_of_range(client):
    result = await client.call_tool("siglent_get_channel", {"channel": 5})
    assert result.is_error


async def test_timebase_trigger_counter_awg_error(client):
    assert (await call(client, "siglent_get_timebase")).structured_content["tdiv"] == 0.001
    assert (await call(client, "siglent_get_trigger")).structured_content["level"] == 1.5
    assert (await call(client, "siglent_read_counter")).structured_content["frequency_hz"] == 1000.0
    assert (await call(client, "siglent_get_awg")).structured_content["wave"] == "SINE"
    assert (await call(client, "siglent_get_error")).structured_content == {"code": 0, "message": "No error"}


async def test_measure_invalid_value_has_note(client, fake):
    fake.responses["C1:PAVA? FREQ"] = "C1:PAVA FREQ,****"
    m = (await call(client, "siglent_measure", items=["FREQ", "PKPK"])).structured_content
    assert m["measurements"]["FREQ"]["value"] is None
    assert "note" in m["measurements"]["FREQ"]
    assert m["measurements"]["PKPK"] == {"value": 1.0, "unit": "V"}


async def test_wait_for_acquisition(client, fake):
    fake.responses["SAST?"] = ["SAST Ready", "SAST Stop"]
    w = (await call(client, "siglent_wait_for_acquisition", timeout_s=2)).structured_content
    assert w["triggered"] is True and w["state"] == "Stop"


async def test_missing_scope_gives_actionable_error(storage):
    def factory():
        raise OscNotFoundError("No USBTMC device found.")

    server = create_server(session=Session(factory), storage=storage, max_samples=1000)
    async with Client(server) as c:
        result = await c.call_tool("siglent_identify", {})
    assert result.is_error
    assert "udev rule" in result.content[0].text
```

Run: `.venv/bin/python -m pytest tests/mcp_server -q`
Expected: FAIL (error de colección) con `ModuleNotFoundError: No module named 'siglent_mcp.server'`.

- [ ] **Step 2: Modelos y piezas comunes**

En `pyproject.toml`: añadir `"siglent_mcp.tools"` a `packages` y reinstalar con `.venv/bin/pip install -e ".[dev]"`.

`siglent_mcp/models.py`:

```python
"""Return types of the tools. The SDK turns them into outputSchema.

typing_extensions.TypedDict is required: pydantic rejects typing.TypedDict on
Python < 3.12.
"""

from __future__ import annotations

from typing_extensions import NotRequired, TypedDict


class Identity(TypedDict):
    manufacturer: str
    model: str
    serial: str
    firmware: str
    raw: str


class ChannelState(TypedDict):
    channel: int
    enabled: bool
    probe: float | None
    coupling: str
    bw_limit: str
    unit: str
    invert: bool
    vdiv: float | None
    offset: float | None
    skew: float | None


class ChannelList(TypedDict):
    channels: list[ChannelState]


class TimebaseState(TypedDict):
    tdiv: float | None
    delay: float | None
    sample_rate: float | None
    memory: str
    averages: int | None


class TriggerState(TypedDict):
    mode: str
    type: str
    source: str | None
    level: float | None
    coupling: str | None


class Status(TypedDict):
    acquisition_state: str
    trigger: TriggerState
    timebase: TimebaseState
    channels: list[ChannelState]


class Measurement(TypedDict):
    value: float | None
    unit: str
    note: NotRequired[str]


class MeasureResult(TypedDict):
    source: str
    measurements: dict[str, Measurement]


class CounterState(TypedDict):
    enabled: bool | None
    frequency_hz: float | None
    raw: str


class BurstState(TypedDict):
    enabled: bool
    cycles: int | None
    period_s: float | None


class SweepState(TypedDict):
    enabled: bool
    start_hz: float | None
    stop_hz: float | None
    time_s: float | None
    direction: str | None


class AwgState(TypedDict):
    enabled: bool
    load: str | None
    wave: str | None
    freq_hz: float | None
    amp_vpp: float | None
    offset_v: float | None
    phase_deg: float | None
    duty_pct: float | None
    arb: str | None
    modulation: bool | None
    sync: bool | None
    burst: BurstState | None
    sweep: SweepState | None


class ErrorState(TypedDict):
    code: int | None
    message: str


class WaitResult(TypedDict):
    triggered: bool
    state: str
    waited_s: float


class AcquisitionResult(TypedDict):
    action: str
    trigger_mode: str | None
    state: str
    note: NotRequired[str]


class SerialTriggerResult(TypedDict):
    protocol: str
    settings: dict[str, str | int | float | None]


class MathState(TypedDict):
    function: str
    offset: float | None
    scale: float | None


class DisplayState(TypedDict):
    grid: str
    intensity: int | None
    menu: bool
    cursor_mode: str


class SetupResult(TypedDict):
    action: str
    path: str


class WaveformChannel(TypedDict):
    n: int
    sample_rate: float | None
    duration: float
    min: float
    max: float
    vpp: float
    mean: float
    rms: float
    vdiv: float
    offset: float
    horz_interval: float
    horz_offset: float
    points: list[list[float]]
    csv_path: NotRequired[str]


class WaveformResult(TypedDict):
    sources: dict[str, WaveformChannel]
    acquisition_stopped: bool
    note: NotRequired[str]


class Diagnostics(TypedDict):
    min_v: float
    max_v: float
    threshold_v: float
    hint: str


class UartFrame(TypedDict):
    time: float
    value: int
    ascii: str
    errors: list[str]


class I2cTransaction(TypedDict):
    time: float
    address: int | None
    read: bool
    data: list[int]
    acks: list[bool]
    repeated_start: bool


class SpiFrame(TypedDict):
    time: float
    mosi: list[int]
    miso: list[int]


class DecodePage(TypedDict):
    total: int
    count: int
    offset: int
    has_more: bool
    next_offset: int | None
    json_path: str
    acquisition_stopped: bool
    diagnostics: NotRequired[Diagnostics]
    note: NotRequired[str]


class UartPage(DecodePage):
    frames: list[UartFrame]
    text: str


class I2cPage(DecodePage):
    transactions: list[I2cTransaction]


class SpiPage(DecodePage):
    frames: list[SpiFrame]


class ResetResult(TypedDict):
    status: str


class SelfTestResult(TypedDict):
    passed: bool | None
    result: str
    raw: str


class RawResult(TypedDict):
    command: str
    response: str | None
```

`siglent_mcp/tools/__init__.py`:

```python
"""Tool modules; each exposes register(server, deps)."""
```

`siglent_mcp/tools/common.py`:

```python
"""Shared pieces for the tool modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

import anyio
from mcp.server.mcpserver import Context
from mcp_types import ToolAnnotations
from pydantic import Field

from ..session import Session
from ..storage import Storage


@dataclass
class Deps:
    session: Session
    storage: Storage
    max_samples: int


def _hints(*, read_only: bool, idempotent: bool, destructive: bool = False) -> ToolAnnotations:
    return ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
        open_world_hint=False,
    )


READ = _hints(read_only=True, idempotent=True)
WRITE = _hints(read_only=False, idempotent=True)
WRITE_ONCE = _hints(read_only=False, idempotent=False)
DANGER = _hints(read_only=False, idempotent=True, destructive=True)
DANGER_ONCE = _hints(read_only=False, idempotent=False, destructive=True)

Source = Literal["C1", "C2", "C3", "C4"]
ChannelNumber = Annotated[int, Field(ge=1, le=4, description="Channel number, 1-4.")]

STOPPED_NOTE = (
    "Acquisition was stopped so every channel comes from the same capture. "
    "Resume it with siglent_control_acquisition(action='run')."
)


def report_progress(ctx: Context, done: float, total: float, message: str) -> None:
    """Send a progress notification from a sync tool (runs in a worker thread)."""
    anyio.from_thread.run(ctx.report_progress, done, total, message)
```

- [ ] **Step 3: Tools de lectura**

`siglent_mcp/tools/status.py`:

```python
"""Read-only tools: identity, status, settings, measurements, waiting."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from osc_cli.ops import acquisition, awg, measure, misc, system, timebase, trigger
from osc_cli.ops import channel as ops_channel

from ..errors import tool_errors
from ..models import (
    AwgState, ChannelList, CounterState, ErrorState, Identity, MeasureResult,
    Status, TimebaseState, TriggerState, WaitResult,
)
from .common import READ, Deps, Source

MeasureItem = Literal[
    "PKPK", "MAX", "MIN", "TOP", "BASE", "AMPL", "MEAN", "RMS",
    "PER", "FREQ", "RISE", "FALL", "WID", "DUTY", "OVSN",
    "FPRE", "CMEAN", "CRMS",
]


def register(server: MCPServer, deps: Deps) -> None:
    session = deps.session

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_identify() -> Identity:
        """Identify the connected oscilloscope: manufacturer, model, serial number and firmware.

        Use it to confirm the scope is reachable over USB.
        """
        return session.run(system.identify, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_status() -> Status:
        """Snapshot of the whole scope in one call: acquisition state (SAST), trigger,
        timebase and every enabled channel with its settings.

        Call this first, and before changing settings, to learn the starting
        configuration.
        """

        def snapshot(o):
            channels = [ops_channel.read(o, n) for n in ops_channel.CHANNELS]
            return {
                "acquisition_state": acquisition.state(o),
                "trigger": trigger.read(o),
                "timebase": timebase.read(o),
                "channels": [c for c in channels if c["enabled"]],
            }

        result = session.run(snapshot, retry=True)
        session.remember_mode(result["trigger"]["mode"])
        return result

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_channel(
        channel: Annotated[
            int | None, Field(ge=1, le=4, description="Channel 1-4; omit for all four.")
        ] = None,
    ) -> ChannelList:
        """Vertical settings of one channel or all four: enabled, probe factor,
        coupling, bandwidth limit, unit, invert, volts/div, offset (V) and skew (s)."""
        numbers = ops_channel.CHANNELS if channel is None else (channel,)
        return {"channels": session.run(lambda o: [ops_channel.read(o, n) for n in numbers], retry=True)}

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_timebase() -> TimebaseState:
        """Horizontal settings: time/div (s), trigger delay (s), sample rate (Sa/s),
        memory depth and number of averages."""
        return session.run(timebase.read, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_trigger() -> TriggerState:
        """Trigger settings: mode (AUTO/NORM/SINGLE/STOP), type, source, level (V)
        and coupling. source/level/coupling are null when the scope does not report
        them for the current trigger type."""
        result = session.run(trigger.read, retry=True)
        session.remember_mode(result["mode"])
        return result

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_measure(
        source: Source = "C1",
        items: Annotated[
            list[MeasureItem] | None,
            Field(description="Measurements to read; default PKPK, FREQ, PER, MEAN, RMS, MIN, MAX, DUTY."),
        ] = None,
    ) -> MeasureResult:
        """Automatic measurements on a channel, computed by the scope on the current capture.

        Values are SI (V, s, Hz, %). A value is null when the scope cannot measure
        it (no signal, clipped or too few cycles on screen); the note says how to fix it.
        """
        return {"source": source, "measurements": session.run(measure.measure, source, items, retry=True)}

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_read_counter() -> CounterState:
        """Read the hardware frequency counter (enable it with siglent_set_counter)."""
        return session.run(misc.read_counter, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_awg() -> AwgState:
        """Current waveform generator settings: output on/off, load, wave type,
        frequency (Hz), amplitude (Vpp), offset (V), phase (deg), duty (%), arbitrary
        wave, modulation, sync, burst and sweep. Unsupported fields are null."""
        return session.run(awg.read, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_error() -> ErrorState:
        """Last entry of the scope's error queue (code 0 means no error).

        Useful after siglent_send_raw_command to check that a command was accepted.
        """
        return session.run(system.last_error, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_wait_for_acquisition(
        timeout_s: Annotated[float, Field(ge=0.1, le=300, description="Maximum wait in seconds.")] = 10.0,
    ) -> WaitResult:
        """Wait until the scope reports a completed capture (state Stop or Trig'd).

        Use after siglent_control_acquisition(action='single') before measuring or
        capturing. triggered=false means the timeout passed without a trigger:
        check the trigger level and source.
        """
        return acquisition.wait(lambda: session.run(acquisition.state, retry=True), timeout_s)
```

- [ ] **Step 4: Servidor (solo con `status` registrado en esta task)**

Escribir `siglent_mcp/server.py` así, pero con `from .tools import status` y `TOOL_MODULES = (status,)`; las tasks 13, 14 y 15 amplían esas dos líneas hasta la versión final mostrada:

`siglent_mcp/server.py`:

```python
"""MCP server exposing the Siglent SDS1104X-E oscilloscope over stdio."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer

from osc_cli.ops.waveform import DEFAULT_MAX_SAMPLES

from .session import Session
from .storage import Storage
from .tools import capture, config, danger, decode, status
from .tools.common import Deps

SERVER_NAME = "siglent_sds1104xe_mcp"
INSTRUCTIONS = """\
Controls a Siglent SDS1104X-E oscilloscope (4 channels and a built-in waveform \
generator) over USB.

Start with siglent_get_status to learn the current configuration before changing \
anything. Units are SI: volts, seconds, hertz. Tools marked destructive drive the \
generator output into the circuit under test or overwrite the scope configuration; \
confirm with the user before using them. Captures and decodes save the full data \
under the data directory and return the file paths."""
TOOL_MODULES = (status, config, capture, decode, danger)


def create_server(session: Session | None = None, storage: Storage | None = None,
                  max_samples: int | None = None) -> MCPServer:
    session = session or Session()
    storage = storage or Storage()
    if max_samples is None:
        max_samples = int(os.environ.get("OSC_MAX_SAMPLES", DEFAULT_MAX_SAMPLES))

    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield {}
        finally:
            session.close()

    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS, lifespan=lifespan)
    deps = Deps(session=session, storage=storage, max_samples=max_samples)
    for module in TOOL_MODULES:
        module.register(server, deps)
    return server


# Module-level object so `mcp dev siglent_mcp/server.py` can find it.
server = create_server()


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("OSC_LOG_LEVEL", "INFO"))
    server.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Verificar**

Run: `.venv/bin/python -m pytest tests/mcp_server -q`
Expected: PASS (8).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml siglent_mcp/models.py siglent_mcp/tools siglent_mcp/server.py tests/mcp_server
git commit -m "Add MCP server with read-only status tools"
```

---

### Task 13: Tools de configuración (11)

**Files:**
- Create: `siglent_mcp/tools/config.py`
- Modify: `siglent_mcp/server.py` (`from .tools import config, status`; `TOOL_MODULES = (status, config)`)
- Test: `tests/mcp_server/test_config_tools.py`

**Interfaces:**
- Consumes: `channel.apply`, `timebase.apply`, `trigger.apply`, `acquisition.*`, `decode.configure_*`, `misc.*` (Tasks 4-9); `Session.remember_mode`, `Session.last_continuous_mode` (Task 10); `common.*`, `models.*` (Task 12).
- Produces: tools `siglent_set_channel`, `siglent_set_timebase`, `siglent_set_trigger`, `siglent_control_acquisition`, `siglent_configure_uart_trigger`, `siglent_configure_i2c_trigger`, `siglent_configure_spi_trigger`, `siglent_set_math`, `siglent_set_display`, `siglent_set_counter`, `siglent_save_setup`.

- [ ] **Step 1: Tests que fallan**

`tests/mcp_server/test_config_tools.py`:

```python
import pytest

from osc_cli.device import OscTransportError
from tests.mcp_server.conftest import call

pytestmark = pytest.mark.anyio


async def test_set_channel_writes_only_given_fields(client, fake):
    state = (await call(client, "siglent_set_channel", channel=2, vdiv=0.2, coupling="A1M")).structured_content
    assert fake.writes[-2:] == ["C2:CPL A1M", "C2:VDIV 0.2"]
    assert state["channel"] == 2


async def test_set_channel_validates(client):
    result = await client.call_tool("siglent_set_channel", {"channel": 1, "coupling": "AC"})
    assert result.is_error


async def test_set_timebase(client, fake):
    await call(client, "siglent_set_timebase", memory="70K", tdiv=0.0005)
    assert fake.writes[-2:] == ["MSIZ 70K", "TDIV 0.0005"]


async def test_run_returns_to_last_continuous_mode(client, fake):
    fake.responses["TRMD?"] = ["TRMD NORM", "TRMD STOP"]
    await call(client, "siglent_set_trigger", mode="NORM")
    r = (await call(client, "siglent_control_acquisition", action="run")).structured_content
    assert r["trigger_mode"] == "NORM"
    assert fake.writes[-1] == "TRMD NORM"


async def test_single_suggests_waiting(client, fake):
    r = (await call(client, "siglent_control_acquisition", action="single")).structured_content
    assert fake.writes[-1] == "TRMD SINGLE"
    assert "siglent_wait_for_acquisition" in r["note"]


async def test_single_is_not_retried_after_transport_error(client, fake):
    fake.fail_writes["TRMD SINGLE"] = OscTransportError("pipe")
    result = await client.call_tool("siglent_control_acquisition", {"action": "single"})
    assert result.is_error
    assert "may or may not have run" in result.content[0].text
    assert fake.writes.count("TRMD SINGLE") == 1


async def test_force_and_stop(client, fake):
    await call(client, "siglent_control_acquisition", action="force")
    await call(client, "siglent_control_acquisition", action="stop")
    assert fake.writes[-2:] == ["*TRG", "STOP"]


async def test_serial_trigger_tools(client, fake):
    r = (await call(client, "siglent_configure_uart_trigger", rx="C3", baud=9600)).structured_content
    assert r["protocol"] == "uart" and r["settings"]["baud"] == 9600
    assert "TRIG_UART:RX C3" in fake.writes
    await call(client, "siglent_configure_i2c_trigger", scl="C2", sda="C3")
    await call(client, "siglent_configure_spi_trigger")
    assert "TRIG_IIC:SCL C2" in fake.writes and "TRIG_SPI:CS C4" in fake.writes


async def test_math_display_counter_setup(client, fake):
    await call(client, "siglent_set_math", function="FFT")
    await call(client, "siglent_set_display", menu=False)
    c = (await call(client, "siglent_set_counter", enabled=True)).structured_content
    s = (await call(client, "siglent_save_setup", path="/usb/a.xml")).structured_content
    assert ["MATH:FUNC FFT", "MENU OFF", "FCNT STATE,ON", 'STORE_SETUP FILE,"/usb/a.xml"'] == [
        w for w in fake.writes if w != "CHDR SHORT"
    ]
    assert c["frequency_hz"] == 1000.0 and s == {"action": "saved", "path": "/usb/a.xml"}


async def test_save_setup_rejects_quotes(client):
    result = await client.call_tool("siglent_save_setup", {"path": 'a"b'})
    assert result.is_error and "quotes" in result.content[0].text
```

Run: `.venv/bin/python -m pytest tests/mcp_server/test_config_tools.py -q`
Expected: FAIL (las tools no existen: `is_error` con "Unknown tool").

- [ ] **Step 2: Implementar y registrar**

`siglent_mcp/tools/config.py`:

```python
"""Tools that change scope settings without driving the circuit under test."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from osc_cli.ops import acquisition, decode, misc, timebase, trigger
from osc_cli.ops import channel as ops_channel

from ..errors import tool_errors
from ..models import (
    AcquisitionResult, ChannelState, CounterState, DisplayState, MathState,
    SerialTriggerResult, SetupResult, TimebaseState, TriggerState,
)
from .common import WRITE, WRITE_ONCE, ChannelNumber, Deps, Source

Positive = Annotated[float | None, Field(gt=0)]
SetupPath = Annotated[str, Field(min_length=1, max_length=200, description='File path on the scope, e.g. "/usb/setup1.xml".')]


def register(server: MCPServer, deps: Deps) -> None:
    session = deps.session

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_channel(
        channel: ChannelNumber,
        enabled: bool | None = None,
        vdiv: Annotated[float | None, Field(gt=0, description="Volts per division.")] = None,
        offset: Annotated[float | None, Field(description="Vertical offset in volts.")] = None,
        coupling: Literal["A1M", "D1M", "A50", "D50", "GND"] | None = None,
        bw_limit: Literal["OFF", "20M", "200M"] | None = None,
        probe: Annotated[float | None, Field(gt=0, description="Probe attenuation, e.g. 1 or 10.")] = None,
        invert: bool | None = None,
        unit: Literal["V", "A"] | None = None,
        skew: Annotated[float | None, Field(description="Deskew in seconds.")] = None,
    ) -> ChannelState:
        """Change a channel's vertical settings. Only the arguments you pass change.

        coupling: A=AC, D=DC, 1M/50 = input impedance, GND = grounded. Returns the
        channel state read back from the scope.
        """
        return session.run(
            ops_channel.apply, channel, retry=True,
            enabled=enabled, vdiv=vdiv, offset=offset, coupling=coupling, bw_limit=bw_limit,
            probe=probe, invert=invert, unit=unit, skew=skew,
        )

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_timebase(
        tdiv: Annotated[float | None, Field(gt=0, description="Seconds per division.")] = None,
        delay: Annotated[float | None, Field(description="Horizontal trigger delay in seconds.")] = None,
        memory: Annotated[
            Literal["7K", "70K", "700K", "7M", "14K", "140K", "1.4M", "14M"] | None,
            Field(description="Memory depth. Large depths make siglent_capture_waveform slow; "
                              "7K-700K is plenty for most analysis."),
        ] = None,
        averages: Annotated[int | None, Field(ge=1, le=1024)] = None,
    ) -> TimebaseState:
        """Change horizontal settings. Only the arguments you pass change.

        The 14K/140K/1.4M/14M depths apply when at most two channels are on.
        """
        return session.run(timebase.apply, tdiv, delay, memory, averages, retry=True)

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_trigger(
        mode: Literal["AUTO", "NORM", "SINGLE", "STOP"] | None = None,
        type: Literal["EDGE", "SERIAL", "PULSE", "VIDEO", "SLOPE", "PATTERN", "DROP", "INTV", "RUNT"] | None = None,
        source: Literal["C1", "C2", "C3", "C4", "EXT", "LINE"] | None = None,
        level: Annotated[float | None, Field(description="Trigger level in volts.")] = None,
        coupling: Literal["DC", "AC", "HFREJ", "LFREJ"] | None = None,
    ) -> TriggerState:
        """Change trigger settings. Only the arguments you pass change; the mode is
        applied last. For one-shot captures prefer siglent_control_acquisition(action='single')."""
        result = session.run(trigger.apply, retry=True, mode=mode, type=type,
                             source=source, level=level, coupling=coupling)
        session.remember_mode(mode or result["mode"])
        return result

    @server.tool(annotations=WRITE_ONCE)
    @tool_errors
    def siglent_control_acquisition(action: Literal["run", "stop", "single", "force"]) -> AcquisitionResult:
        """Start, stop or arm the acquisition.

        run: continuous acquisition in the last AUTO/NORM mode. stop: freeze the
        current capture. single: arm one capture; then call
        siglent_wait_for_acquisition. force: trigger now even without a trigger event.
        """

        def act(o):
            mode = None
            if action == "run":
                mode = acquisition.resume(o, session.last_continuous_mode)
            elif action == "stop":
                acquisition.stop(o)
            elif action == "single":
                acquisition.single(o)
                mode = "SINGLE"
            else:
                acquisition.force(o)
            return {"action": action, "trigger_mode": mode, "state": acquisition.state(o)}

        result = session.run(act, retry=False)
        if action == "single":
            result["note"] = "Call siglent_wait_for_acquisition before measuring or capturing."
        return result

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_configure_uart_trigger(
        rx: Source = "C1",
        tx: Source | None = None,
        baud: Annotated[int, Field(ge=50, le=10_000_000)] = 115200,
        parity: Literal["NONE", "EVEN", "ODD"] = "NONE",
        stop_bits: Annotated[float, Field(ge=1, le=2)] = 1.0,
        polarity: Literal["HIGH", "LOW"] = "HIGH",
    ) -> SerialTriggerResult:
        """Set the scope's serial trigger to UART so it triggers on bus traffic.

        This configures triggering only; read the bytes with siglent_decode_uart.
        polarity is the idle level (HIGH for standard TTL/CMOS UART).
        """
        settings = session.run(decode.configure_uart_trigger, rx, tx, baud, parity,
                               stop_bits, polarity, retry=True)
        return {"protocol": "uart", "settings": settings}

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_configure_i2c_trigger(scl: Source = "C1", sda: Source = "C2") -> SerialTriggerResult:
        """Set the scope's serial trigger to I2C. Read transactions with siglent_decode_i2c."""
        return {"protocol": "i2c", "settings": session.run(decode.configure_i2c_trigger, scl, sda, retry=True)}

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_configure_spi_trigger(
        clk: Source = "C1", miso: Source = "C2", mosi: Source = "C3", cs: Source = "C4",
    ) -> SerialTriggerResult:
        """Set the scope's serial trigger to SPI. Read frames with siglent_decode_spi."""
        settings = session.run(decode.configure_spi_trigger, clk, miso, mosi, cs, retry=True)
        return {"protocol": "spi", "settings": settings}

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_math(
        function: Literal["FX", "FY", "FZ", "ADD", "SUB", "MUL", "DIV", "FFT"] | None = None,
        offset: Annotated[float | None, Field(description="Math trace offset.")] = None,
        scale: Annotated[float | None, Field(gt=0, description="Math trace scale per division.")] = None,
    ) -> MathState:
        """Configure the math trace (e.g. ADD of two channels or FFT). Only the arguments you pass change."""
        return session.run(misc.apply_math, function, offset, scale, retry=True)

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_display(
        grid: Literal["FULL", "HALF", "OFF"] | None = None,
        intensity: Annotated[int | None, Field(ge=0, le=100, description="Trace intensity, %.")] = None,
        menu: bool | None = None,
        cursor_mode: Literal["OFF", "TRACK", "HABS", "HREL", "VABS", "VREL"] | None = None,
    ) -> DisplayState:
        """Change display options (grid, trace intensity, side menu, cursors).
        Handy before siglent_capture_screen."""
        return session.run(misc.apply_display, grid, intensity, menu, cursor_mode, retry=True)

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_counter(enabled: bool) -> CounterState:
        """Turn the hardware frequency counter on or off and return its reading."""

        def act(o):
            misc.set_counter(o, enabled)
            return misc.read_counter(o)

        return session.run(act, retry=True)

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_save_setup(path: SetupPath) -> SetupResult:
        """Save the current scope configuration to a file on the scope (internal or USB stick).

        Restore it later with siglent_recall_setup.
        """
        session.run(misc.save_setup, path, retry=True)
        return {"action": "saved", "path": path}
```

En `siglent_mcp/server.py`: `from .tools import config, status` y `TOOL_MODULES = (status, config)`.

- [ ] **Step 3: Verificar**

Run: `.venv/bin/python -m pytest tests/mcp_server -q`
Expected: PASS (18).

- [ ] **Step 4: Commit**

```bash
git add siglent_mcp/tools/config.py siglent_mcp/server.py tests/mcp_server/test_config_tools.py
git commit -m "Add configuration and acquisition control tools"
```

---

### Task 14: Tools de captura y decodificación paginada (5)

**Files:**
- Create: `siglent_mcp/tools/capture.py`, `siglent_mcp/tools/decode.py`
- Modify: `siglent_mcp/server.py` (`from .tools import capture, config, decode, status`; `TOOL_MODULES = (status, config, capture, decode)`)
- Test: `tests/mcp_server/test_capture_decode_tools.py`

**Interfaces:**
- Consumes: `screen.capture_png` (Task 9), `waveform.capture` (Task 8), `decode.load_csv/capture_lines/with_ascii/paginate/diagnose` (Task 9), `osc_cli.decoders`, `Storage.output_path/prune/input_file` (Task 11), `common.report_progress`, `STOPPED_NOTE` (Task 12).
- Produces: tools `siglent_capture_screen` (contenido no estructurado: `[ImageContent]` o `[ImageContent, TextContent]`), `siglent_capture_waveform`, `siglent_decode_uart` (parámetro offline `rx_csv`), `siglent_decode_i2c` (`scl_csv`, `sda_csv`), `siglent_decode_spi` (`clk_csv`, `mosi_csv`, `miso_csv`, `cs_csv`).

- [ ] **Step 1: Tests que fallan**

`tests/mcp_server/test_capture_decode_tools.py`:

```python
import json
from pathlib import Path

import pytest
from mcp import Client

from siglent_mcp.server import create_server
from siglent_mcp.session import Session
from tests.bmp_util import make_bmp, read_png
from tests.fakes import codes_from_volts, make_wavedesc_block
from tests.mcp_server.conftest import call
from tests.test_decoders import DT, i2c_wave, spi_wave, uart_wave

pytestmark = pytest.mark.anyio


def put_wave(fake, source, volts, vdiv=1.0):
    fake.blocks[source] = make_wavedesc_block(codes_from_volts(volts, vdiv), vdiv=vdiv, interval=DT)


async def test_capture_screen_returns_png(client, fake):
    fake.raw["SCDP"] = make_bmp([[(255, 0, 0)] * 3] * 2)
    result = await call(client, "siglent_capture_screen")
    assert [c.type for c in result.content] == ["image"]
    assert result.content[0].mime_type == "image/png"


async def test_capture_screen_saves_inside_data_dir(client, fake, storage):
    fake.raw["SCDP"] = make_bmp([[(0, 255, 0)]])
    result = await call(client, "siglent_capture_screen", save_path="shot.png")
    assert result.content[1].text == f"Saved to {storage.root / 'shot.png'}"
    assert read_png((storage.root / "shot.png").read_bytes())[2] == [[(0, 255, 0)]]
    bad = await client.call_tool("siglent_capture_screen", {"save_path": "../x.png"})
    assert bad.is_error and "inside" in bad.content[0].text


async def test_capture_waveform_two_channels(client, fake):
    put_wave(fake, "C1", [0.0, 1.0] * 50)
    put_wave(fake, "C2", [0.5] * 100)
    r = (await call(client, "siglent_capture_waveform", sources=["C1", "C2"], max_points=10)).structured_content
    assert fake.writes[1] == "STOP"
    assert r["acquisition_stopped"] is True and "run" in r["note"]
    c1 = r["sources"]["C1"]
    assert c1["n"] == 100 and c1["vpp"] == pytest.approx(1.0) and len(c1["points"]) <= 10
    assert Path(c1["csv_path"]).read_text().startswith("index,voltage,time\n")


async def test_capture_waveform_dedupes_sources(client, fake):
    put_wave(fake, "C1", [0.0] * 10)
    r = (await call(client, "siglent_capture_waveform", sources=["C1", "C1"], save_csv=False)).structured_content
    assert list(r["sources"]) == ["C1"]
    assert "csv_path" not in r["sources"]["C1"]
    assert r["acquisition_stopped"] is False


async def test_capture_waveform_refuses_huge_memory(fake, storage):
    put_wave(fake, "C1", [0.0] * 5000)
    server = create_server(session=Session(lambda: fake), storage=storage, max_samples=1000)
    async with Client(server) as c:
        result = await c.call_tool("siglent_capture_waveform", {"sources": ["C1"]})
    assert result.is_error and "OSC_MAX_SAMPLES" in result.content[0].text


async def test_decode_uart_live_with_pagination(client, fake):
    put_wave(fake, "C1", uart_wave(b"Hola", 9600))
    r = (await call(client, "siglent_decode_uart", baud=9600, limit=2)).structured_content
    assert r["text"] == "Ho" and r["total"] == 4
    assert r["has_more"] is True and r["next_offset"] == 2
    assert [f["value"] for f in json.loads(Path(r["json_path"]).read_text())] == list(b"Hola")
    r2 = (await call(client, "siglent_decode_uart", baud=9600, limit=2, offset=2, freeze=False)).structured_content
    assert r2["text"] == "la" and r2["has_more"] is False


async def test_decode_uart_from_capture_csv_round_trip(client, fake):
    put_wave(fake, "C1", uart_wave(b"OK!", 9600))
    cap = (await call(client, "siglent_capture_waveform", sources=["C1"])).structured_content
    fake.blocks.clear()  # offline decode must not touch the scope
    r = (await call(client, "siglent_decode_uart", baud=9600, rx_csv=cap["sources"]["C1"]["csv_path"])).structured_content
    assert r["text"] == "OK!" and r["acquisition_stopped"] is False


async def test_decode_uart_nothing_found_has_diagnostics(client, fake):
    put_wave(fake, "C1", [3.3] * 1000)
    r = (await call(client, "siglent_decode_uart", baud=9600)).structured_content
    assert r["total"] == 0 and "barely moves" in r["diagnostics"]["hint"]


async def test_decode_i2c_live(client, fake):
    scl, sda = i2c_wave([(0x50, False, [0x12])])
    put_wave(fake, "C1", scl)
    put_wave(fake, "C2", sda)
    r = (await call(client, "siglent_decode_i2c")).structured_content
    assert r["transactions"][0]["address"] == 0x50 and r["transactions"][0]["data"] == [0x12]


async def test_decode_i2c_offline_needs_both_csvs(client, tmp_path):
    f = tmp_path / "scl.csv"
    f.write_text("index,voltage,time\n0,0,0\n1,0,1e-6\n")
    r = await client.call_tool("siglent_decode_i2c", {"scl_csv": str(f)})
    assert r.is_error and "sda_csv" in r.content[0].text


async def test_decode_spi_live(client, fake):
    clk, mosi, cs = spi_wave([0xA5, 0x3C])
    put_wave(fake, "C1", clk)
    put_wave(fake, "C2", mosi)
    put_wave(fake, "C4", cs)
    r = (await call(client, "siglent_decode_spi", mosi="C2", cs="C4")).structured_content
    assert [f["mosi"] for f in r["frames"]] == [[0xA5], [0x3C]]
    assert all(f["miso"] == [] for f in r["frames"])


async def test_decode_spi_needs_a_data_line(client, fake):
    put_wave(fake, "C1", [0.0] * 10)
    r = await client.call_tool("siglent_decode_spi", {})
    assert r.is_error and "mosi" in r.content[0].text
```

Run: `.venv/bin/python -m pytest tests/mcp_server/test_capture_decode_tools.py -q`
Expected: FAIL ("Unknown tool").

- [ ] **Step 2: Implementar y registrar**

`siglent_mcp/tools/capture.py`:

```python
"""Screenshot and waveform capture tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import Context, Image, MCPServer
from mcp_types import TextContent
from pydantic import Field

from osc_cli.ops import screen, waveform

from ..errors import tool_errors
from ..models import WaveformResult
from .common import READ, STOPPED_NOTE, WRITE, Deps, Source, report_progress


def register(server: MCPServer, deps: Deps) -> None:
    session, storage = deps.session, deps.storage

    @server.tool(annotations=READ, structured_output=False)
    @tool_errors
    def siglent_capture_screen(
        save_path: Annotated[
            str | None,
            Field(description="Optional PNG file name, relative to the data directory, to also save the image."),
        ] = None,
    ) -> list[Image | TextContent]:
        """Screenshot of the oscilloscope display as a PNG image you can look at.

        Good for a quick visual check of traces, cursors and on-screen measurements.
        For numbers use siglent_measure or siglent_capture_waveform instead.
        """
        png = session.run(screen.capture_png, retry=True)
        content: list[Image | TextContent] = [Image(data=png, format="png")]
        if save_path:
            path = storage.output_path("screens", ".png", save_path)
            path.write_bytes(png)
            content.append(TextContent(type="text", text=f"Saved to {path}"))
        return content

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_capture_waveform(
        ctx: Context,
        sources: Annotated[
            list[Source],
            Field(min_length=1, max_length=4, description='Channels to capture, e.g. ["C1"] or ["C1", "C2"].'),
        ],
        max_points: Annotated[
            int, Field(ge=2, le=5000, description="Points returned per channel (min/max decimated).")
        ] = 500,
        save_csv: Annotated[
            bool, Field(description="Also save every sample to a CSV (index,voltage,time) and return its path.")
        ] = True,
    ) -> WaveformResult:
        """Capture sampled data from one or more channels.

        Returns per channel: statistics over all samples (min, max, vpp, mean, rms
        in V; sample_rate in Sa/s; duration in s), up to max_points [time_s, volts]
        pairs decimated with min/max buckets so glitches are kept, and the path of a
        CSV with every sample (usable by the decode tools via *_csv). With several
        channels the acquisition is stopped first so they share one trigger.
        Captures above OSC_MAX_SAMPLES points per channel are refused; reduce the
        memory depth with siglent_set_timebase.
        """

        def csv_path_for(source):
            return storage.output_path("waveforms", f"_{source}.csv")

        def progress(done, total, message):
            report_progress(ctx, done, total, message)

        result = session.run(
            waveform.capture, sources, max_points, deps.max_samples,
            csv_path_for if save_csv else None, progress, retry=True,
        )
        if save_csv:
            storage.prune("waveforms")
        if result["acquisition_stopped"]:
            result["note"] = STOPPED_NOTE
        return result
```

`siglent_mcp/tools/decode.py`:

```python
"""UART / I2C / SPI byte extraction from captured (or saved) waveforms."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from osc_cli import decoders
from osc_cli.ops import decode

from ..errors import tool_errors
from ..models import I2cPage, SpiPage, UartPage
from .common import STOPPED_NOTE, WRITE, Deps, Source

Limit = Annotated[int, Field(ge=1, le=2000, description="Items per page.")]
Offset = Annotated[int, Field(ge=0, description="Index of the first item; use next_offset to page.")]
Threshold = Annotated[float | None, Field(description="Logic threshold in volts; default is the midpoint of the signal.")]
Freeze = Annotated[bool, Field(description="Stop the acquisition first so all lines come from one capture. Leaves the scope stopped.")]
CsvPath = Annotated[str | None, Field(description="Decode this CSV (from siglent_capture_waveform) instead of capturing.")]


def _acquire(deps: Deps, live: dict, offline: dict, required: tuple, freeze: bool):
    """Samples per bus line (role -> volts), dt, and whether the scope was stopped."""
    if any(offline.values()):
        chosen = {role: path for role, path in offline.items() if path}
        missing = [role for role in required if role not in chosen]
        if missing:
            raise ValueError("Offline decode is missing " + ", ".join(f"{r}_csv" for r in missing))
        lines, dt = {}, None
        for role, path in chosen.items():
            lines[role], line_dt = decode.load_csv(deps.storage.input_file(path))
            dt = dt or line_dt
        return lines, dt, False
    chosen = {role: src for role, src in live.items() if src}
    captured, dt, stopped = deps.session.run(
        decode.capture_lines, list(chosen.values()), freeze, deps.max_samples, retry=True,
    )
    return {role: captured[src] for role, src in chosen.items()}, dt, stopped


def _page(deps: Deps, kind: str, items: list, limit: int, offset: int, stopped: bool,
          diag_samples, threshold) -> dict:
    path = deps.storage.output_path("decodes", f"_{kind}.json")
    path.write_text(json.dumps(items))
    deps.storage.prune("decodes")
    page = decode.paginate(items, limit, offset)
    result = {key: page[key] for key in ("total", "count", "offset", "has_more", "next_offset")}
    result.update(json_path=str(path), acquisition_stopped=stopped, items=page["items"])
    if not items:
        result["diagnostics"] = decode.diagnose(diag_samples, threshold)
    if stopped:
        result["note"] = STOPPED_NOTE
    return result


def register(server: MCPServer, deps: Deps) -> None:

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_decode_uart(
        rx: Source = "C1",
        baud: Annotated[int, Field(ge=50, le=10_000_000)] = 115200,
        bits: Annotated[int, Field(ge=5, le=9)] = 8,
        parity: Literal["NONE", "EVEN", "ODD"] = "NONE",
        stop_bits: Annotated[float, Field(ge=1, le=2)] = 1.0,
        polarity: Literal["HIGH", "LOW"] = "HIGH",
        msb_first: bool = False,
        threshold: Threshold = None,
        freeze: Freeze = True,
        rx_csv: CsvPath = None,
        limit: Limit = 200,
        offset: Offset = 0,
    ) -> UartPage:
        """Extract UART bytes from a channel (decoded on the host from the captured samples).

        Returns a page of frames {time_s, value, ascii, errors} plus the page as text,
        and json_path with every frame. errors lists 'parity'/'framing' problems.
        When nothing decodes, diagnostics shows the levels seen and what to adjust.
        The capture must hold at least 3 samples per bit (raise time/div resolution
        for high baud rates).
        """
        lines, dt, stopped = _acquire(deps, {"rx": rx}, {"rx": rx_csv}, ("rx",), freeze)
        frames = decode.with_ascii(decoders.uart_decode(
            lines["rx"], dt, baud, bits, parity, stop_bits, polarity, not msb_first, threshold,
        ))
        result = _page(deps, "uart", frames, limit, offset, stopped, lines["rx"], threshold)
        result["frames"] = result.pop("items")
        result["text"] = "".join(f["ascii"] for f in result["frames"])
        return result

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_decode_i2c(
        scl: Source = "C1",
        sda: Source = "C2",
        threshold: Threshold = None,
        freeze: Freeze = True,
        scl_csv: CsvPath = None,
        sda_csv: CsvPath = None,
        limit: Limit = 200,
        offset: Offset = 0,
    ) -> I2cPage:
        """Extract I2C transactions from the SCL/SDA channels (decoded on the host).

        Each transaction: {time, address (7-bit), read, data, acks, repeated_start};
        acks[0] is the address ACK, a False entry is a NACK.
        """
        lines, dt, stopped = _acquire(
            deps, {"scl": scl, "sda": sda}, {"scl": scl_csv, "sda": sda_csv}, ("scl", "sda"), freeze,
        )
        txns = decoders.i2c_decode(lines["scl"], lines["sda"], dt, threshold, threshold)
        result = _page(deps, "i2c", txns, limit, offset, stopped, lines["sda"], threshold)
        result["transactions"] = result.pop("items")
        return result

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_decode_spi(
        clk: Source = "C1",
        mosi: Source | None = None,
        miso: Source | None = None,
        cs: Annotated[Source | None, Field(description="Chip select (active low); without it the capture is one frame.")] = None,
        bits: Annotated[int, Field(ge=4, le=32)] = 8,
        cpol: Literal[0, 1] = 0,
        cpha: Literal[0, 1] = 0,
        lsb_first: bool = False,
        threshold: Threshold = None,
        freeze: Freeze = True,
        clk_csv: CsvPath = None,
        mosi_csv: CsvPath = None,
        miso_csv: CsvPath = None,
        cs_csv: CsvPath = None,
        limit: Limit = 200,
        offset: Offset = 0,
    ) -> SpiPage:
        """Extract SPI words from CLK and MOSI and/or MISO (decoded on the host).

        Give at least one of mosi/miso. Each frame (one per CS assertion):
        {time, mosi: [words], miso: [words]}.
        """
        live = {"clk": clk, "mosi": mosi, "miso": miso, "cs": cs}
        offline = {"clk": clk_csv, "mosi": mosi_csv, "miso": miso_csv, "cs": cs_csv}
        lines, dt, stopped = _acquire(deps, live, offline, ("clk",), freeze)
        if "mosi" not in lines and "miso" not in lines:
            raise ValueError("Give at least one of mosi / miso (or mosi_csv / miso_csv).")
        frames = decoders.spi_decode(
            lines["clk"], lines.get("mosi"), lines.get("miso"), lines.get("cs"),
            dt, bits, cpol, cpha, not lsb_first, threshold,
        )
        result = _page(deps, "spi", frames, limit, offset, stopped, lines["clk"], threshold)
        result["frames"] = result.pop("items")
        return result
```

En `siglent_mcp/server.py`: `from .tools import capture, config, decode, status` y `TOOL_MODULES = (status, config, capture, decode)`.

- [ ] **Step 3: Verificar**

Run: `.venv/bin/python -m pytest tests/mcp_server -q`
Expected: PASS (30).

- [ ] **Step 4: Commit**

```bash
git add siglent_mcp/tools/capture.py siglent_mcp/tools/decode.py siglent_mcp/server.py tests/mcp_server/test_capture_decode_tools.py
git commit -m "Add screenshot, waveform capture and paginated serial decode tools"
```

---

### Task 15: Tools destructivas (8), catálogo completo, stdio y empaquetado

**Files:**
- Create: `siglent_mcp/tools/danger.py`
- Modify: `siglent_mcp/server.py` (versión final: `from .tools import capture, config, danger, decode, status`; `TOOL_MODULES = (status, config, capture, decode, danger)`)
- Modify: `pyproject.toml` (script `siglent-mcp`), `README.md`
- Test: `tests/mcp_server/test_danger_tools.py`, `tests/mcp_server/test_server.py`

**Interfaces:**
- Consumes: `awg.apply/apply_burst/apply_sweep` (Task 7), `misc.recall_setup`, `system.reset/selftest/calibrate/raw_command` (Task 6), `Session.run(..., restore_header=True, timeout_ms=...)` (Task 10).
- Produces: tools `siglent_recall_setup`, `siglent_set_awg`, `siglent_set_awg_burst`, `siglent_set_awg_sweep`, `siglent_reset`, `siglent_run_selftest`, `siglent_calibrate`, `siglent_send_raw_command`; script de consola `siglent-mcp`.

- [ ] **Step 1: Tests que fallan**

`tests/mcp_server/test_danger_tools.py`:

```python
import pytest

from osc_cli.device import OscTransportError
from tests.mcp_server.conftest import call

pytestmark = pytest.mark.anyio


async def test_set_awg_turns_output_on_last(client, fake):
    state = (await call(client, "siglent_set_awg", enabled=True, wave="SQUARE", freq=5000, amp=2)).structured_content
    assert [w for w in fake.writes if w != "CHDR SHORT"] == [
        "C1:BSWV WVTP,SQUARE", "C1:BSWV FRQ,5000.0", "C1:BSWV AMP,2.0", "C1:OUTP ON",
    ]
    assert state["wave"] == "SINE"  # fake read-back


async def test_set_awg_rejects_conflicting_arb(client):
    r = await client.call_tool("siglent_set_awg", {"arb": "StairUp", "wave": "SINE"})
    assert r.is_error and "arb" in r.content[0].text


async def test_burst_and_sweep(client, fake):
    b = (await call(client, "siglent_set_awg_burst", enabled=True, cycles=3)).structured_content
    s = (await call(client, "siglent_set_awg_sweep", start=100, stop=200)).structured_content
    assert b["cycles"] == 1 and s["direction"] == "UP"
    assert "C1:BTWV NCYC,3" in fake.writes and "C1:SWWV STOP,200.0" in fake.writes


async def test_reset_restores_header(client, fake):
    await call(client, "siglent_reset")
    assert fake.writes[-2:] == ["*RST", "CHDR SHORT"]


async def test_recall_setup(client, fake):
    r = (await call(client, "siglent_recall_setup", path="/usb/a.xml")).structured_content
    assert r == {"action": "recalled", "path": "/usb/a.xml"}
    assert fake.writes[-2:] == ['RECALL_SETUP FILE,"/usb/a.xml"', "CHDR SHORT"]


async def test_selftest_and_calibrate(client, fake):
    t = (await call(client, "siglent_run_selftest")).structured_content
    assert t == {"passed": True, "result": "0", "raw": "*TST 0"}
    fake.responses["*CAL?"] = "*CAL 1"
    c = (await call(client, "siglent_calibrate")).structured_content
    assert c["passed"] is False


async def test_raw_command_restores_header(client, fake):
    r = (await call(client, "siglent_send_raw_command", command="CHDR OFF", expect_response=False)).structured_content
    assert r == {"command": "CHDR OFF", "response": None}
    assert fake.writes[-2:] == ["CHDR OFF", "CHDR SHORT"]
    q = (await call(client, "siglent_send_raw_command", command="TDIV?", expect_response=True)).structured_content
    assert q["response"] == "TDIV 1.00E-03S"


async def test_raw_command_not_retried(client, fake):
    fake.fail_writes["C1:OUTP ON"] = OscTransportError("pipe")
    r = await client.call_tool("siglent_send_raw_command", {"command": "C1:OUTP ON", "expect_response": False})
    assert r.is_error and "may or may not have run" in r.content[0].text
    assert fake.writes.count("C1:OUTP ON") == 1
```

`tests/mcp_server/test_server.py`:

```python
import os
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.anyio

# name: (read_only, destructive, idempotent) — the table in the spec.
EXPECTED = {
    "siglent_identify": (True, False, True),
    "siglent_get_status": (True, False, True),
    "siglent_get_channel": (True, False, True),
    "siglent_get_timebase": (True, False, True),
    "siglent_get_trigger": (True, False, True),
    "siglent_measure": (True, False, True),
    "siglent_capture_screen": (True, False, True),
    "siglent_read_counter": (True, False, True),
    "siglent_get_awg": (True, False, True),
    "siglent_get_error": (True, False, True),
    "siglent_wait_for_acquisition": (True, False, True),
    "siglent_set_channel": (False, False, True),
    "siglent_set_timebase": (False, False, True),
    "siglent_set_trigger": (False, False, True),
    "siglent_control_acquisition": (False, False, False),
    "siglent_capture_waveform": (False, False, True),
    "siglent_decode_uart": (False, False, True),
    "siglent_decode_i2c": (False, False, True),
    "siglent_decode_spi": (False, False, True),
    "siglent_configure_uart_trigger": (False, False, True),
    "siglent_configure_i2c_trigger": (False, False, True),
    "siglent_configure_spi_trigger": (False, False, True),
    "siglent_set_math": (False, False, True),
    "siglent_set_display": (False, False, True),
    "siglent_set_counter": (False, False, True),
    "siglent_save_setup": (False, False, True),
    "siglent_recall_setup": (False, True, True),
    "siglent_set_awg": (False, True, True),
    "siglent_set_awg_burst": (False, True, True),
    "siglent_set_awg_sweep": (False, True, True),
    "siglent_reset": (False, True, True),
    "siglent_run_selftest": (False, True, False),
    "siglent_calibrate": (False, True, False),
    "siglent_send_raw_command": (False, True, False),
}


async def test_tool_catalog_and_annotations(client):
    tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == set(EXPECTED)
    for name, (read_only, destructive, idempotent) in EXPECTED.items():
        a = tools[name].annotations
        assert (a.read_only_hint, a.destructive_hint, a.idempotent_hint) == (read_only, destructive, idempotent), name
        assert a.open_world_hint is False, name
        assert tools[name].description, name
        if name != "siglent_capture_screen":
            assert tools[name].output_schema is not None, name


async def test_stdio_server_starts_without_a_scope(tmp_path):
    root = Path(__file__).resolve().parents[2]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "siglent_mcp.server"],
        cwd=str(root),
        env={**os.environ, "OSC_DATA_DIR": str(tmp_path), "OSC_LOG_LEVEL": "DEBUG"},
    )
    async with Client(params) as c:
        tools = (await c.list_tools()).tools
    assert len(tools) == len(EXPECTED)
```

Run: `.venv/bin/python -m pytest tests/mcp_server/test_danger_tools.py tests/mcp_server/test_server.py -q`
Expected: FAIL ("Unknown tool" y catálogo con 26 tools en vez de 34).

- [ ] **Step 2: Implementar y registrar**

`siglent_mcp/tools/danger.py`:

```python
"""Destructive tools: drive the generator output or overwrite the configuration."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from osc_cli.ops import awg, misc, system
from osc_cli.ops._parse import value_of

from ..errors import tool_errors
from ..models import AwgState, BurstState, RawResult, ResetResult, SelfTestResult, SetupResult, SweepState
from .common import DANGER, DANGER_ONCE, Deps, report_progress

LONG_TIMEOUT_MS = 120_000
RAW_HELP = """Send one command string to the scope exactly as written.

This firmware speaks the LeCroy X-Stream dialect, not standard Siglent SCPI:
channel settings are C<n>:VDIV/OFST/CPL/TRA, measurements C<n>:PAVA? <param>,
timebase TDIV/TRDL/MSIZ, trigger TRMD/TRSE/TRSR/TRLV; the generator uses Siglent
C1:BSWV/C1:OUTP. Set expect_response=true for queries (commands ending in '?').
The server resets the header mode to CHDR SHORT afterwards. Check
siglent_get_error if the scope ignores a command. Prefer the dedicated tools."""


def _selftest_result(raw: str) -> dict:
    text = value_of(raw)
    code = text.strip()
    passed = (code == "0") if code.lstrip("-").isdigit() else None
    return {"passed": passed, "result": text, "raw": raw}


def register(server: MCPServer, deps: Deps) -> None:
    session = deps.session

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_recall_setup(
        path: Annotated[str, Field(min_length=1, max_length=200, description="Setup file path on the scope.")],
    ) -> SetupResult:
        """Load a setup file stored on the scope, replacing the whole current configuration.

        Check the new state with siglent_get_status afterwards.
        """
        session.run(misc.recall_setup, path, retry=False, restore_header=True)
        return {"action": "recalled", "path": path}

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_set_awg(
        enabled: Annotated[bool | None, Field(description="Generator output on/off; applied last when turning on, first when turning off.")] = None,
        wave: Literal["SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC"] | None = None,
        freq: Annotated[float | None, Field(gt=0, description="Frequency in Hz.")] = None,
        amp: Annotated[float | None, Field(gt=0, description="Amplitude in Vpp.")] = None,
        offset: Annotated[float | None, Field(description="DC offset in volts.")] = None,
        phase: Annotated[float | None, Field(ge=0, le=360, description="Phase in degrees.")] = None,
        duty: Annotated[float | None, Field(gt=0, lt=100, description="Square wave duty cycle, %.")] = None,
        load: Literal["HZ", "50"] | None = None,
        arb: Literal["StairUp", "StairDn", "StairUD", "Ppulse", "Npulse", "Trapezia",
                     "Upramp", "Dnramp", "ExpFal", "ExpRise"] | None = None,
        modulation: bool | None = None,
        sync: bool | None = None,
    ) -> AwgState:
        """Configure the built-in waveform generator. DRIVES A SIGNAL INTO THE CIRCUIT
        connected to the generator output when enabled: confirm amplitude and offset
        with the user first.

        Only the arguments you pass change. load is the expected termination (HZ =
        high impedance, 50 = 50 ohm) and scales the actual output voltage.
        """
        return session.run(
            awg.apply, retry=True, enabled=enabled, wave=wave, freq=freq, amp=amp, offset=offset,
            phase=phase, duty=duty, load=load, arb=arb, modulation=modulation, sync=sync,
        )

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_set_awg_burst(
        enabled: bool | None = None,
        cycles: Annotated[int | None, Field(ge=1, le=1_000_000, description="Cycles per burst.")] = None,
        period: Annotated[float | None, Field(gt=0, description="Burst period in seconds.")] = None,
    ) -> BurstState:
        """Configure burst mode of the waveform generator (N cycles every period). Drives the output."""
        return session.run(awg.apply_burst, enabled, cycles, period, retry=True)

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_set_awg_sweep(
        enabled: bool | None = None,
        start: Annotated[float | None, Field(gt=0, description="Start frequency in Hz.")] = None,
        stop: Annotated[float | None, Field(gt=0, description="Stop frequency in Hz.")] = None,
        time: Annotated[float | None, Field(gt=0, description="Sweep time in seconds.")] = None,
        direction: Literal["UP", "DOWN"] | None = None,
    ) -> SweepState:
        """Configure a frequency sweep on the waveform generator. Drives the output."""
        return session.run(awg.apply_sweep, enabled, start, stop, time, direction, retry=True)

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_reset() -> ResetResult:
        """Restore factory defaults (*RST). Erases the whole current configuration."""
        session.run(system.reset, retry=False, restore_header=True)
        session.last_continuous_mode = None
        return {"status": "Factory defaults restored (*RST). Check the new state with siglent_get_status."}

    @server.tool(annotations=DANGER_ONCE)
    @tool_errors
    def siglent_run_selftest(ctx: Context) -> SelfTestResult:
        """Run the scope's internal self-test (*TST?). Disconnects the inputs and can
        take up to two minutes. passed is true when the scope reports 0."""
        report_progress(ctx, 0, 1, "self-test running")
        raw = session.run(system.selftest, retry=False, timeout_ms=LONG_TIMEOUT_MS)
        report_progress(ctx, 1, 1, "self-test finished")
        return _selftest_result(raw)

    @server.tool(annotations=DANGER_ONCE)
    @tool_errors
    def siglent_calibrate(ctx: Context) -> SelfTestResult:
        """Run self-calibration (*CAL?). Disconnect all probes first; takes up to two
        minutes. passed is true when the scope reports 0."""
        report_progress(ctx, 0, 1, "calibration running")
        raw = session.run(system.calibrate, retry=False, timeout_ms=LONG_TIMEOUT_MS)
        report_progress(ctx, 1, 1, "calibration finished")
        return _selftest_result(raw)

    @server.tool(annotations=DANGER_ONCE, description=RAW_HELP)
    @tool_errors
    def siglent_send_raw_command(
        command: Annotated[str, Field(min_length=1, max_length=512)],
        expect_response: bool,
    ) -> RawResult:
        response = session.run(system.raw_command, command, expect_response,
                               retry=False, restore_header=True)
        return {"command": command, "response": response}
```

En `siglent_mcp/server.py`: `from .tools import capture, config, danger, decode, status` y `TOOL_MODULES = (status, config, capture, decode, danger)`.

- [ ] **Step 3: Empaquetado final**

`pyproject.toml` completo tras esta task:

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
[project]
name = "sds1104x-cli"
version = "1.0.0"
description = "Full-featured CLI to control a Siglent SDS1104X-E oscilloscope over USBTMC"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
dependencies = [
    "click>=8.0",
    "pyvisa>=1.13",
    "pyvisa-py>=0.5",
    "pyusb>=1.2",
]

[project.optional-dependencies]
mcp = ["mcp>=2.3,<3", "typing_extensions>=4.12"]
dev = ["pytest>=8", "anyio>=4.10", "mcp[cli]>=2.3,<3", "typing_extensions>=4.12"]

[project.scripts]
osc = "osc_cli.cli:run"
siglent-mcp = "siglent_mcp.server:main"

[tool.setuptools]
packages = ["osc_cli", "osc_cli.commands", "osc_cli.ops", "siglent_mcp", "siglent_mcp.tools"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["hw: needs a real SDS1104X-E connected (run with OSC_HW=1)"]
```

Run: `.venv/bin/pip install -e ".[dev]" && ls .venv/bin/siglent-mcp`
Expected: la ruta del script existe.

- [ ] **Step 4: README**

Insertar esta sección justo antes de `## Notas de implementación`:

````markdown
## Servidor MCP (para Claude y otros agentes)

El paquete incluye `siglent-mcp`, un servidor [MCP](https://modelcontextprotocol.io)
que expone el osciloscopio como 34 tools (`siglent_*`): estado, configuración,
mediciones, capturas de pantalla (PNG) y de forma de onda, decodificación
UART/I2C/SPI y el generador AWG.

```bash
.venv/bin/pip install -e ".[mcp]"          # requiere Python >= 3.10
claude mcp add siglent -- "$PWD/.venv/bin/siglent-mcp"
```

Para probarlo sin cliente: `.venv/bin/pip install -e ".[dev]"` y
`.venv/bin/mcp dev siglent_mcp/server.py` (MCP Inspector; necesita `uv` y `npx`).

Las tools que cambian la salida del generador o sobrescriben la configuración
(`siglent_set_awg*`, `siglent_reset`, `siglent_recall_setup`,
`siglent_calibrate`, `siglent_run_selftest`, `siglent_send_raw_command`) se
marcan como destructivas para que el cliente pida confirmación.

| Variable | Default | Uso |
|---|---|---|
| `OSC_RESOURCE` | autodetección | Recurso VISA explícito |
| `OSC_TIMEOUT_MS` | `5000` | Timeout de E/S por lectura |
| `OSC_LOCK_TIMEOUT_S` | `120` | Espera máxima por el equipo ocupado |
| `OSC_DATA_DIR` | `~/.local/share/siglent-mcp` | CSV, PNG y JSON generados |
| `OSC_KEEP_FILES` | `20` | Archivos autogenerados que se conservan por tipo |
| `OSC_MAX_SAMPLES` | `2000000` | Puntos máximos por canal en una captura |
| `OSC_LOG_LEVEL` | `INFO` | Logs (van a stderr) |

Evaluación con Claude (opcional, contra el equipo real; ver el comentario de
`evaluation/siglent_eval.xml` para el cableado):

```bash
pip install anthropic
ANTHROPIC_API_KEY=... python ~/.claude/skills/mcp-builder/scripts/evaluation.py \
  -t stdio -c .venv/bin/siglent-mcp -m claude-opus-5-5 evaluation/siglent_eval.xml
```
````

Y en la sección `## Tests`, reemplazar ``Tests offline: `python tests/test_decoders.py`.`` por:

```markdown
Tests offline: `.venv/bin/python -m pytest` (instala antes `.[dev]`).
Tests contra el equipo real: `OSC_HW=1 .venv/bin/python -m pytest tests/hw -v -s`.
```

- [ ] **Step 5: Verificar todo**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (253 tests; el de stdio lanza el servidor real como subproceso).

- [ ] **Step 6: Commit**

```bash
git add siglent_mcp/tools/danger.py siglent_mcp/server.py pyproject.toml README.md tests/mcp_server/test_danger_tools.py tests/mcp_server/test_server.py
git commit -m "Add destructive tools, siglent-mcp entry point and MCP docs"
```

---

### Task 16: Smoke tests de hardware y evaluación

**Files:**
- Create: `tests/hw/__init__.py` (vacío), `tests/hw/test_smoke.py`, `evaluation/siglent_eval.xml`

**Interfaces:**
- Consumes: ops (Tasks 4-9), `get_device`, `bmp_to_png`.
- Produces: tests marcados `hw` (omitidos salvo `OSC_HW=1`) que resuelven las preguntas abiertas del spec, y el XML de evaluación para `mcp-builder`.

- [ ] **Step 1: Escribir los tests de hardware**

`tests/hw/test_smoke.py`:

```python
"""Smoke tests against a real SDS1104X-E. Skipped unless OSC_HW=1.

Setup: scope on and connected over USB, the probe on C1 hooked to the
calibration output (1 kHz square wave). Run:

    OSC_HW=1 .venv/bin/python -m pytest tests/hw -v -s

The tests restore the settings they change. Several of them settle open
questions from the spec; their assertion messages say what to change if the
firmware behaves differently.
"""

import os
import struct
import time

import pytest

from osc_cli.device import OscError, get_device
from osc_cli.imaging import PNG_SIGNATURE, bmp_to_png
from osc_cli.ops import acquisition, channel, measure, screen, system, timebase, trigger, waveform
from osc_cli.ops._parse import value_of

pytestmark = [
    pytest.mark.hw,
    pytest.mark.skipif(os.environ.get("OSC_HW") != "1", reason="set OSC_HW=1 with the scope connected"),
]


@pytest.fixture(scope="module")
def osc():
    o = get_device(os.environ.get("OSC_RESOURCE") or None)
    o.write("CHDR SHORT")
    yield o
    o.close()


def test_identify(osc):
    info = system.identify(osc)
    print(info)
    assert info["manufacturer"].upper() == "SIGLENT"
    assert info["model"].startswith("SDS")


def test_status_reads(osc):
    print(channel.read(osc, 1), timebase.read(osc), trigger.read(osc), acquisition.state(osc))


def test_measure_calibration_signal(osc):
    m = measure.measure(osc, "C1", ["FREQ", "PKPK"])
    print(m)
    assert m["FREQ"]["value"] == pytest.approx(1000, rel=0.05), "Is C1 on the CAL output?"


def test_channel_set_get_round_trip(osc):
    before = channel.read(osc, 1)
    try:
        assert channel.apply(osc, 1, vdiv=1.0)["vdiv"] == pytest.approx(1.0)
    finally:
        channel.apply(osc, 1, vdiv=before["vdiv"])


def test_screen_dump_format(osc):
    bmp = screen.capture_bmp(osc)
    bpp = struct.unpack_from("<H", bmp, 28)[0]
    print(f"SCDP: {len(bmp)} bytes, {bpp} bpp")
    assert bmp_to_png(bmp).startswith(PNG_SIGNATURE)


def test_capture_and_sparsing(osc):
    """Settles whether WFSU SP is honoured and how HORIZ_INTERVAL behaves with it."""
    count = waveform.sample_count(osc, "C1")
    print(f"SANU? C1 -> {count}")
    assert count, "SANU? did not answer: fetch() then cannot plan sparsing; use MSIZ? instead"
    limit = max(count // 4, 1000)
    try:
        raw = waveform.fetch(osc, "C1", max_samples=limit)
    except OscError as e:
        pytest.fail(f"WFSU SP ignored by the firmware ({e}). Expected: fetch refuses; "
                    "document in README that captures need memory <= OSC_MAX_SAMPLES.")
    full_span = 14 * timebase.read(osc)["tdiv"]
    span = len(raw.codes) * raw.horz_interval
    print(f"{len(raw.codes)} points, span {span:.6g} s, screen {full_span:.6g} s")
    assert span == pytest.approx(full_span, rel=0.1), (
        "With sparsing the time span is wrong: the descriptor interval is probably already "
        "scaled; drop the '* sparsing' factor in parse_wavedesc."
    )


def test_single_wait_and_resume(osc):
    """Settles that SAST? reports completion and that TRMD (not ARM) resumes."""
    previous = trigger.read(osc)["mode"]
    try:
        acquisition.single(osc)
        result = acquisition.wait(lambda: acquisition.state(osc), 5)
        print(result)
        assert result["triggered"], "SAST? never reported Stop/Trig'd: switch wait() to INR? bit 0"
        mode = acquisition.resume(osc, previous)
        time.sleep(0.5)
        assert value_of(osc.query("TRMD?")) == mode
        assert acquisition.state(osc).lower() != "stop", "TRMD did not resume acquisition"
    finally:
        trigger.apply(osc, mode=previous if previous in ("AUTO", "NORM") else "AUTO")
```

- [ ] **Step 2: Verificar que se omiten sin equipo**

Run: `.venv/bin/python -m pytest -q`
Expected: `253 passed, 7 skipped` (sin `OSC_HW`).

- [ ] **Step 3: Escribir la evaluación**

`evaluation/siglent_eval.xml`:

```xml
<evaluation>
   <!-- Setup: SDS1104X-E on USB; C1 probe (x10 setting) on the CAL output;
        the generator output (AWG) wired to C2 with a BNC cable. -->
   <qa_pair>
      <question>What is the model name of the connected oscilloscope?</question>
      <answer>SDS1104X-E</answer>
   </qa_pair>
   <qa_pair>
      <question>What firmware version is the oscilloscope running?</question>
      <answer>8.1.6.1.37R2</answer>
   </qa_pair>
   <qa_pair>
      <question>What is the frequency of the signal on channel 1, in hertz, rounded to the nearest integer?</question>
      <answer>1000</answer>
   </qa_pair>
   <qa_pair>
      <question>What is the duty cycle of the signal on channel 1, in percent, rounded to the nearest integer?</question>
      <answer>50</answer>
   </qa_pair>
   <qa_pair>
      <question>What is the period of the signal on channel 1, in milliseconds, rounded to one decimal place?</question>
      <answer>1.0</answer>
   </qa_pair>
   <qa_pair>
      <question>Turn channels 1 and 2 on and channels 3 and 4 off. How many channels are enabled afterwards?</question>
      <answer>2</answer>
   </qa_pair>
   <qa_pair>
      <question>Set the horizontal scale to 500 microseconds per division. What time per division, in seconds, does the scope report afterwards?</question>
      <answer>0.0005</answer>
   </qa_pair>
   <qa_pair>
      <question>Make the waveform generator output a 5 kHz square wave of 2 Vpp and measure the frequency on channel 2. What is it in kilohertz, rounded to the nearest integer?</question>
      <answer>5</answer>
   </qa_pair>
   <qa_pair>
      <question>Set the generator to a 2 kHz sine and switch its output off. What frequency, in hertz, does the generator report?</question>
      <answer>2000</answer>
   </qa_pair>
   <qa_pair>
      <question>Capture channel 1 and count the rising edges in the returned points between time 0 and 3 ms. How many are there?</question>
      <answer>3</answer>
   </qa_pair>
</evaluation>
```

- [ ] **Step 4: Commit**

```bash
git add tests/hw evaluation/siglent_eval.xml
git commit -m "Add hardware smoke tests and MCP evaluation set"
```

- [ ] **Step 5: Ejecución con el equipo (la hace el usuario)**

Con el SDS1104X-E conectado y la sonda de C1 en la salida CAL:

Run: `OSC_HW=1 .venv/bin/python -m pytest tests/hw -v -s`
Expected: 7 passed. Si falla alguno, su mensaje indica el cambio:
- `test_capture_and_sparsing` falla porque se ignora `WFSU SP` → documentar en README que la memoria debe ser ≤ `OSC_MAX_SAMPLES` (el código ya rechaza la captura).
- `test_capture_and_sparsing` falla por el intervalo → quitar el factor `* max(sparsing, 1)` en `parse_wavedesc` y ajustar `test_get_waveform_raw_with_sparsing_scales_interval_and_resets_wfsu`.
- `test_single_wait_and_resume` falla en `triggered` → cambiar `acquisition.state` para leer el bit 0 de `INR?`.
- `test_screen_dump_format` falla → el `bpp` impreso dice qué formato soportar en `imaging.py`.

---
