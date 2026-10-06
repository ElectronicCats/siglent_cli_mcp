"""Trigger control commands (LeCroy dialect).

The command strings live in osc_cli.ops.trigger. Serial decode triggers are in
the decode group.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import trigger as ops_trig


@click.group(name="trigger")
def trigger_group():
    """Trigger configuration."""


@trigger_group.command("mode")
@click.argument("value", type=click.Choice(ops_trig.MODES), required=False)
@click.pass_context
def mode(ctx, value):
    """Get/set trigger mode via TRMD."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "mode"))
    else:
        ops_trig.write_field(o, "mode", value)
        click.echo(f"Trigger mode = {value}")


@trigger_group.command("type")
@click.argument(
    "value",
    type=click.Choice(ops_trig.TYPES),
    required=False,
)
@click.pass_context
def type_(ctx, value):
    """Get/set trigger type via TRSE."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "type"))
    else:
        ops_trig.write_field(o, "type", value)
        click.echo(f"Trigger type = {value}")


@trigger_group.command("source")
@click.argument("value", type=click.Choice(ops_trig.SOURCES), required=False)
@click.pass_context
def source(ctx, value):
    """Get/set trigger source via TRSR."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "source"))
    else:
        ops_trig.write_field(o, "source", value)
        click.echo(f"Trigger source = {value}")


@trigger_group.command("level")
@click.argument("value", type=float, required=False)
@click.pass_context
def level(ctx, value):
    """Get/set trigger level (V) via TRLV."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "level"))
    else:
        ops_trig.write_field(o, "level", value)
        click.echo(f"Trigger level = {value} V")


@trigger_group.command("coupling")
@click.argument("value", type=click.Choice(ops_trig.COUPLINGS), required=False)
@click.pass_context
def coupling(ctx, value):
    """Get/set trigger coupling via TRCP."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_trig.query_field(o, "coupling"))
    else:
        ops_trig.write_field(o, "coupling", value)
        click.echo(f"Trigger coupling = {value}")


@trigger_group.command("status")
@click.pass_context
def status(ctx):
    """Show current trigger settings."""
    o = osc(ctx)
    click.echo(f"Mode    : {ops_trig.query_field(o, 'mode')}")
    click.echo(f"Setup   : {ops_trig.query_field(o, 'type')}")
    for label, field in [("Source", "source"), ("Level", "level"), ("Coupling", "coupling")]:
        try:
            click.echo(f"{label:8s}: {ops_trig.query_field(o, field, retries=0)}")
        except Exception:  # noqa: BLE001
            pass
