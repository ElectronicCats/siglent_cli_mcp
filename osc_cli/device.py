"""Low-level connection layer for the SDS1104X-E oscilloscope over USBTMC.

The SDS1104X-E speaks a LeCroy X-Stream style command set (NOT standard Siglent
SCPI). This module uses pyvisa with the pyvisa-py backend (no NI-VISA needed)
and auto-detects the device by USB VID/PID (Siglent f4ec:ee38).

Key protocol details discovered from the live device:
- Responses echo a short header (e.g. "C1:VDIV 1.00E+00V") unless CHDR OFF.
- Binary waveform data uses IEEE 488.2 definite-length blocks "#9<9digits><data>".
- Screen dumps (SCDP) return raw BMP bytes (no block framing); the length
  comes from the BMP header itself.
"""

from __future__ import annotations

import struct
import time
from contextlib import contextmanager
from dataclasses import dataclass

try:
    import pyvisa
except ImportError:  # pragma: no cover
    pyvisa = None

SIGLENT_VID = 0xF4EC
SIGLENT_PID = 0xEE38
WAVEDESC_LEN = 346


class OscError(Exception):
    """Raised on oscilloscope communication or protocol errors."""


class OscTransportError(OscError):
    """The USB/VISA transport failed (timeout, pipe error, short read).

    Unlike protocol errors, the same request may succeed on a new connection.
    """

    retried = False


class OscNotFoundError(OscError):
    """No oscilloscope could be opened."""


@dataclass(frozen=True)
class WaveformRaw:
    """One channel's capture as raw 8-bit ADC codes plus its scaling."""

    codes: bytes  # signed int8 ADC codes, one per returned sample
    vdiv: float  # volts/div (VERTICAL_GAIN on this firmware)
    offset: float  # vertical offset (V)
    horz_interval: float  # seconds between returned samples
    horz_offset: float  # time of the first sample (s)
    wave_count: int
    first_valid: int
    last_valid: int


class Oscilloscope:
    """Connection wrapper exposing query/write/binary helpers."""

    def __init__(self, resource: str | None = None, timeout_ms: int = 5000, *, instrument=None):
        self.timeout_ms = timeout_ms
        self.resource_name = resource
        self._rm = None
        if instrument is not None:
            self._inst = instrument
        else:
            if pyvisa is None:
                raise OscError(
                    "pyvisa is not installed. Run: pip install pyvisa pyvisa-py pyusb"
                )
            self._rm = pyvisa.ResourceManager("@py")
            self._inst = self._open_resource()
        self._inst.timeout = self.timeout_ms
        self._inst.write_termination = "\n"
        self._inst.read_termination = "\n"

    def _open_resource(self):
        if self.resource_name:
            try:
                return self._rm.open_resource(self.resource_name)
            except Exception as e:  # noqa: BLE001
                raise OscNotFoundError(
                    f"Cannot open resource '{self.resource_name}': {e}"
                ) from e
        return self._find_siglent()

    def _find_siglent(self):
        resources = self._rm.list_resources()
        usb_resources = [r for r in resources if r.upper().startswith("USB")]
        if not usb_resources:
            raise OscNotFoundError(
                "No USBTMC device found. Is the oscilloscope connected and "
                "powered on? Check permissions (see README 'udev' section)."
            )

        for r in usb_resources:
            try:
                if self._is_siglent(r):
                    return self._rm.open_resource(r)
            except Exception:  # noqa: BLE001
                continue

        inst = self._rm.open_resource(usb_resources[0])
        try:
            inst.query("*IDN?")
        except Exception as e:  # noqa: BLE001
            raise OscNotFoundError(
                f"Found USB device {usb_resources[0]} but could not query *IDN?: {e}"
            ) from e
        return inst

    @staticmethod
    def _is_siglent(resource: str) -> bool:
        norm = resource.upper()
        vid = f"{SIGLENT_VID:X}"
        pid = f"{SIGLENT_PID:X}"
        return vid in norm and pid in norm

    # ---- low level SCPI -------------------------------------------------
    def write(self, cmd: str) -> None:
        """Send a command (no response expected)."""
        try:
            self._inst.write(cmd)
        except Exception as e:  # noqa: BLE001
            raise OscTransportError(f"Write '{cmd}' failed: {e}") from e

    def query(self, cmd: str, retries: int = 3) -> str:
        """Send a query and return the stripped response.

        The AWG firmware occasionally leaves the USBTMC pipe in a transient
        error state after bursts of writes, causing a spurious USBError on the
        next read. We retry transparently `retries` times to absorb this. Use
        retries=0 for queries that must not run twice (*CAL?, *TST?).
        """
        last_exc = None
        for attempt in range(retries + 1):
            try:
                return self._inst.query(cmd).strip()
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt == retries:
                    break
                # Clear any pending status before retrying.
                try:
                    self._inst.clear()
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.1 * (attempt + 1))
        raise OscTransportError(
            f"Query '{cmd}' failed after {retries + 1} attempt(s): {last_exc}"
        ) from last_exc

    def query_raw(self, cmd: str) -> bytes:
        """Send a query and return the raw bytes (for binary responses)."""
        self.write(cmd)
        try:
            return self._inst.read_raw()
        except Exception as e:  # noqa: BLE001
            raise OscTransportError(f"Read after '{cmd}' failed: {e}") from e

    def _read_chunk(self, got: int, expected) -> bytes:
        try:
            chunk = self._inst.read_raw()
        except Exception as e:  # noqa: BLE001
            raise OscTransportError(
                f"Read failed after {got} of {expected} bytes: {e}"
            ) from e
        if not chunk:
            raise OscTransportError(f"Empty read after {got} of {expected} bytes")
        return chunk

    def read_binary_block(self, deadline_s: float = 60.0) -> bytes:
        """Read an IEEE 488.2 definite-length block (#<n><n digits><data>).

        USBTMC delivers the payload in small transfers and binary data may
        contain 0x0A bytes, so newline termination is disabled and reads are
        accumulated until the declared byte count arrives or `deadline_s`
        passes.
        """
        old_term = self._inst.read_termination
        self._inst.read_termination = None
        start = time.monotonic()
        try:
            data = bytearray()
            header_end = declared = None
            while True:
                if time.monotonic() - start > deadline_s:
                    raise OscTransportError(
                        f"Block transfer timed out after {len(data)} of "
                        f"{declared if declared is not None else '?'} bytes"
                    )
                data += self._read_chunk(len(data), declared if declared is not None else "?")
                if declared is None:
                    i = data.find(b"#")
                    if i < 0:
                        if len(data) > 64:
                            raise OscError(f"No block header in {bytes(data[:32])!r}")
                        continue
                    if len(data) < i + 2:
                        continue
                    ndigits = data[i + 1] - 0x30
                    if not 1 <= ndigits <= 9:
                        raise OscError(f"Unexpected block header: {bytes(data[i:i + 3])!r}")
                    if len(data) < i + 2 + ndigits:
                        continue
                    declared = int(data[i + 2 : i + 2 + ndigits])
                    header_end = i + 2 + ndigits
                if len(data) >= header_end + declared:
                    return bytes(data[header_end : header_end + declared])
        finally:
            self._inst.read_termination = old_term

    def read_bmp(self, cmd: str = "SCDP", deadline_s: float = 30.0) -> bytes:
        """Send `cmd` and read a raw BMP whose length comes from its own header."""
        self.write(cmd)
        old_term = self._inst.read_termination
        self._inst.read_termination = None
        start = time.monotonic()
        try:
            data = bytearray()
            size = None
            while size is None or len(data) < size:
                if time.monotonic() - start > deadline_s:
                    raise OscTransportError(
                        f"Screen dump timed out after {len(data)} of {size or '?'} bytes"
                    )
                data += self._read_chunk(len(data), size or "?")
                if size is None and len(data) >= 6:
                    if data[:2] != b"BM":
                        raise OscError(
                            f"Screen dump is not a BMP (starts with {bytes(data[:8])!r})"
                        )
                    size = struct.unpack_from("<I", data, 2)[0]
            return bytes(data[:size])
        finally:
            self._inst.read_termination = old_term

    def query_float(self, cmd: str) -> float:
        # LeCroy responses embed units; extract the leading numeric token.
        return parse_float(self.query(cmd))

    def query_int(self, cmd: str) -> int:
        return int(parse_float(self.query(cmd)))

    def idn(self) -> str:
        return self.query("*IDN?")

    @contextmanager
    def timeout(self, ms: int):
        """Temporarily use a different I/O timeout (e.g. for *CAL?)."""
        old = self._inst.timeout
        self._inst.timeout = ms
        try:
            yield
        finally:
            self._inst.timeout = old

    def close(self) -> None:
        if self._inst is not None:
            try:
                self._inst.close()
            except Exception:  # noqa: BLE001
                pass
            self._inst = None

    def __enter__(self) -> "Oscilloscope":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- convenience ----------------------------------------------------
    def reset(self) -> None:
        self.write("*RST")

    def opc_wait(self, timeout_s: float = 5.0) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < timeout_s:
            if self.query("*OPC?") == "1":
                return True
            time.sleep(0.05)
        return False

    # ---- waveform data --------------------------------------------------
    def get_waveform_raw(
        self, channel: str = "C1", sparsing: int = 1, deadline_s: float = 60.0
    ) -> WaveformRaw:
        """Fetch one channel's capture as raw ADC codes.

        `sparsing` > 1 asks the scope to send every k-th point (WFSU SP). The
        firmware ignores NP, so without sparsing the full memory is returned.
        """
        self.write("CHDR OFF")
        try:
            self.write(f"WFSU SP,{sparsing if sparsing > 1 else 0},NP,0,FP,0")
            self.write(f"{channel}:WF? ALL")
            block = self.read_binary_block(deadline_s)
        finally:
            try:
                if sparsing > 1:
                    self.write("WFSU SP,0,NP,0,FP,0")
                self.write("CHDR SHORT")
            except OscError:
                pass
        return parse_wavedesc(block, sparsing)

    def get_waveform(self, channel: str = "C1", points: int = 0) -> dict:
        """Fetch a full waveform as the legacy dict (lists of volts and seconds).

        `points` is accepted for compatibility; the firmware ignores NP.
        """
        return waveform_dict(self.get_waveform_raw(channel))


def parse_wavedesc(block: bytes, sparsing: int = 1) -> WaveformRaw:
    """Split a WF? ALL block into its WAVEDESC scaling and int8 codes."""
    if len(block) < WAVEDESC_LEN:
        raise OscError(f"Waveform block too short ({len(block)} bytes)")

    def f32(off):
        return struct.unpack_from("<f", block, off)[0]

    def i32(off):
        return struct.unpack_from("<i", block, off)[0]

    desc_len = i32(36)
    array1_len = i32(60)
    return WaveformRaw(
        codes=bytes(block[desc_len : desc_len + array1_len]),
        vdiv=f32(156),  # VERTICAL_GAIN stores volts/div on this firmware
        offset=f32(160),
        horz_interval=f32(176) * max(sparsing, 1),
        horz_offset=struct.unpack_from("<d", block, 180)[0],
        wave_count=i32(116),
        first_valid=i32(124),
        last_valid=i32(128),
    )


def waveform_dict(raw: WaveformRaw) -> dict:
    """Legacy representation: volts and times as Python lists."""
    # 8-bit signed ADC codes span the 8-division grid: 256 codes / 8 div
    # = 32 codes per division, so volts = code * vdiv / 32.
    scale = raw.vdiv / 32.0
    samples = [scale * (b if b < 128 else b - 256) - raw.offset for b in raw.codes]
    times = [raw.horz_interval * k + raw.horz_offset for k in range(raw.wave_count)]
    return {
        "vdiv": raw.vdiv,
        "offset": raw.offset,
        "horz_interval": raw.horz_interval,
        "horz_offset": raw.horz_offset,
        "wave_count": raw.wave_count,
        "first_valid": raw.first_valid,
        "last_valid": raw.last_valid,
        "samples": samples,
        "times": times,
    }


def parse_float(s: str) -> float:
    """Extract a numeric value from a LeCroy-style response like 'C1:VDIV 1.00E+00V'."""
    import re

    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    if not m:
        raise ValueError(f"No numeric value in {s!r}")
    return float(m.group())


def get_device(resource: str | None = None, timeout_ms: int = 5000) -> Oscilloscope:
    """Factory: connect to the oscilloscope, raising a helpful error on failure."""
    try:
        return Oscilloscope(resource, timeout_ms)
    except OscError:
        raise
    except Exception as e:  # noqa: BLE001
        raise OscNotFoundError(
            f"Could not connect to the oscilloscope: {e}\n"
            "Check that it is powered on, connected via USB, and that the udev "
            "rule granting access is installed (see README)."
        ) from e
