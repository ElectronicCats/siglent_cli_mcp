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
