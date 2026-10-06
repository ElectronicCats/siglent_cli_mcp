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
