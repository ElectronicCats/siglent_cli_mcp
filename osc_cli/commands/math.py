"""Math channel, display, and cursor commands (LeCroy dialect)."""

from __future__ import annotations

import click

from ..cli import osc


@click.group(name="math")
def math_group():
    """Math channel control (MATH:...)."""


@math_group.command("function")
@click.argument("value", type=click.Choice(["FX", "FY", "FZ", "ADD", "SUB", "MUL", "DIV", "FFT"]), required=False)
@click.pass_context
def function(ctx, value):
    """Get/set the math function via MATH:FUNC."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("MATH:FUNC?"))
    else:
        o.write(f"MATH:FUNC {value}")
        click.echo(f"Math function = {value}")


@math_group.command("offset")
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, value):
    """Get/set math vertical offset via MATH:OFST."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("MATH:OFST?"))
    else:
        o.write(f"MATH:OFST {value}")
        click.echo(f"Math offset = {value}")


@math_group.command("scale")
@click.argument("value", type=float, required=False)
@click.pass_context
def scale(ctx, value):
    """Get/set math vertical scale via MATH:SCALE."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("MATH:SCALE?"))
    else:
        o.write(f"MATH:SCALE {value}")
        click.echo(f"Math scale = {value}")


@click.group(name="display")
def display_group():
    """Display and rendering control."""


@display_group.command("grid")
@click.argument("value", type=click.Choice(["FULL", "HALF", "OFF"]), required=False)
@click.pass_context
def grid(ctx, value):
    """Get/set grid display via GRDS."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("GRDS?"))
    else:
        o.write(f"GRDS {value}")
        click.echo(f"Grid = {value}")


@display_group.command("intensity")
@click.argument("value", type=int, required=False)
@click.pass_context
def intensity(ctx, value):
    """Get/set trace intensity via INTS."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("INTS?"))
    else:
        o.write(f"INTS TRACE,{value}")
        click.echo(f"Trace intensity = {value}")


@display_group.command("menu")
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def menu(ctx, value):
    """Get/set menu display via MENU."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("MENU?"))
    else:
        o.write(f"MENU {value}")
        click.echo(f"Menu = {value}")


@click.group(name="cursor")
def cursor_group():
    """Cursor control."""


@cursor_group.command("mode")
@click.argument("value", type=click.Choice(["OFF", "TRACK", "HABS", "HREL", "VABS", "VREL"]), required=False)
@click.pass_context
def mode(ctx, value):
    """Get/set cursor mode via CRMS."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("CRMS?"))
    else:
        o.write(f"CRMS {value}")
        click.echo(f"Cursor mode = {value}")
