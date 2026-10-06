"""Screen capture (SCDP returns an 800x480 BMP)."""

from __future__ import annotations

from ..device import OscError
from ..imaging import bmp_to_png


def capture_bmp(o) -> bytes:
    return o.read_bmp("SCDP")


def capture_png(o) -> bytes:
    try:
        return bmp_to_png(capture_bmp(o))
    except ValueError as e:
        raise OscError(f"Screen dump could not be converted to PNG: {e}") from e
