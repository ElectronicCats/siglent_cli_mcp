"""Low-level connection layer for the SDS1104X-E oscilloscope over USBTMC.

The SDS1104X-E speaks a LeCroy X-Stream style command set (NOT standard Siglent
SCPI). This module uses pyvisa with the pyvisa-py backend (no NI-VISA needed)
and auto-detects the device by USB VID/PID (Siglent f4ec:ee38).

Key protocol details discovered from the live device:
- Responses echo a short header (e.g. "C1:VDIV 1.00E+00V") unless CHDR OFF.
- Binary waveform data uses IEEE 488.2 definite-length blocks "#9<9digits><data>".
- Screen dumps (SCDP) return raw BMP bytes (no block framing).
"""

from __future__ import annotations

import struct
import time

try:
    import pyvisa
except ImportError:  # pragma: no cover
    pyvisa = None

SIGLENT_VID = 0xF4EC
SIGLENT_PID = 0xEE38


class OscError(Exception):
    """Raised on oscilloscope communication or protocol errors."""


class Oscilloscope:
    """Connection wrapper exposing query/write/binary helpers."""

    def __init__(self, resource: str | None = None, timeout_ms: int = 5000):
        if pyvisa is None:
            raise OscError(
                "pyvisa is not installed. Run: pip install pyvisa pyvisa-py pyusb"
            )
        self.timeout_ms = timeout_ms
        self._rm = pyvisa.ResourceManager("@py")
        self._inst = None
        self.resource_name = resource
        self._open()

    def _open(self) -> None:
        target = self.resource_name
        if target:
            try:
                self._inst = self._rm.open_resource(target)
            except Exception as e:  # noqa: BLE001
                raise OscError(f"Cannot open resource '{target}': {e}") from e
        else:
            self._inst = self._find_siglent()

        self._inst.timeout = self.timeout_ms
        self._inst.write_termination = "\n"
        self._inst.read_termination = "\n"

    def _find_siglent(self):
        resources = self._rm.list_resources()
        usb_resources = [r for r in resources if r.upper().startswith("USB")]
        if not usb_resources:
            raise OscError(
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
            raise OscError(
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
        self._inst.write(cmd)

    def query(self, cmd: str) -> str:
        """Send a query and return the stripped response.

        The AWG firmware occasionally leaves the USBTMC pipe in a transient
        error state after bursts of writes, causing a spurious USBError on the
        next read. We retry transparently a few times to absorb this.
        """
        last_exc = None
        for attempt in range(4):
            try:
                return self._inst.query(cmd).strip()
            except Exception as e:  # noqa: BLE001
                last_exc = e
                # Clear any pending status before retrying.
                try:
                    self._inst.clear()
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.1 * (attempt + 1))
        raise OscError(f"Query '{cmd}' failed after retries: {last_exc}")

    def query_raw(self, cmd: str) -> bytes:
        """Send a query and return the raw bytes (for binary responses)."""
        self._inst.write(cmd)
        return self._inst.read_raw()

    def read_binary_block(self) -> bytes:
        """Read an IEEE 488.2 definite-length block (#9<9digits><data>).

        USBTMC delivers the payload in ~512-byte transfers, and binary data may
        contain 0x0A bytes, so we disable newline termination and accumulate
        reads until the full declared byte count has been received.
        """
        old_term = self._inst.read_termination
        self._inst.read_termination = None
        try:
            data = bytearray()
            declared = None
            for _ in range(10000):
                chunk = self._inst.read_raw()
                data += chunk
                if declared is None:
                    i = data.find(b"#")
                    if i >= 0 and data[i + 1 : i + 2] == b"9":
                        declared = int(data[i + 2 : i + 11])
                    elif i >= 0 and data[i + 1 : i + 2] != b"9":
                        raise OscError(
                            f"Unexpected block header: {data[i:i+3]!r}"
                        )
                if declared is not None and len(data) >= declared + i + 11:
                    break
            if declared is None:
                return bytes(data)
            i = data.find(b"#")
            return bytes(data[i + 11 : i + 11 + declared])
        finally:
            self._inst.read_termination = old_term

    def query_float(self, cmd: str) -> float:
        # LeCroy responses embed units; extract the leading numeric token.
        return parse_float(self.query(cmd))

    def query_int(self, cmd: str) -> int:
        return int(parse_float(self.query(cmd)))

    def idn(self) -> str:
        return self.query("*IDN?")

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
    def get_waveform(self, channel: str = "C1", points: int = 0) -> dict:
        """Fetch a full waveform and return parsed descriptor + samples.

        Returns a dict with keys: gain, offset, horz_interval, horz_offset,
        samples (list of floats in volts), times (list of float seconds),
        first_valid, last_valid.
        """
        self.write("CHDR OFF")
        self.write(f"WFSU SP,0,NP,{points},FP,0")
        self.write(f"{channel}:WF? ALL")
        block = self.read_binary_block()
        self.write("CHDR SHORT")

        desc_len = struct.unpack("<i", block[36:40])[0]
        desc = block[:desc_len]

        def f32(off):
            return struct.unpack("<f", desc[off : off + 4])[0]

        def f64(off):
            return struct.unpack("<d", desc[off : off + 8])[0]

        def i32(off):
            return struct.unpack("<i", desc[off : off + 4])[0]

        vdiv = f32(156)  # VERTICAL_GAIN stores volts/div on this firmware
        offset = f32(160)
        horz_interval = f32(176)
        horz_offset = f64(180)
        wave_count = i32(116)
        first_valid = i32(124)
        last_valid = i32(128)
        array1_len = i32(60)

        data = block[desc_len : desc_len + array1_len]
        # 8-bit signed ADC codes span the 8-division grid: 256 codes / 8 div
        # = 32 codes per division, so volts = code * vdiv / 32.
        scale = vdiv / 32.0
        samples = [scale * (b if b < 128 else b - 256) - offset for b in data]
        times = [horz_interval * k + horz_offset for k in range(wave_count)]

        return {
            "vdiv": vdiv,
            "offset": offset,
            "horz_interval": horz_interval,
            "horz_offset": horz_offset,
            "wave_count": wave_count,
            "first_valid": first_valid,
            "last_valid": last_valid,
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
        raise OscError(
            f"Could not connect to the oscilloscope: {e}\n"
            "Check that it is powered on, connected via USB, and that the udev "
            "rule granting access is installed (see README)."
        ) from e
