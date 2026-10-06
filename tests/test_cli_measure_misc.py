import pytest

from tests.fakes import FakeOscilloscope, run_cli

ALL_ITEMS = ["PKPK", "MAX", "MIN", "MEAN", "RMS", "PER", "FREQ", "DUTY", "RISE", "FALL"]


def pava(src, item):
    return FakeOscilloscope().responses[f"{src}:PAVA? {item}"]


CASES = [
    (["measure", "item", "-i", "FREQ", "-s", "C2"], [("q", "C2:PAVA? FREQ")], pava("C2", "FREQ") + "\n"),
    (["measure", "all"], [("q", f"C1:PAVA? {i}") for i in ALL_ITEMS],
     "".join(pava("C1", i) + "\n" for i in ALL_ITEMS)),
    (["measure", "vpp"], [("q", "C1:PAVA? PKPK")], pava("C1", "PKPK") + "\n"),
    (["measure", "period", "-s", "C3"], [("q", "C3:PAVA? PER")], pava("C3", "PER") + "\n"),
    (["math", "function"], [("q", "MATH:FUNC?")], "MATH:FUNC ADD\n"),
    (["math", "function", "FFT"], [("w", "MATH:FUNC FFT")], "Math function = FFT\n"),
    (["math", "scale", "2"], [("w", "MATH:SCALE 2.0")], "Math scale = 2.0\n"),
    (["display", "grid", "HALF"], [("w", "GRDS HALF")], "Grid = HALF\n"),
    (["display", "intensity", "60"], [("w", "INTS TRACE,60")], "Trace intensity = 60\n"),
    (["display", "menu"], [("q", "MENU?")], "MENU ON\n"),
    (["cursor", "mode", "TRACK"], [("w", "CRMS TRACK")], "Cursor mode = TRACK\n"),
    (["counter", "on"], [("w", "FCNT STATE,ON")], "Counter enabled.\n"),
    (["counter", "status"], [("q", "FCNT?")], "FCNT STATE,ON,FRQ,1.00000E+03Hz\n"),
    (["save", "setup", "/usb/a.xml"], [("w", 'STORE_SETUP FILE,"/usb/a.xml"')], "Setup saved to /usb/a.xml\n"),
    (["save", "recall-setup", "/usb/a.xml"], [("w", 'RECALL_SETUP FILE,"/usb/a.xml"')],
     "Setup recalled from /usb/a.xml\n"),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_measure_and_misc_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log
