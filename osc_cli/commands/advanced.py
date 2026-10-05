"""Counter (FCNT), save/recall, and miscellaneous commands (LeCroy dialect)."""

from __future__ import annotations

import click

from ..cli import osc


@click.group(name="counter")
def counter_group():
    """Frequency counter (FCNT)."""


@counter_group.command("on")
@click.pass_context
def counter_on(ctx):
    """Enable the frequency counter."""
    osc(ctx).write("FCNT STATE,ON")
    click.echo("Counter enabled.")


@counter_group.command("off")
@click.pass_context
def counter_off(ctx):
    """Disable the frequency counter."""
    osc(ctx).write("FCNT STATE,OFF")
    click.echo("Counter disabled.")


@counter_group.command("status")
@click.pass_context
def counter_status(ctx):
    """Show counter status and values."""
    click.echo(osc(ctx).query("FCNT?"))


@counter_group.command("freq")
@click.pass_context
def counter_freq(ctx):
    """Query the measured frequency (Hz)."""
    # FCNT? returns a list of KEY,VALUE pairs; extract FRQ.
    o = osc(ctx)
    resp = o.query("FCNT?")
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
        o.write(f"STORE_SETUP FILE,\"{path}\"")
        click.echo(f"Setup saved to {path}")


@save_group.command("recall-setup")
@click.argument("path")
@click.pass_context
def recall_setup(ctx, path):
    """Recall a saved setup."""
    osc(ctx).write(f"RECALL_SETUP FILE,\"{path}\"")
    click.echo(f"Setup recalled from {path}")
