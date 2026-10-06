"""Channel (vertical) control commands (LeCroy X-Stream dialect).

Channels are C1..C4. The command strings live in osc_cli.ops.channel.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import channel as ops_channel

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


def _get_or_set(ctx, channel, field, value, message):
    o = osc(ctx)
    n = int(channel)
    if value is None:
        click.echo(ops_channel.query_field(o, n, field))
    else:
        ops_channel.write_field(o, n, field, value)
        click.echo(message.format(ch=f"C{channel}", value=value))


@click.group(name="channel")
def channel_group():
    """Vertical channel control (CH1..CH4)."""


@channel_group.command("list")
@click.pass_context
def channel_list(ctx):
    """Show the state of all channels."""
    o = osc(ctx)
    for n in ops_channel.CHANNELS:
        trace = ops_channel.query_field(o, n, "enabled")
        vdiv = ops_channel.query_field(o, n, "vdiv")
        ofst = ops_channel.query_field(o, n, "offset")
        coup = ops_channel.query_field(o, n, "coupling")
        click.echo(f"C{n}: trace={trace.split()[-1]}  v/div={vdiv.split()[-1]}  "
                   f"offset={ofst.split()[-1]}  coupling={coup.split()[-1]}")


@channel_group.command("on")
@_chan_option()
@click.pass_context
def channel_on(ctx, channel):
    """Turn a channel trace on."""
    ops_channel.write_field(osc(ctx), int(channel), "enabled", True)
    click.echo(f"C{channel} trace enabled.")


@channel_group.command("off")
@_chan_option()
@click.pass_context
def channel_off(ctx, channel):
    """Turn a channel trace off."""
    ops_channel.write_field(osc(ctx), int(channel), "enabled", False)
    click.echo(f"C{channel} trace disabled.")


@channel_group.command("vdiv")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def vdiv(ctx, channel, value):
    """Get/set vertical scale (volts/div)."""
    _get_or_set(ctx, channel, "vdiv", value, "{ch} v/div = {value} V")


@channel_group.command("offset")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, channel, value):
    """Get/set vertical offset (V)."""
    _get_or_set(ctx, channel, "offset", value, "{ch} offset = {value} V")


@channel_group.command("coupling")
@_chan_option()
@click.argument("value", type=click.Choice(ops_channel.COUPLINGS), required=False)
@click.pass_context
def coupling(ctx, channel, value):
    """Get/set input coupling (A=AC, D=DC; 1M/50 ohm; GND)."""
    _get_or_set(ctx, channel, "coupling", value, "{ch} coupling = {value}")


@channel_group.command("bwlimit")
@_chan_option()
@click.argument("value", type=click.Choice(ops_channel.BW_LIMITS), required=False)
@click.pass_context
def bwlimit(ctx, channel, value):
    """Get/set bandwidth limit (OFF/20M/200M)."""
    _get_or_set(ctx, channel, "bw_limit", value, "{ch} bandwidth limit = {value}")


@channel_group.command("probe")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def probe(ctx, channel, value):
    """Get/set probe attenuation factor (e.g. 1, 10, 100)."""
    _get_or_set(ctx, channel, "probe", value, "{ch} probe attenuation = {value}")


@channel_group.command("invert")
@_chan_option()
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def invert(ctx, channel, value):
    """Get/set channel inversion (INVT)."""
    _get_or_set(ctx, channel, "invert", value, "{ch} invert = {value}")


@channel_group.command("unit")
@_chan_option()
@click.argument("value", type=click.Choice(ops_channel.UNITS), required=False)
@click.pass_context
def unit(ctx, channel, value):
    """Get/set channel unit (V/A)."""
    _get_or_set(ctx, channel, "unit", value, "{ch} unit = {value}")


@channel_group.command("skew")
@_chan_option()
@click.argument("value", type=float, required=False)
@click.pass_context
def skew(ctx, channel, value):
    """Get/set channel deskew (seconds)."""
    _get_or_set(ctx, channel, "skew", value, "{ch} skew = {value} s")
