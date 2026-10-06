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
