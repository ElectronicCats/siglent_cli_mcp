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
