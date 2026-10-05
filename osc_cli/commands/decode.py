"""Serial decode trigger commands (LeCroy dialect).

The SDS1104X-E exposes serial decode through trigger commands:
TRIG_UART:..., TRIG_IIC:... (I2C), TRIG_SPI:....
"""

from __future__ import annotations

import click

from ..cli import osc

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
    o = osc(ctx)
    o.write("TRSE SERIAL")
    o.write(f"TRIG_UART:RX {rx}")
    o.write(f"TRIG_UART:BAUD {baud}")
    o.write(f"TRIG_UART:PARITY {parity}")
    o.write(f"TRIG_UART:STOP {stop}")
    o.write(f"TRIG_UART:POLARITY {polarity}")
    if tx:
        o.write(f"TRIG_UART:TX {tx}")
    click.echo(f"UART decode: RX={rx} baud={baud} parity={parity} stop={stop}")


@decode_group.command("i2c")
@click.option("--scl", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--sda", type=click.Choice(CH), default="C2", show_default=True)
@click.pass_context
def i2c(ctx, scl, sda):
    """Configure I2C decode trigger."""
    o = osc(ctx)
    o.write("TRSE SERIAL")
    o.write(f"TRIG_IIC:SCL {scl}")
    o.write(f"TRIG_IIC:SDA {sda}")
    click.echo(f"I2C decode: SCL={scl} SDA={sda}")


@decode_group.command("spi")
@click.option("--clk", type=click.Choice(CH), default="C1", show_default=True)
@click.option("--miso", type=click.Choice(CH), default="C2", show_default=True)
@click.option("--mosi", type=click.Choice(CH), default="C3", show_default=True)
@click.option("--cs", type=click.Choice(CH), default="C4", show_default=True)
@click.pass_context
def spi(ctx, clk, miso, mosi, cs):
    """Configure SPI decode trigger."""
    o = osc(ctx)
    o.write("TRSE SERIAL")
    o.write(f"TRIG_SPI:CLK {clk}")
    o.write(f"TRIG_SPI:MISO {miso}")
    o.write(f"TRIG_SPI:MOSI {mosi}")
    o.write(f"TRIG_SPI:CS {cs}")
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

