"""One persistent, lock-protected connection to the oscilloscope.

USBTMC handles one request at a time, so every tool call goes through
Session.run, which serializes access and reconnects after transport errors.
"""

from __future__ import annotations

import logging
import os
import threading

from osc_cli.device import OscTransportError, get_device
from osc_cli.ops.acquisition import CONTINUOUS_MODES

log = logging.getLogger(__name__)


class ScopeBusy(Exception):
    """Another call held the scope for longer than the lock timeout."""


def default_factory():
    resource = os.environ.get("OSC_RESOURCE") or None
    timeout_ms = int(os.environ.get("OSC_TIMEOUT_MS", "5000"))
    return get_device(resource, timeout_ms)


class Session:
    def __init__(self, factory=None, lock_timeout_s: float | None = None):
        self._factory = factory or default_factory
        if lock_timeout_s is None:
            lock_timeout_s = float(os.environ.get("OSC_LOCK_TIMEOUT_S", "120"))
        self._lock_timeout_s = lock_timeout_s
        self._lock = threading.Lock()
        self._osc = None
        self.last_continuous_mode: str | None = None

    def run(self, fn, *args, retry: bool, timeout_ms: int | None = None,
            restore_header: bool = False, **kwargs):
        """Call fn(osc, *args, **kwargs) holding the instrument lock.

        retry=True: after an OscTransportError, reconnect and call fn once
        more. Only for operations that are safe to repeat.
        restore_header=True: send CHDR SHORT afterwards (for *RST, setup
        recall and raw commands, which may change the header mode).
        """
        if not self._lock.acquire(timeout=self._lock_timeout_s):
            raise ScopeBusy(f"lock not acquired within {self._lock_timeout_s:g} s")
        try:
            attempts = 2 if retry else 1
            for attempt in range(1, attempts + 1):
                osc = None
                try:
                    osc = self._osc if self._osc is not None else self._connect()
                    result = self._call(osc, fn, args, kwargs, timeout_ms)
                except OscTransportError as exc:
                    log.warning("transport error (attempt %d/%d): %s", attempt, attempts, exc)
                    self._disconnect()
                    if attempt == attempts:
                        exc.retried = retry
                        raise
                    continue
                except Exception:
                    if restore_header and osc is not None:
                        self._restore_header(osc)
                    raise
                if restore_header:
                    self._restore_header(osc)
                return result
            raise AssertionError("unreachable")
        finally:
            self._lock.release()

    def remember_mode(self, mode: str | None) -> None:
        """Track the last continuous trigger mode so 'run' can return to it."""
        mode = (mode or "").upper()
        if mode in CONTINUOUS_MODES:
            self.last_continuous_mode = mode

    def close(self) -> None:
        with self._lock:
            self._disconnect()

    # ---- internals ------------------------------------------------------------
    def _connect(self):
        osc = self._factory()
        self._osc = osc
        osc.write("CHDR SHORT")
        return osc

    def _disconnect(self) -> None:
        if self._osc is not None:
            try:
                self._osc.close()
            except Exception:  # noqa: BLE001
                pass
            self._osc = None

    @staticmethod
    def _call(osc, fn, args, kwargs, timeout_ms):
        if timeout_ms:
            with osc.timeout(timeout_ms):
                return fn(osc, *args, **kwargs)
        return fn(osc, *args, **kwargs)

    def _restore_header(self, osc) -> None:
        try:
            osc.write("CHDR SHORT")
        except OscTransportError:
            self._disconnect()  # reconnecting sets CHDR SHORT again
