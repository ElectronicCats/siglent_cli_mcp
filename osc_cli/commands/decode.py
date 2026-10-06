"""Serial decode trigger commands (LeCroy dialect).

The SDS1104X-E exposes serial decode through trigger commands:
TRIG_UART:..., TRIG_IIC:... (I2C), TRIG_SPI:.... The command strings and the
capture/CSV helpers live in osc_cli.ops.decode.
"""

from __future__ import annotations

import json

import click

from .. import decoders
from ..cli import osc
from ..ops import decode as ops_decode

CH = ["C1", "C2", "C3", "C4"]


@click.group(name="decode")
def decode_group():
    """Serial bus decode (UART, I2C, SPI)."""


@decode_group.command("uart")
@click.option("--rx", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--tx", type=click.Choice(CH), default=None, help="TX source (optional).")
@click.option("--baud", type=int, default=115200, show_default=True)
@click.option("--parity", type=click.Choice(["NONE", "EVEN", "ODD"]), default="NONE", show_default=True)
@click.option("--stop", type=float, default=1.0, show_default=True)
@click.option("--polarity", type=click.Choice(["HIGH", "LOW"]), default="HIGH", show_default=True)
@click.pass_context
def uart(ctx, rx, tx, baud, parity, stop, polarity):
    """Configure UART decode trigger."""
    ops_decode.configure_uart_trigger(osc(ctx), rx, tx, baud, parity, stop, polarity)
    click.echo(f"UART decode: RX={rx} baud={baud} parity={parity} stop={stop}")


@decode_group.command("i2c")
@click.option("--scl", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--sda", type=click.Choice(CH), default="C2", show_default=True)
@click.pass_context
def i2c(ctx, scl, sda):
    """Configure I2C decode trigger."""
    ops_decode.configure_i2c_trigger(osc(ctx), scl, sda)
    click.echo(f"I2C decode: SCL={scl} SDA={sda}")


@decode_group.command("spi")
@click.option("--clk", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--miso", type=click.Choice(CH), default="C2", show_default=True)
@click.option("--mosi", type=click.Choice(CH), default="C3", show_default=True)
@click.option("--cs", type=click.Choice(CH), default="C4", show_default=True)
@click.pass_context
def spi(ctx, clk, miso, mosi, cs):
    """Configure SPI decode trigger."""
    ops_decode.configure_spi_trigger(osc(ctx), clk, miso, mosi, cs)
    click.echo(f"SPI decode: CLK={clk} MISO={miso} MOSI={mosi} CS={cs}")


@decode_group.command("status")
@click.pass_context
def status(ctx):
    """Show current serial decode configuration."""
    o = osc(ctx)
    click.echo(f"Trigger setup: {o.query('TRSE?')}")
    for c in ["BAUD", "PARITY", "STOP", "POLARITY", "RX", "TX", "BIT"]:
        try:
            click.echo(f"UART {c:8s}: {o.query(f'TRIG_UART:{c}?')}")
        except Exception:  # noqa: BLE001
            pass


# ---- byte extraction (software decode of captured waveforms) ---------------
#
# The scope's built-in decoder cannot be read back over USBTMC, so these
# commands capture the channels and decode the samples on the host. Use
# --file to decode a CSV saved by `osc waveform capture` without a scope.


def _load(ctx, source, path, stop):
    """Return (samples, dt) from a CSV file or a live capture of `source`."""
    if path:
        try:
            return ops_decode.load_csv(path)
        except ValueError as e:
            raise click.ClickException(str(e))
    # stop=True freezes the acquisition so every channel is the same capture.
    lines, dt, _ = ops_decode.capture_lines(osc(ctx), [source], stop, None)
    return lines[source], dt


def _fmt_options(f):
    for opt in reversed([
        click.option("--json", "as_json", is_flag=True, help="Output JSON."),
        click.option("--no-stop", is_flag=True, help="Do not STOP the acquisition before reading."),
        click.option("--threshold", type=float, default=None, help="Logic threshold in volts (default: midpoint)."),
    ]):
        f = opt(f)
    return f


@decode_group.command("uart-bytes")
@click.option("--rx", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--file", "path", type=click.Path(exists=True), help="Decode a CSV from `waveform capture` instead.")
@click.option("--baud", type=int, default=115200, show_default=True)
@click.option("--bits", type=click.IntRange(5, 9), default=8, show_default=True)
@click.option("--parity", type=click.Choice(["NONE", "EVEN", "ODD"]), default="NONE", show_default=True)
@click.option("--stop", "stop_bits", type=float, default=1.0, show_default=True)
@click.option("--polarity", type=click.Choice(["HIGH", "LOW"]), default="HIGH", show_default=True, help="Idle level.")
@click.option("--msb-first", is_flag=True, help="MSB first (default: LSB first).")
@_fmt_options
@click.pass_context
def uart_bytes(ctx, rx, path, baud, bits, parity, stop_bits, polarity, msb_first, as_json, no_stop, threshold):
    """Capture a channel and extract the UART bytes."""
    samples, dt = _load(ctx, rx, path, not no_stop)
    try:
        frames = decoders.uart_decode(
            samples, dt, baud, bits, parity, stop_bits, polarity, not msb_first, threshold
        )
    except ValueError as e:
        raise click.ClickException(str(e))
    if as_json:
        click.echo(json.dumps(frames))
        return
    for fr in frames:
        err = f"  ! {','.join(fr['errors'])}" if fr["errors"] else ""
        ch = chr(fr["value"]) if 32 <= fr["value"] < 127 else "."
        click.echo(f"{fr['time']*1e3:12.4f} ms  0x{fr['value']:02X}  {ch}{err}")
    text = "".join(chr(f["value"]) if 32 <= f["value"] < 127 else "." for f in frames)
    click.echo(f"\n{len(frames)} bytes: {text}")


@decode_group.command("i2c-bytes")
@click.option("--scl", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--sda", type=click.Choice(CH), default="C2", show_default=True)
@click.option("--scl-file", type=click.Path(exists=True), help="CSV for SCL (offline).")
@click.option("--sda-file", type=click.Path(exists=True), help="CSV for SDA (offline).")
@_fmt_options
@click.pass_context
def i2c_bytes(ctx, scl, sda, scl_file, sda_file, as_json, no_stop, threshold):
    """Capture SCL/SDA and extract I2C transactions."""
    c, dt = _load(ctx, scl, scl_file, not no_stop)
    d, _ = _load(ctx, sda, sda_file, False)
    txns = decoders.i2c_decode(c, d, dt, threshold, threshold)
    if as_json:
        click.echo(json.dumps(txns))
        return
    for t in txns:
        rw = "R" if t["read"] else "W"
        addr = "?" if t["address"] is None else f"0x{t['address']:02X}"
        data = " ".join(f"{b:02X}" for b in t["data"])
        nack = " NACK" if t["acks"] and not all(t["acks"]) else ""
        rs = "Sr" if t["repeated_start"] else "S"
        click.echo(f"{t['time']*1e3:12.4f} ms  {rs} {addr} {rw}  {data}{nack}")
    click.echo(f"\n{len(txns)} transactions")


@decode_group.command("spi-bytes")
@click.option("--clk", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--mosi", type=click.Choice(CH), default=None)
@click.option("--miso", type=click.Choice(CH), default=None)
@click.option("--cs", type=click.Choice(CH), default=None, help="Chip select (active low).")
@click.option("--clk-file", type=click.Path(exists=True), help="CSV for CLK (offline).")
@click.option("--mosi-file", type=click.Path(exists=True))
@click.option("--miso-file", type=click.Path(exists=True))
@click.option("--cs-file", type=click.Path(exists=True))
@click.option("--bits", type=click.IntRange(4, 32), default=8, show_default=True)
@click.option("--cpol", type=click.IntRange(0, 1), default=0, show_default=True)
@click.option("--cpha", type=click.IntRange(0, 1), default=0, show_default=True)
@click.option("--lsb-first", is_flag=True, help="LSB first (default: MSB first).")
@_fmt_options
@click.pass_context
def spi_bytes(ctx, clk, mosi, miso, cs, clk_file, mosi_file, miso_file, cs_file,
              bits, cpol, cpha, lsb_first, as_json, no_stop, threshold):
    """Capture the SPI lines and extract MOSI/MISO words."""
    k, dt = _load(ctx, clk, clk_file, not no_stop)

    def side(ch, f):
        return _load(ctx, ch, f, False)[0] if (ch or f) else None

    m, s, c = side(mosi, mosi_file), side(miso, miso_file), side(cs, cs_file)
    if m is None and s is None:
        raise click.ClickException("Give at least one of --mosi / --miso.")
    frames = decoders.spi_decode(k, m, s, c, dt, bits, cpol, cpha, not lsb_first, threshold)
    if as_json:
        click.echo(json.dumps(frames))
        return
    w = (bits + 3) // 4
    for fr in frames:
        click.echo(f"{fr['time']*1e3:12.4f} ms")
        if m is not None:
            click.echo("  MOSI: " + " ".join(f"{b:0{w}X}" for b in fr["mosi"]))
        if s is not None:
            click.echo("  MISO: " + " ".join(f"{b:0{w}X}" for b in fr["miso"]))
    click.echo(f"\n{len(frames)} frames")
