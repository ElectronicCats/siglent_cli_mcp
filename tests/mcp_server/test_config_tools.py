import pytest

from osc_cli.device import OscTransportError
from tests.mcp_server.conftest import call

pytestmark = pytest.mark.anyio


async def test_set_channel_writes_only_given_fields(client, fake):
    state = (await call(client, "siglent_set_channel", channel=2, vdiv=0.2, coupling="A1M")).structured_content
    assert fake.writes[-2:] == ["C2:CPL A1M", "C2:VDIV 0.2"]
    assert state["channel"] == 2


async def test_set_channel_validates(client):
    result = await client.call_tool("siglent_set_channel", {"channel": 1, "coupling": "AC"})
    assert result.is_error


async def test_set_timebase(client, fake):
    await call(client, "siglent_set_timebase", memory="70K", tdiv=0.0005)
    assert fake.writes[-2:] == ["MSIZ 70K", "TDIV 0.0005"]


async def test_run_returns_to_last_continuous_mode(client, fake):
    fake.responses["TRMD?"] = ["TRMD NORM", "TRMD STOP"]
    await call(client, "siglent_set_trigger", mode="NORM")
    r = (await call(client, "siglent_control_acquisition", action="run")).structured_content
    assert r["trigger_mode"] == "NORM"
    assert fake.writes[-1] == "TRMD NORM"


async def test_single_suggests_waiting(client, fake):
    r = (await call(client, "siglent_control_acquisition", action="single")).structured_content
    assert fake.writes[-1] == "TRMD SINGLE"
    assert "siglent_wait_for_acquisition" in r["note"]


async def test_single_is_not_retried_after_transport_error(client, fake):
    fake.fail_writes["TRMD SINGLE"] = OscTransportError("pipe")
    result = await client.call_tool("siglent_control_acquisition", {"action": "single"})
    assert result.is_error
    assert "may or may not have run" in result.content[0].text
    assert fake.writes.count("TRMD SINGLE") == 1


async def test_force_and_stop(client, fake):
    await call(client, "siglent_control_acquisition", action="force")
    await call(client, "siglent_control_acquisition", action="stop")
    assert fake.writes[-2:] == ["*TRG", "STOP"]


async def test_serial_trigger_tools(client, fake):
    r = (await call(client, "siglent_configure_uart_trigger", rx="C3", baud=9600)).structured_content
    assert r["protocol"] == "uart" and r["settings"]["baud"] == 9600
    assert "TRIG_UART:RX C3" in fake.writes
    await call(client, "siglent_configure_i2c_trigger", scl="C2", sda="C3")
    await call(client, "siglent_configure_spi_trigger")
    assert "TRIG_IIC:SCL C2" in fake.writes and "TRIG_SPI:CS C4" in fake.writes


async def test_math_display_counter_setup(client, fake):
    await call(client, "siglent_set_math", function="FFT")
    await call(client, "siglent_set_display", menu=False)
    c = (await call(client, "siglent_set_counter", enabled=True)).structured_content
    s = (await call(client, "siglent_save_setup", path="/usb/a.xml")).structured_content
    assert ["MATH:FUNC FFT", "MENU OFF", "FCNT STATE,ON", 'STORE_SETUP FILE,"/usb/a.xml"'] == [
        w for w in fake.writes if w != "CHDR SHORT"
    ]
    assert c["frequency_hz"] == 1000.0 and s == {"action": "saved", "path": "/usb/a.xml"}


async def test_save_setup_rejects_quotes(client):
    result = await client.call_tool("siglent_save_setup", {"path": 'a"b'})
    assert result.is_error and "quotes" in result.content[0].text


async def test_save_setup_rejects_command_injection(client, fake):
    result = await client.call_tool("siglent_save_setup", {"path": "x\nTRMD STOP"})
    assert result.is_error
    assert not any("TRMD STOP" in w for w in fake.writes)
