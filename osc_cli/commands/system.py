"""System, utility, and IEEE-488.2 common commands (LeCroy X-Stream dialect)."""

from __future__ import annotations

import click

from ..cli import osc


@click.group(name="system")
def system_group():
    """System identity, status, clock, and common commands."""


@system_group.command("idn")
@click.pass_context
def idn(ctx):
    """Return the instrument identification string (*IDN?)."""
    click.echo(osc(ctx).idn())


@system_group.command("reset")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def reset(ctx, yes):
    """Reset the oscilloscope to factory defaults (*RST)."""
    if not yes:
        click.confirm("This resets the oscilloscope to factory defaults. Continue?", abort=True)
    osc(ctx).reset()
    click.echo("Reset complete.")


@system_group.command("error")
@click.pass_context
def error(ctx):
    """Query the next error in the error queue (SYST:ERR?)."""
    click.echo(osc(ctx).query("SYSTem:ERRor?"))


@system_group.command("clear")
@click.pass_context
def clear(ctx):
    """Clear the status registers and error queue (*CLS)."""
    osc(ctx).write("*CLS")


@system_group.command("opc")
@click.pass_context
def opc(ctx):
    """Wait for pending operations to complete (*OPC?)."""
    click.echo(osc(ctx).query("*OPC?"))


@system_group.command("trigger")
@click.pass_context
def trigger(ctx):
    """Send a software trigger (*TRG)."""
    osc(ctx).write("*TRG")


@system_group.command("selftest")
@click.pass_context
def selftest(ctx):
    """Run self-test and report the status (*TST?)."""
    click.echo(osc(ctx).query("*TST?"))


@system_group.command("calibrate")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def calibrate(ctx, yes):
    """Run internal self-calibration (*CAL?)."""
    if not yes:
        click.confirm("Self-calibration will run on the oscilloscope. Continue?", abort=True)
    click.echo(osc(ctx).query("*CAL?"))


@system_group.command("version")
@click.pass_context
def version(ctx):
    """Query the SCPI version (SYST:VERS?)."""
    click.echo(osc(ctx).query("SYSTem:VERSion?"))


@system_group.command("scopeid")
@click.pass_context
def scopeid(ctx):
    """Query the unique scope ID (SCOPEID?)."""
    click.echo(osc(ctx).query("SCOPEID?"))


@system_group.command("date")
@click.argument("value", required=False)
@click.pass_context
def date(ctx, value):
    """Get/set the date (YYYYMMDD)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("SYSTem:DATE?"))
    else:
        o.write(f"SYSTem:DATE {value}")
        click.echo(f"Date set to {value}")


@system_group.command("time")
@click.argument("value", required=False)
@click.pass_context
def time_(ctx, value):
    """Get/set the time (HHMMSS)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("SYSTem:TIME?"))
    else:
        o.write(f"SYSTem:TIME {value}")
        click.echo(f"Time set to {value}")


@system_group.command("header")
@click.argument("value", type=click.Choice(["SHORT", "LONG", "OFF"]), required=False)
@click.pass_context
def header(ctx, value):
    """Get/set response header mode (CHDR)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("CHDR?"))
    else:
        o.write(f"CHDR {value}")
        click.echo(f"Header mode = {value}")
