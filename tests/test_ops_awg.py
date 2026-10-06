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
