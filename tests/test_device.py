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
