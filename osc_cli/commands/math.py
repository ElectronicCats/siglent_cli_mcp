"""Math channel, display, and cursor commands (LeCroy dialect)."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import misc as ops_misc


@click.group(name="math")
def math_group():
    """Math channel control (MATH:...)."""


@math_group.command("function")
@click.argument("value", type=click.Choice(ops_misc.MATH_FUNCTIONS), required=False)
@click.pass_context
def function(ctx, value):
    """Get/set the math function via MATH:FUNC."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "MATH:FUNC"))
    else:
        ops_misc.set_math_function(o, value)
        click.echo(f"Math function = {value}")


@math_group.command("offset")
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, value):
    """Get/set math vertical offset via MATH:OFST."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "MATH:OFST"))
    else:
        ops_misc.set_math_offset(o, value)
        click.echo(f"Math offset = {value}")


@math_group.command("scale")
@click.argument("value", type=float, required=False)
@click.pass_context
def scale(ctx, value):
    """Get/set math vertical scale via MATH:SCALE."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "MATH:SCALE"))
    else:
        ops_misc.set_math_scale(o, value)
        click.echo(f"Math scale = {value}")


@click.group(name="display")
def display_group():
    """Display and rendering control."""


@display_group.command("grid")
@click.argument("value", type=click.Choice(ops_misc.GRIDS), required=False)
@click.pass_context
def grid(ctx, value):
    """Get/set grid display via GRDS."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "GRDS"))
    else:
        ops_misc.set_grid(o, value)
        click.echo(f"Grid = {value}")


@display_group.command("intensity")
@click.argument("value", type=int, required=False)
@click.pass_context
def intensity(ctx, value):
    """Get/set trace intensity via INTS."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "INTS"))
    else:
        ops_misc.set_intensity(o, value)
        click.echo(f"Trace intensity = {value}")


@display_group.command("menu")
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def menu(ctx, value):
    """Get/set menu display via MENU."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "MENU"))
    else:
        ops_misc.set_menu(o, value)
        click.echo(f"Menu = {value}")


@click.group(name="cursor")
def cursor_group():
    """Cursor control."""


@cursor_group.command("mode")
@click.argument("value", type=click.Choice(ops_misc.CURSOR_MODES), required=False)
@click.pass_context
def mode(ctx, value):
    """Get/set cursor mode via CRMS."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_misc.query(o, "CRMS"))
    else:
        ops_misc.set_cursor_mode(o, value)
        click.echo(f"Cursor mode = {value}")
