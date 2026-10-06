import pytest

from osc_cli.imaging import bmp_to_png
from tests.bmp_util import make_bmp, read_png

PIXELS = [
    [(255, 0, 0), (0, 255, 0), (0, 0, 255)],
    [(255, 255, 255), (0, 0, 0), (255, 255, 0)],
]


@pytest.mark.parametrize("bpp", [24, 32])
@pytest.mark.parametrize("top_down", [False, True])
def test_converts_truecolor(bpp, top_down):
    png = bmp_to_png(make_bmp(PIXELS, bpp=bpp, top_down=top_down))
    assert read_png(png) == (3, 2, PIXELS)


@pytest.mark.parametrize("masks", [None, (0xF800, 0x07E0, 0x001F)])
def test_converts_16_bit(masks):
    png = bmp_to_png(make_bmp(PIXELS, bpp=16, masks=masks))
    assert read_png(png) == (3, 2, PIXELS)


def test_converts_32_bit_bitfields():
    masks = (0x00FF0000, 0x0000FF00, 0x000000FF)
    png = bmp_to_png(make_bmp(PIXELS, bpp=32, masks=masks))
    assert read_png(png)[2] == PIXELS


def test_rejects_non_bmp():
    with pytest.raises(ValueError, match="BM"):
        bmp_to_png(b"\x89PNG" + bytes(100))


def test_rejects_truncated():
    data = make_bmp(PIXELS)
    with pytest.raises(ValueError, match="Truncated"):
        bmp_to_png(data[:-4])


def test_rejects_unsupported_depth():
    data = bytearray(make_bmp(PIXELS))
    data[28] = 8  # biBitCount
    with pytest.raises(ValueError, match="8 bits"):
        bmp_to_png(bytes(data))


def test_rejects_bitfields_without_masks():
    """Regression: BI_BITFIELDS BMP too short to contain masks must raise ValueError."""
    # Create BMP: header (14) + info (40) + pixel data = 65 bytes total
    # compression=3 (BI_BITFIELDS) but only 11 bytes after info header (needs 12 for masks)
    data = bytearray(65)
    data[0:2] = b"BM"
    # File size at offset 2
    import struct
    struct.pack_into("<I", data, 2, 65)
    # Pixel offset at offset 10 (54 = 14 + 40)
    struct.pack_into("<I", data, 10, 54)
    # Width, height at offset 18-22 (1x1 to minimize pixel data)
    struct.pack_into("<ii", data, 18, 1, 1)
    # Planes at offset 26
    struct.pack_into("<H", data, 26, 1)
    # Bit count (16) at offset 28
    struct.pack_into("<H", data, 28, 16)
    # Compression = 3 (BI_BITFIELDS) at offset 30
    struct.pack_into("<I", data, 30, 3)
    with pytest.raises(ValueError, match="BI_BITFIELDS"):
        bmp_to_png(bytes(data))
