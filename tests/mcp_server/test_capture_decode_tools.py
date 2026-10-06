import json
from pathlib import Path

import pytest
from mcp import Client

from siglent_mcp.server import create_server
from siglent_mcp.session import Session
from tests.bmp_util import make_bmp, read_png
from tests.fakes import codes_from_volts, make_wavedesc_block
from tests.mcp_server.conftest import call
from tests.test_decoders import DT, i2c_wave, spi_wave, uart_wave

pytestmark = pytest.mark.anyio


async def test_uart_description_is_accurate(client):
    """Verify UART tool description has correct frame structure."""
    tools = await client.list_tools()
    uart_tool = next(t for t in tools.tools if t.name == "siglent_decode_uart")
    assert "{time, value, ascii, errors}" in uart_tool.description
    assert "time_s" not in uart_tool.description


def put_wave(fake, source, volts, vdiv=1.0):
    fake.blocks[source] = make_wavedesc_block(codes_from_volts(volts, vdiv), vdiv=vdiv, interval=DT)


async def test_capture_screen_returns_png(client, fake):
    fake.raw["SCDP"] = make_bmp([[(255, 0, 0)] * 3] * 2)
    result = await call(client, "siglent_capture_screen")
    assert [c.type for c in result.content] == ["image"]
    assert result.content[0].mime_type == "image/png"


async def test_capture_screen_saves_inside_data_dir(client, fake, storage):
    fake.raw["SCDP"] = make_bmp([[(0, 255, 0)]])
    result = await call(client, "siglent_capture_screen", save_path="shot.png")
    assert result.content[1].text == f"Saved to {storage.root / 'shot.png'}"
    assert read_png((storage.root / "shot.png").read_bytes())[2] == [[(0, 255, 0)]]
    bad = await client.call_tool("siglent_capture_screen", {"save_path": "../x.png"})
    assert bad.is_error and "inside" in bad.content[0].text


async def test_capture_waveform_two_channels(client, fake):
    put_wave(fake, "C1", [0.0, 1.0] * 50)
    put_wave(fake, "C2", [0.5] * 100)
    r = (await call(client, "siglent_capture_waveform", sources=["C1", "C2"], max_points=10)).structured_content
    assert fake.writes[1] == "STOP"
    assert r["acquisition_stopped"] is True and "run" in r["note"]
    c1 = r["sources"]["C1"]
    assert c1["n"] == 100 and c1["vpp"] == pytest.approx(1.0) and len(c1["points"]) <= 10
    assert Path(c1["csv_path"]).read_text().startswith("index,voltage,time\n")


async def test_capture_waveform_dedupes_sources(client, fake):
    put_wave(fake, "C1", [0.0] * 10)
    r = (await call(client, "siglent_capture_waveform", sources=["C1", "C1"], save_csv=False)).structured_content
    assert list(r["sources"]) == ["C1"]
    assert "csv_path" not in r["sources"]["C1"]
    assert r["acquisition_stopped"] is False


async def test_capture_waveform_refuses_huge_memory(fake, storage):
    put_wave(fake, "C1", [0.0] * 5000)
    server = create_server(session=Session(lambda: fake), storage=storage, max_samples=1000)
    async with Client(server) as c:
        result = await c.call_tool("siglent_capture_waveform", {"sources": ["C1"]})
    assert result.is_error and "OSC_MAX_SAMPLES" in result.content[0].text


async def test_decode_uart_live_with_pagination(client, fake):
    put_wave(fake, "C1", uart_wave(b"Hola", 9600))
    r = (await call(client, "siglent_decode_uart", baud=9600, limit=2)).structured_content
    assert r["text"] == "Ho" and r["total"] == 4
    assert r["has_more"] is True and r["next_offset"] == 2
    assert [f["value"] for f in json.loads(Path(r["json_path"]).read_text())] == list(b"Hola")
    r2 = (await call(client, "siglent_decode_uart", baud=9600, limit=2, offset=2, freeze=False)).structured_content
    assert r2["text"] == "la" and r2["has_more"] is False


async def test_decode_uart_from_capture_csv_round_trip(client, fake):
    put_wave(fake, "C1", uart_wave(b"OK!", 9600))
    cap = (await call(client, "siglent_capture_waveform", sources=["C1"])).structured_content
    fake.blocks.clear()  # offline decode must not touch the scope
    r = (await call(client, "siglent_decode_uart", baud=9600, rx_csv=cap["sources"]["C1"]["csv_path"])).structured_content
    assert r["text"] == "OK!" and r["acquisition_stopped"] is False


async def test_decode_uart_nothing_found_has_diagnostics(client, fake):
    put_wave(fake, "C1", [3.3] * 1000)
    r = (await call(client, "siglent_decode_uart", baud=9600)).structured_content
    assert r["total"] == 0 and "barely moves" in r["diagnostics"]["hint"]


async def test_decode_i2c_live(client, fake):
    scl, sda = i2c_wave([(0x50, False, [0x12])])
    put_wave(fake, "C1", scl)
    put_wave(fake, "C2", sda)
    r = (await call(client, "siglent_decode_i2c")).structured_content
    assert r["transactions"][0]["address"] == 0x50 and r["transactions"][0]["data"] == [0x12]


async def test_decode_i2c_offline_needs_both_csvs(client, tmp_path):
    f = tmp_path / "scl.csv"
    f.write_text("index,voltage,time\n0,0,0\n1,0,1e-6\n")
    r = await client.call_tool("siglent_decode_i2c", {"scl_csv": str(f)})
    assert r.is_error and "sda_csv" in r.content[0].text


async def test_decode_spi_live(client, fake):
    clk, mosi, cs = spi_wave([0xA5, 0x3C])
    put_wave(fake, "C1", clk)
    put_wave(fake, "C2", mosi)
    put_wave(fake, "C4", cs)
    r = (await call(client, "siglent_decode_spi", mosi="C2", cs="C4")).structured_content
    assert [f["mosi"] for f in r["frames"]] == [[0xA5], [0x3C]]
    assert all(f["miso"] == [] for f in r["frames"])


async def test_decode_spi_needs_a_data_line(client, fake):
    put_wave(fake, "C1", [0.0] * 10)
    r = await client.call_tool("siglent_decode_spi", {})
    assert r.is_error and "mosi" in r.content[0].text
