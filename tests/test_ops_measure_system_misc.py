import pytest

from osc_cli.ops import measure, misc, system
from tests.fakes import FakeOscilloscope


def test_measure_default_items_with_units():
    result = measure.measure(FakeOscilloscope(), "C1")
    assert list(result) == list(measure.DEFAULT_ITEMS)
    assert result["FREQ"] == {"value": 1000.0, "unit": "Hz"}
    assert result["DUTY"] == {"value": 50.0, "unit": "%"}


def test_measure_invalid_reading_is_null_with_note():
    fake = FakeOscilloscope()
    fake.responses["C2:PAVA? FREQ"] = "C2:PAVA FREQ,****"
    entry = measure.measure(fake, "C2", ["FREQ"])["FREQ"]
    assert entry["value"] is None
    assert "v/div" in entry["note"]


def test_measure_rejects_unknown_item_and_source():
    with pytest.raises(ValueError, match="VOLTS"):
        measure.measure(FakeOscilloscope(), "C1", ["VOLTS"])
    with pytest.raises(ValueError, match="source"):
        measure.measure(FakeOscilloscope(), "C5")


def test_identify():
    assert system.identify(FakeOscilloscope()) == {
        "manufacturer": "SIGLENT", "model": "SDS1104X-E", "serial": "SDSMMEBQ3R1234",
        "firmware": "8.1.6.1.37R2", "raw": "SIGLENT,SDS1104X-E,SDSMMEBQ3R1234,8.1.6.1.37R2",
    }


def test_last_error():
    assert system.last_error(FakeOscilloscope()) == {"code": 0, "message": "No error"}
    fake = FakeOscilloscope()
    fake.responses["SYSTem:ERRor?"] = "garbled"
    assert system.last_error(fake) == {"code": None, "message": "garbled"}


def test_selftest_and_calibrate_are_not_retried():
    fake = FakeOscilloscope()
    assert system.selftest(fake) == "*TST 0"
    assert fake.last_retries == 0
    assert system.calibrate(fake) == "*CAL 0"
    assert fake.last_retries == 0


def test_raw_command_query_and_write():
    fake = FakeOscilloscope()
    assert system.raw_command(fake, "TDIV?", True) == "TDIV 1.00E-03S"
    assert system.raw_command(fake, "TDIV 1E-3", False) is None
    assert fake.writes == ["TDIV 1E-3"]


def test_math_read_and_apply():
    fake = FakeOscilloscope()
    state = misc.apply_math(fake, function="FFT", scale=2.0)
    assert fake.writes == ["MATH:FUNC FFT", "MATH:SCALE 2.0"]
    assert state == {"function": "ADD", "offset": 0.0, "scale": 1.0}  # fake read-back


def test_display_read_and_apply():
    fake = FakeOscilloscope()
    state = misc.apply_display(fake, menu=False, intensity=60, cursor_mode="TRACK")
    assert fake.writes == ["INTS TRACE,60", "MENU OFF", "CRMS TRACK"]
    assert state == {"grid": "FULL", "intensity": 60, "menu": True, "cursor_mode": "OFF"}


def test_display_rejects_bad_grid():
    with pytest.raises(ValueError, match="grid"):
        misc.apply_display(FakeOscilloscope(), grid="DOTS")


def test_counter():
    fake = FakeOscilloscope()
    misc.set_counter(fake, True)
    assert fake.writes == ["FCNT STATE,ON"]
    assert misc.read_counter(fake) == {
        "enabled": True, "frequency_hz": 1000.0, "raw": "FCNT STATE,ON,FRQ,1.00000E+03Hz",
    }


def test_setup_paths_are_quoted_and_validated():
    fake = FakeOscilloscope()
    misc.save_setup(fake, "/usb/a.xml")
    misc.recall_setup(fake, "/usb/a.xml")
    assert fake.writes == ['STORE_SETUP FILE,"/usb/a.xml"', 'RECALL_SETUP FILE,"/usb/a.xml"']
    with pytest.raises(ValueError, match="quotes"):
        misc.save_setup(fake, 'a"b')
