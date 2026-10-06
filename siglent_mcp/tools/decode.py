"""UART / I2C / SPI byte extraction from captured (or saved) waveforms."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from osc_cli import decoders
from osc_cli.ops import decode

from ..errors import tool_errors
from ..models import I2cPage, SpiPage, UartPage
from .common import STOPPED_NOTE, WRITE, Deps, Source

Limit = Annotated[int, Field(ge=1, le=2000, description="Items per page.")]
Offset = Annotated[int, Field(ge=0, description="Index of the first item; use next_offset to page.")]
Threshold = Annotated[float | None, Field(description="Logic threshold in volts; default is the midpoint of the signal.")]
Freeze = Annotated[bool, Field(description="Stop the acquisition first so all lines come from one capture. Leaves the scope stopped.")]
CsvPath = Annotated[str | None, Field(description="Decode this CSV (from siglent_capture_waveform) instead of capturing.")]


def _acquire(deps: Deps, live: dict, offline: dict, required: tuple, freeze: bool):
    """Samples per bus line (role -> volts), dt, and whether the scope was stopped."""
    if any(offline.values()):
        chosen = {role: path for role, path in offline.items() if path}
        missing = [role for role in required if role not in chosen]
        if missing:
            raise ValueError("Offline decode is missing " + ", ".join(f"{r}_csv" for r in missing))
        lines, dt = {}, None
        for role, path in chosen.items():
            lines[role], line_dt = decode.load_csv(deps.storage.input_file(path))
            dt = dt or line_dt
        return lines, dt, False
    chosen = {role: src for role, src in live.items() if src}
    captured, dt, stopped = deps.session.run(
        decode.capture_lines, list(chosen.values()), freeze, deps.max_samples, retry=True,
    )
    return {role: captured[src] for role, src in chosen.items()}, dt, stopped


def _page(deps: Deps, kind: str, items: list, limit: int, offset: int, stopped: bool,
          diag_samples, threshold) -> dict:
    path = deps.storage.output_path("decodes", f"_{kind}.json")
    path.write_text(json.dumps(items))
    deps.storage.prune("decodes")
    page = decode.paginate(items, limit, offset)
    result = {key: page[key] for key in ("total", "count", "offset", "has_more", "next_offset")}
    result.update(json_path=str(path), acquisition_stopped=stopped, items=page["items"])
    if not items:
        result["diagnostics"] = decode.diagnose(diag_samples, threshold)
    if stopped:
        result["note"] = STOPPED_NOTE
    return result


def register(server: MCPServer, deps: Deps) -> None:

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_decode_uart(
        rx: Source = "C1",
        baud: Annotated[int, Field(ge=50, le=10_000_000)] = 115200,
        bits: Annotated[int, Field(ge=5, le=9)] = 8,
        parity: Literal["NONE", "EVEN", "ODD"] = "NONE",
        stop_bits: Annotated[float, Field(ge=1, le=2)] = 1.0,
        polarity: Literal["HIGH", "LOW"] = "HIGH",
        msb_first: bool = False,
        threshold: Threshold = None,
        freeze: Freeze = True,
        rx_csv: CsvPath = None,
        limit: Limit = 200,
        offset: Offset = 0,
    ) -> UartPage:
        """Extract UART bytes from a channel (decoded on the host from the captured samples).

        Returns a page of frames {time, value, ascii, errors} (time in seconds from
        the start of the capture) plus the page as text, and json_path with every frame.
        errors lists 'parity'/'framing' problems. When nothing decodes, diagnostics
        shows the levels seen and what to adjust. The capture must hold at least 3
        samples per bit (raise time/div resolution for high baud rates).
        """
        lines, dt, stopped = _acquire(deps, {"rx": rx}, {"rx": rx_csv}, ("rx",), freeze)
        frames = decode.with_ascii(decoders.uart_decode(
            lines["rx"], dt, baud, bits, parity, stop_bits, polarity, not msb_first, threshold,
        ))
        result = _page(deps, "uart", frames, limit, offset, stopped, lines["rx"], threshold)
        result["frames"] = result.pop("items")
        result["text"] = "".join(f["ascii"] for f in result["frames"])
        return result

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_decode_i2c(
        scl: Source = "C1",
        sda: Source = "C2",
        threshold: Threshold = None,
        freeze: Freeze = True,
        scl_csv: CsvPath = None,
        sda_csv: CsvPath = None,
        limit: Limit = 200,
        offset: Offset = 0,
    ) -> I2cPage:
        """Extract I2C transactions from the SCL/SDA channels (decoded on the host).

        Each transaction: {time, address (7-bit), read, data, acks, repeated_start};
        acks[0] is the address ACK, a False entry is a NACK.
        """
        lines, dt, stopped = _acquire(
            deps, {"scl": scl, "sda": sda}, {"scl": scl_csv, "sda": sda_csv}, ("scl", "sda"), freeze,
        )
        txns = decoders.i2c_decode(lines["scl"], lines["sda"], dt, threshold, threshold)
        result = _page(deps, "i2c", txns, limit, offset, stopped, lines["sda"], threshold)
        result["transactions"] = result.pop("items")
        return result

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_decode_spi(
        clk: Source = "C1",
        mosi: Source | None = None,
        miso: Source | None = None,
        cs: Annotated[Source | None, Field(description="Chip select (active low); without it the capture is one frame.")] = None,
        bits: Annotated[int, Field(ge=4, le=32)] = 8,
        cpol: Literal[0, 1] = 0,
        cpha: Literal[0, 1] = 0,
        lsb_first: bool = False,
        threshold: Threshold = None,
        freeze: Freeze = True,
        clk_csv: CsvPath = None,
        mosi_csv: CsvPath = None,
        miso_csv: CsvPath = None,
        cs_csv: CsvPath = None,
        limit: Limit = 200,
        offset: Offset = 0,
    ) -> SpiPage:
        """Extract SPI words from CLK and MOSI and/or MISO (decoded on the host).

        Give at least one of mosi/miso. Each frame (one per CS assertion):
        {time, mosi: [words], miso: [words]}.
        """
        live = {"clk": clk, "mosi": mosi, "miso": miso, "cs": cs}
        offline = {"clk": clk_csv, "mosi": mosi_csv, "miso": miso_csv, "cs": cs_csv}
        lines, dt, stopped = _acquire(deps, live, offline, ("clk",), freeze)
        if "mosi" not in lines and "miso" not in lines:
            raise ValueError("Give at least one of mosi / miso (or mosi_csv / miso_csv).")
        frames = decoders.spi_decode(
            lines["clk"], lines.get("mosi"), lines.get("miso"), lines.get("cs"),
            dt, bits, cpol, cpha, not lsb_first, threshold,
        )
        result = _page(deps, "spi", frames, limit, offset, stopped, lines["clk"], threshold)
        result["frames"] = result.pop("items")
        return result
