"""Test doubles for the oscilloscope, so no hardware is needed."""

from __future__ import annotations

import re
import struct
from contextlib import contextmanager
from dataclasses import replace

from click.testing import CliRunner

from osc_cli.device import OscError, parse_float, parse_wavedesc, waveform_dict

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


def run_cli(monkeypatch, fake, *args):
    """Invoke the `osc` CLI with `fake` in place of the real device."""
    from osc_cli import cli as cli_module

    monkeypatch.setattr(cli_module, "get_device", lambda *a, **k: fake)
    return CliRunner().invoke(cli_module.cli, list(args), catch_exceptions=False)


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
