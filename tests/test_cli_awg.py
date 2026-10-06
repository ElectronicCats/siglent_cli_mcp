import pytest

from tests.fakes import FakeOscilloscope, run_cli

R = FakeOscilloscope().responses

CASES = [
    (["awg", "status"], [("q", "C1:OUTP?"), ("q", "C1:BSWV?"), ("q", "C1:MDWV?")],
     f"Output : {R['C1:OUTP?']}\nWave   : {R['C1:BSWV?']}\nMod    : {R['C1:MDWV?']}\n"),
    (["awg", "on"], [("w", "C1:OUTP ON")], "AWG output enabled.\n"),
    (["awg", "off"], [("w", "C1:OUTP OFF")], "AWG output disabled.\n"),
    (["awg", "wave", "SQUARE"], [("w", "C1:BSWV WVTP,SQUARE")], "Waveform type = SQUARE\n"),
    (["awg", "freq", "5000"], [("w", "C1:BSWV FRQ,5000.0")], "Frequency = 5000.0 Hz\n"),
    (["awg", "amp", "2"], [("w", "C1:BSWV AMP,2.0")], "Amplitude = 2.0 Vpp\n"),
    (["awg", "duty", "25"], [("w", "C1:BSWV DUTY,25.0")], "Duty cycle = 25.0%\n"),
    (["awg", "load", "50"], [("w", "C1:OUTP LOAD,50")], "Load = 50\n"),
    (["awg", "set", "--wave", "SQUARE", "--freq", "5000", "--on"],
     [("w", "C1:BSWV WVTP,SQUARE"), ("w", "C1:BSWV FRQ,5000.0"), ("w", "C1:OUTP ON"), ("q", "C1:BSWV?")],
     f"AWG configured.\n{R['C1:BSWV?']}\n"),
    (["awg", "arb"], [("q", "C1:ARWV?")], f"{R['C1:ARWV?']}\n"),
    (["awg", "arb", "StairUp"], [("w", "C1:ARWV INDEX,StairUp"), ("w", "C1:BSWV WVTP,ARB")],
     "Arbitrary waveform = StairUp\n"),
    (["awg", "burst", "--on", "--cycles", "10"],
     [("w", "C1:BTWV STATE,ON"), ("w", "C1:BTWV NCYC,10"), ("q", "C1:BTWV?")], f"{R['C1:BTWV?']}\n"),
    (["awg", "sweep", "--start", "100", "--stop", "1000"],
     [("w", "C1:SWWV START,100.0"), ("w", "C1:SWWV STOP,1000.0"), ("q", "C1:SWWV?")], f"{R['C1:SWWV?']}\n"),
    (["awg", "modulate", "--on"], [("w", "C1:MDWV STATE,ON"), ("q", "C1:MDWV?")], f"{R['C1:MDWV?']}\n"),
    (["awg", "sync", "ON"], [("w", "C1:SYNC ON")], "Sync output = ON\n"),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_awg_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log
