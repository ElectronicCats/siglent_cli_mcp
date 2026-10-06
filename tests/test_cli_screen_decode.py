import json

import pytest

from tests.bmp_util import make_bmp
from tests.fakes import FakeOscilloscope, codes_from_volts, make_wavedesc_block, run_cli
from tests.test_decoders import DT, uart_wave

MSG = b"Hola"


def uart_fake():
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(codes_from_volts(uart_wave(MSG, 9600), 1.0), vdiv=1.0, interval=DT)
    return fake


def test_screen_capture(monkeypatch, tmp_path):
    fake = FakeOscilloscope()
    bmp = make_bmp([[(1, 2, 3)] * 4] * 2)
    fake.raw["SCDP"] = bmp
    out = tmp_path / "s.bmp"
    result = run_cli(monkeypatch, fake, "screen", "capture", "-o", str(out))
    assert result.output == f"Screen saved to {out} ({len(bmp)} bytes, BMP).\n"
    assert out.read_bytes() == bmp


CONFIG_CASES = [
    (["decode", "uart", "--rx", "C2", "--baud", "9600"],
     ["TRSE SERIAL", "TRIG_UART:RX C2", "TRIG_UART:BAUD 9600", "TRIG_UART:PARITY NONE",
      "TRIG_UART:STOP 1.0", "TRIG_UART:POLARITY HIGH"],
     "UART decode: RX=C2 baud=9600 parity=NONE stop=1.0\n"),
    (["decode", "i2c"], ["TRSE SERIAL", "TRIG_IIC:SCL C1", "TRIG_IIC:SDA C2"],
     "I2C decode: SCL=C1 SDA=C2\n"),
    (["decode", "spi"], ["TRSE SERIAL", "TRIG_SPI:CLK C1", "TRIG_SPI:MISO C2", "TRIG_SPI:MOSI C3",
                         "TRIG_SPI:CS C4"],
     "SPI decode: CLK=C1 MISO=C2 MOSI=C3 CS=C4\n"),
]


@pytest.mark.parametrize("args,writes,output", CONFIG_CASES)
def test_decode_trigger_config(monkeypatch, args, writes, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.output == output
    assert fake.writes == writes


def test_uart_bytes_live_json(monkeypatch):
    fake = uart_fake()
    result = run_cli(monkeypatch, fake, "decode", "uart-bytes", "--baud", "9600", "--json")
    frames = json.loads(result.output)
    assert bytes(f["value"] for f in frames) == MSG
    assert fake.writes[0] == "STOP"


def test_uart_bytes_from_file_text(monkeypatch, tmp_path):
    path = tmp_path / "rx.csv"
    wave = uart_wave(MSG, 9600)
    path.write_text("index,voltage,time\n" + "".join(f"{i},{v},{i * DT}\n" for i, v in enumerate(wave)))
    result = run_cli(monkeypatch, FakeOscilloscope(), "decode", "uart-bytes", "--file", str(path), "--baud", "9600")
    assert result.output.endswith("\n4 bytes: Hola\n")
    assert result.output.splitlines()[0].split()[2:] == ["0x48", "H"]


def test_csv_with_one_sample_is_rejected(monkeypatch, tmp_path):
    path = tmp_path / "short.csv"
    path.write_text("index,voltage,time\n0,0.0,0.0\n")
    from click.testing import CliRunner

    from osc_cli import cli as cli_module
    result = CliRunner().invoke(cli_module.cli, ["decode", "uart-bytes", "--file", str(path)])
    assert result.exit_code != 0
    assert "not enough samples" in result.output


def test_spi_bytes_needs_a_data_line(monkeypatch):
    from click.testing import CliRunner

    from osc_cli import cli as cli_module
    fake = uart_fake()
    monkeypatch.setattr(cli_module, "get_device", lambda *a, **k: fake)
    result = CliRunner().invoke(cli_module.cli, ["decode", "spi-bytes"])
    assert "Give at least one of --mosi / --miso." in result.output


def test_i2c_bytes_live(monkeypatch):
    from tests.test_decoders import i2c_wave
    scl, sda = i2c_wave([(0x50, False, [0xAB])])
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(codes_from_volts(scl, 1.0), vdiv=1.0, interval=DT)
    fake.blocks["C2"] = make_wavedesc_block(codes_from_volts(sda, 1.0), vdiv=1.0, interval=DT)
    result = run_cli(monkeypatch, fake, "decode", "i2c-bytes", "--json")
    txns = json.loads(result.output)
    assert txns[0]["address"] == 0x50 and txns[0]["data"] == [0xAB]
