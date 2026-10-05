"""Trigger control commands (LeCroy dialect).

TRMD (mode), TRSE (setup/type), TRSR (source), TRCP (coupling), TRLV (level),
TRDL (delay). Serial decode triggers use TRIG_UART:/TRIG_IIC:/TRIG_SPI:.
"""

from __future__ import annotations

import click

from ..cli import osc


@click.group(name="trigger")
def trigger_group():
    """Trigger configuration."""


@trigger_group.command("mode")
@click.argument("value", type=click.Choice(["AUTO", "NORM", "SINGLE", "STOP"]), required=False)
@click.pass_context
def mode(ctx, value):
    """Get/set trigger mode via TRMD."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("TRMD?"))
    else:
        o.write(f"TRMD {value}")
        click.echo(f"Trigger mode = {value}")


@trigger_group.command("type")
@click.argument(
    "value",
    type=click.Choice(["EDGE", "SERIAL", "PULSE", "VIDEO", "SLOPE", "PATTERN", "DROP", "INTV", "RUNT"]),
    required=False,
)
@click.pass_context
def type_(ctx, value):
    """Get/set trigger type via TRSE."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("TRSE?"))
    else:
        o.write(f"TRSE {value}")
        click.echo(f"Trigger type = {value}")


@trigger_group.command("source")
@click.argument("value", type=click.Choice(["C1", "C2", "C3", "C4", "EXT", "LINE"]), required=False)
@click.pass_context
def source(ctx, value):
    """Get/set trigger source via TRSR."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("TRSR?"))
    else:
        o.write(f"TRSR {value}")
        click.echo(f"Trigger source = {value}")


@trigger_group.command("level")
@click.argument("value", type=float, required=False)
@click.pass_context
def level(ctx, value):
    """Get/set trigger level (V) via TRLV."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("TRLV?"))
    else:
        o.write(f"TRLV {value}")
        click.echo(f"Trigger level = {value} V")


@trigger_group.command("coupling")
@click.argument("value", type=click.Choice(["DC", "AC", "HFREJ", "LFREJ"]), required=False)
@click.pass_context
def coupling(ctx, value):
    """Get/set trigger coupling via TRCP."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("TRCP?"))
    else:
        o.write(f"TRCP {value}")
        click.echo(f"Trigger coupling = {value}")


@trigger_group.command("status")
@click.pass_context
def status(ctx):
    """Show current trigger settings."""
    o = osc(ctx)
    click.echo(f"Mode    : {o.query('TRMD?')}")
    click.echo(f"Setup   : {o.query('TRSE?')}")
    for label, cmd in [("Source", "TRSR?"), ("Level", "TRLV?"), ("Coupling", "TRCP?")]:
        try:
            click.echo(f"{label:8s}: {o.query(cmd)}")
        except Exception:  # noqa: BLE001
            pass
