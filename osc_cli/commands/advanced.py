"""Counter (FCNT), save/recall, and miscellaneous commands (LeCroy dialect)."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import misc as ops_misc


@click.group(name="counter")
def counter_group():
    """Frequency counter (FCNT)."""


@counter_group.command("on")
@click.pass_context
def counter_on(ctx):
    """Enable the frequency counter."""
    ops_misc.set_counter(osc(ctx), True)
    click.echo("Counter enabled.")


@counter_group.command("off")
@click.pass_context
def counter_off(ctx):
    """Disable the frequency counter."""
    ops_misc.set_counter(osc(ctx), False)
    click.echo("Counter disabled.")


@counter_group.command("status")
@click.pass_context
def counter_status(ctx):
    """Show counter status and values."""
    click.echo(ops_misc.query(osc(ctx), "FCNT"))


@counter_group.command("freq")
@click.pass_context
def counter_freq(ctx):
    """Query the measured frequency (Hz)."""
    # FCNT? returns a list of KEY,VALUE pairs; extract FRQ.
    o = osc(ctx)
    resp = ops_misc.query(o, "FCNT")
    for part in resp.split(","):
        if part.startswith("FRQ"):
            click.echo(part)
            return
    click.echo(resp)


@click.group(name="save")
def save_group():
    """Save/recall setups and waveforms."""


@save_group.command("setup")
@click.argument("path", required=False)
@click.pass_context
def setup(ctx, path):
    """Save the current setup to a file on the scope."""
    o = osc(ctx)
    if path is None:
        click.echo("Usage: osc save setup <path>")
    else:
        ops_misc.save_setup(o, path)
        click.echo(f"Setup saved to {path}")


@save_group.command("recall-setup")
@click.argument("path")
@click.pass_context
def recall_setup(ctx, path):
    """Recall a saved setup."""
    ops_misc.recall_setup(osc(ctx), path)
    click.echo(f"Setup recalled from {path}")
