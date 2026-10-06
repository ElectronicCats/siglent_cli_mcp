import os

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from osc_cli.device import OscError, OscNotFoundError, OscTransportError
from siglent_mcp.errors import tool_errors
from siglent_mcp.session import ScopeBusy
from siglent_mcp.storage import Storage, default_root


def test_auto_named_output_goes_under_kind(tmp_path):
    storage = Storage(root=tmp_path)
    path = storage.output_path("waveforms", "_C1.csv")
    assert path.parent == tmp_path / "waveforms"
    assert path.name.endswith("_C1.csv")


def test_requested_output_must_stay_inside_root(tmp_path):
    storage = Storage(root=tmp_path / "data")
    assert storage.output_path("screens", ".png", "shots/a.png") == tmp_path / "data" / "shots" / "a.png"
    with pytest.raises(ValueError, match="inside"):
        storage.output_path("screens", ".png", "../evil.png")
    with pytest.raises(ValueError, match="inside"):
        storage.output_path("screens", ".png", str(tmp_path / "elsewhere.png"))


def test_prune_keeps_newest(tmp_path):
    storage = Storage(root=tmp_path, keep=2)
    folder = tmp_path / "decodes"
    folder.mkdir()
    for i in range(4):
        f = folder / f"{i}.json"
        f.write_text("{}")
        os.utime(f, (1000 + i, 1000 + i))
    storage.prune("decodes")
    assert sorted(p.name for p in folder.iterdir()) == ["2.json", "3.json"]
    storage.prune("missing")  # no error


def test_input_file(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("index,voltage,time\n")
    assert Storage.input_file(str(f)) == f
    with pytest.raises(ValueError, match="not found"):
        Storage.input_file(str(tmp_path / "nope.csv"))
    with pytest.raises(ValueError, match="not found"):
        Storage.input_file(str(tmp_path))


def test_root_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("OSC_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("OSC_KEEP_FILES", "7")
    storage = Storage()
    assert storage.root == tmp_path / "d" and storage.keep == 7
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert default_root() == tmp_path / "xdg" / "siglent-mcp"


def raising(exc):
    @tool_errors
    def tool():
        raise exc

    return tool


def retried(exc):
    exc.retried = True
    return exc


@pytest.mark.parametrize("exc,fragment", [
    (ScopeBusy("x"), "busy"),
    (OscNotFoundError("No USBTMC device found."), "udev rule"),
    (retried(OscTransportError("timeout")), "power-cycle"),
    (OscTransportError("pipe"), "may or may not have run"),
    (OscError("bad header"), "bad header"),
    (ValueError("samples per bit"), "samples per bit"),
    (FileNotFoundError("x.csv"), "x.csv"),
])
def test_tool_errors_maps_exceptions(exc, fragment):
    with pytest.raises(ToolError, match=fragment):
        raising(exc)()


def test_tool_errors_passes_results_and_tool_errors_through():
    @tool_errors
    def ok(x):
        """Doc."""
        return x * 2

    assert ok(2) == 4 and ok.__doc__ == "Doc."
    with pytest.raises(ToolError, match="as is"):
        raising(ToolError("as is"))()
