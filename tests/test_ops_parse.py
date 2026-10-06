import pytest

from osc_cli.ops._parse import pairs, split_number, to_bool, to_float, value_of


@pytest.mark.parametrize("response,value", [
    ("C1:VDIV 5.00E-01V", "5.00E-01V"),
    ("5.00E-01V", "5.00E-01V"),
    ("*IDN SIGLENT,SDS1104X-E,X,1", "SIGLENT,SDS1104X-E,X,1"),
    ("SAST Trig'd", "Trig'd"),
    ('0,"No error"', '0,"No error"'),
    ("OFF\n", "OFF"),
    ("C1:PAVA FREQ,****", "FREQ,****"),
])
def test_value_of(response, value):
    assert value_of(response) == value


@pytest.mark.parametrize("text,expected", [
    ("1.00E+03Hz", (1000.0, "Hz")),
    ("-2.5V", (-2.5, "V")),
    ("5.00E+01%", (50.0, "%")),
    (".5", (0.5, "")),
    ("****", (None, "")),
    ("", (None, "")),
])
def test_split_number(text, expected):
    assert split_number(text) == expected


def test_to_float_and_bool():
    assert to_float("1.40E+06pts") == 1.4e6
    assert to_float("") is None
    assert to_bool("ON") and to_bool(" on ") and not to_bool("OFF")


def test_pairs_ignores_trailing_token():
    assert pairs("WVTP,SINE,FRQ,1000HZ,ODD") == {"WVTP": "SINE", "FRQ": "1000HZ"}
    assert pairs("") == {}
