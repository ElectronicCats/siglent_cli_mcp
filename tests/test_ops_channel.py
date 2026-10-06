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
