"""Convert the scope's BMP screen dumps to PNG using only the standard library."""

from __future__ import annotations

import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_DEFAULT_MASKS = {
    16: (0x7C00, 0x03E0, 0x001F),  # RGB555
    32: (0x00FF0000, 0x0000FF00, 0x000000FF),  # BGRX
}


def bmp_to_png(data: bytes) -> bytes:
    """Convert an uncompressed 16/24/32-bit BMP to an RGB PNG."""
    width, height, rows = _decode_bmp(data)
    return _encode_png(width, height, rows)


def _decode_bmp(data: bytes):
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError("Not a BMP image (missing 'BM' signature)")
    file_size = struct.unpack_from("<I", data, 2)[0]
    if len(data) < file_size:
        raise ValueError(f"Truncated BMP: header declares {file_size} bytes, got {len(data)}")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height, _planes, bpp, compression = struct.unpack_from("<iiHHI", data, 18)
    if bpp not in (16, 24, 32):
        raise ValueError(f"Unsupported BMP depth: {bpp} bits per pixel")
    if compression not in (0, 3) or (compression == 3 and bpp == 24):
        raise ValueError(f"Unsupported BMP compression: {compression}")
    if width <= 0 or height == 0:
        raise ValueError(f"Invalid BMP size {width}x{height}")
    top_down = height < 0
    height = abs(height)
    row_size = (bpp * width + 31) // 32 * 4
    if pixel_offset + row_size * height > len(data):
        raise ValueError("Truncated BMP pixel data")
    # BI_BITFIELDS masks follow the 40-byte info header (offset 54); V4/V5
    # headers store them at the same offset.
    if compression == 3:
        if len(data) < 66:
            raise ValueError("Truncated BMP: missing BI_BITFIELDS masks")
        masks = struct.unpack_from("<III", data, 54)
    else:
        masks = _DEFAULT_MASKS.get(bpp)
    rows = []
    for y in range(height):
        src = y if top_down else height - 1 - y
        start = pixel_offset + src * row_size
        rows.append(_row_to_rgb(data[start : start + row_size], width, bpp, masks))
    return width, height, rows


def _row_to_rgb(row: bytes, width: int, bpp: int, masks) -> bytes:
    if bpp == 24:
        src = row[: width * 3]
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = src[2::3], src[1::3], src[0::3]
        return bytes(rgb)
    if bpp == 32 and tuple(masks) == _DEFAULT_MASKS[32]:
        src = row[: width * 4]
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = src[2::4], src[1::4], src[0::4]
        return bytes(rgb)
    fmt, size = ("<H", 2) if bpp == 16 else ("<I", 4)
    channels = [_channel(mask) for mask in masks]
    out = bytearray()
    for x in range(width):
        px = struct.unpack_from(fmt, row, x * size)[0]
        for shift, maxv, mask in channels:
            out.append(((px & mask) >> shift) * 255 // maxv if maxv else 0)
    return bytes(out)


def _channel(mask: int):
    if mask == 0:
        return 0, 0, 0
    shift = (mask & -mask).bit_length() - 1
    return shift, mask >> shift, mask


def _chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def _encode_png(width: int, height: int, rows) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rows)
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 6))
        + _chunk(b"IEND", b"")
    )
