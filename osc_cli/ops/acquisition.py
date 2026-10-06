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
