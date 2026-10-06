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
