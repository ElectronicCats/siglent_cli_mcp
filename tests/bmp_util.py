"""Build BMPs and decode PNGs for tests (stdlib only)."""

from __future__ import annotations

import struct
import zlib


def _pack(value8: int, mask: int) -> int:
    shift = (mask & -mask).bit_length() - 1
    maxv = mask >> shift
    return ((value8 * maxv // 255) << shift) & mask


def make_bmp(pixels, bpp=24, top_down=False, masks=None) -> bytes:
    """pixels: rows top-to-bottom of (r, g, b). masks => BI_BITFIELDS."""
    height, width = len(pixels), len(pixels[0])
    row_size = (bpp * width + 31) // 32 * 4
    rows = []
    for row in pixels:
        b = bytearray()
        for r, g, bl in row:
            if bpp == 24:
                b += bytes((bl, g, r))
            elif masks:
                value = _pack(r, masks[0]) | _pack(g, masks[1]) | _pack(bl, masks[2])
                b += struct.pack("<H" if bpp == 16 else "<I", value)
            elif bpp == 32:
                b += bytes((bl, g, r, 0))
            else:  # 16 bpp default RGB555
                value = _pack(r, 0x7C00) | _pack(g, 0x03E0) | _pack(bl, 0x001F)
                b += struct.pack("<H", value)
        b += b"\0" * (row_size - len(b))
        rows.append(bytes(b))
    if not top_down:
        rows.reverse()
    pixel_data = b"".join(rows)
    extra = struct.pack("<III", *masks) if masks else b""
    pixel_offset = 14 + 40 + len(extra)
    info = struct.pack(
        "<IiiHHIIiiII", 40, width, -height if top_down else height, 1, bpp,
        3 if masks else 0, len(pixel_data), 2835, 2835, 0, 0,
    )
    header = b"BM" + struct.pack("<IHHI", pixel_offset + len(pixel_data), 0, 0, pixel_offset)
    return header + info + extra + pixel_data


def read_png(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, width = 8, b"", None
    while pos < len(data):
        (length,) = struct.unpack_from(">I", data, pos)
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack_from(">I", data, pos + 8 + length)
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            assert (depth, color) == (8, 2)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 3 + 1
    rows = []
    for y in range(height):
        line = raw[y * stride : (y + 1) * stride]
        assert line[0] == 0
        rows.append([tuple(line[1 + 3 * x : 4 + 3 * x]) for x in range(width)])
    return width, height, rows
