"""Channel (vertical) control commands (LeCroy X-Stream dialect).

Channels are C1..C4. Commands: C1:VDIV, C1:OFST, C1:CPL (coupling), C1:BWL
(bandwidth), C1:ATTN (probe), C1:TRCP (trace coupling), C1:INVT (invert),
C1:UNIT, C1:SKEW, C1:TRA (trace on/off).
"""

from __future__ import annotations

import click

from ..cli import osc
from ..device import parse_float

CHANNELS = ("1", "2", "3", "4")


def _chan_option():
    return click.option(
        "--channel",
        "-c",
        type=click.Choice(CHANNELS),
        default="1",
        show_default=True,
        help="Channel number (1-4).",
    )


def _ch(channel: str) -> str:
    return f"C{channel}"


@click.group(name="channel")
def channel_group():
    """Vertical channel control (CH1..CH4)."""


@channel_group.command("list")
@click.pass_context
def channel_list(ctx):
    """Show the state of all channels."""
    o = osc(ctx)
    for n in CHANNELS:
        ch = _ch(n)
        trace = o.query(f"{ch}:TRA?")
        vdiv = o.query(f"{ch}:VDIV?")
        ofst = o.query(f"{ch}:OFST?")
        coup = o.query(f"{ch}:CPL?")
        click.echo(f"C{n}: trace={trace.split()[-1]}  v/div={vdiv.split()[-1]}  "
                   f"offset={ofst.split()[-1]}  coupling={coup.split()[-1]}")


@channel_group.command("on")
@_chan_option()
@click.pass_context
def channel_on(ctx, channel):
    """Turn a channel trace on."""
    osc(ctx).write(f"C{channel}:TRA ON")
    click.echo(f"C{channel} trace enabled.")


@channel_group.command("off")
@_chan_option()
@click.pass_context
def channel_off(ctx, channel):
    """Turn a channel trace off."""
    osc(ctx).write(f"C{channel}:TRA OFF")
    click.echo(f"C{channel} trace disabled.")


@channel_group.command("vdiv")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def vdiv(ctx, channel, value):
    """Get/set vertical scale (volts/div)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query(f"C{channel}:VDIV?"))
    else:
        o.write(f"C{channel}:VDIV {value}")
        click.echo(f"C{channel} v/div = {value} V")


@channel_group.command("offset")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, channel, value):
    """Get/set vertical offset (V)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query(f"C{channel}:OFST?"))
    else:
        o.write(f"C{channel}:OFST {value}")
        click.echo(f"C{channel} offset = {value} V")


@channel_group.command("coupling")
@_chan_option()
@click.argument(
    "value", type=click.Choice(["A1M", "D1M", "A50", "D50", "GND"]), required=False
)
@click.pass_context
def coupling(ctx, channel, value):
    """Get/set input coupling (A=AC, D=DC; 1M/50 ohm; GND)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query(f"C{channel}:CPL?"))
    else:
        o.write(f"C{channel}:CPL {value}")
        click.echo(f"C{channel} coupling = {value}")


@channel_group.command("bwlimit")
@_chan_option()
@click.argument("value", type=click.Choice(["OFF", "20M", "200M"]), required=False)
@click.pass_context
def bwlimit(ctx, channel, value):
    """Get/set bandwidth limit (OFF/20M/200M)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query(f"C{channel}:BWL?"))
    else:
        o.write(f"C{channel}:BWL {value}")
        click.echo(f"C{channel} bandwidth limit = {value}")


@channel_group.command("probe")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def probe(ctx, channel, value):
    """Get/set probe attenuation factor (e.g. 1, 10, 100)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query(f"C{channel}:ATTN?"))
    else:
        o.write(f"C{channel}:ATTN {value}")
        click.echo(f"C{channel} probe attenuation = {value}")


@channel_group.command("invert")
@_chan_option()
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def invert(ctx, channel, value):
    """Get/set channel inversion (INVT)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query(f"C{channel}:INVT?"))
    else:
        o.write(f"C{channel}:INVT {value}")
        click.echo(f"C{channel} invert = {value}")


@channel_group.command("unit")
@_chan_option()
@click.argument("value", type=click.Choice(["V", "A"]), required=False)
@click.pass_context
def unit(ctx, channel, value):
    """Get/set channel unit (V/A)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query(f"C{channel}:UNIT?"))
    else:
        o.write(f"C{channel}:UNIT {value}")
        click.echo(f"C{channel} unit = {value}")


@channel_group.command("skew")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def skew(ctx, channel, value):
    """Get/set channel deskew (seconds)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query(f"C{channel}:SKEW?"))
    else:
        o.write(f"C{channel}:SKEW {value}")
        click.echo(f"C{channel} skew = {value} s")
