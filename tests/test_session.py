import threading
import time

import pytest

from osc_cli.device import OscError, OscNotFoundError, OscTransportError
from siglent_mcp.session import ScopeBusy, Session
from tests.fakes import FakeOscilloscope


class Factory:
    """Hands out a new FakeOscilloscope per connection, optionally failing first."""

    def __init__(self, fail_first: Exception | None = None):
        self.created: list[FakeOscilloscope] = []
        self.fail_first = fail_first

    def __call__(self):
        if self.fail_first is not None:
            exc, self.fail_first = self.fail_first, None
            raise exc
        fake = FakeOscilloscope()
        self.created.append(fake)
        return fake


def flaky(failures: int, exc=OscTransportError("pipe")):
    calls = {"n": 0}

    def fn(o):
        calls["n"] += 1
        if calls["n"] <= failures:
            raise exc
        return "ok"

    return fn, calls


def test_connects_lazily_once_and_sets_short_headers():
    factory = Factory()
    session = Session(factory)
    assert factory.created == []
    session.run(lambda o: o.query("TDIV?"), retry=True)
    session.run(lambda o: o.query("TDIV?"), retry=True)
    assert len(factory.created) == 1
    assert factory.created[0].log[0] == ("w", "CHDR SHORT")


def test_transport_error_retries_on_new_connection():
    factory = Factory()
    fn, calls = flaky(1)
    assert Session(factory).run(fn, retry=True) == "ok"
    assert calls["n"] == 2
    assert len(factory.created) == 2
    assert factory.created[0].closed


def test_no_retry_when_not_idempotent():
    factory = Factory()
    fn, calls = flaky(1)
    with pytest.raises(OscTransportError) as info:
        Session(factory).run(fn, retry=False)
    assert calls["n"] == 1
    assert info.value.retried is False


def test_gives_up_after_one_retry():
    fn, calls = flaky(5)
    with pytest.raises(OscTransportError) as info:
        Session(Factory()).run(fn, retry=True)
    assert calls["n"] == 2
    assert info.value.retried is True


def test_protocol_errors_are_not_retried_and_keep_connection():
    factory = Factory()
    session = Session(factory)
    fn, calls = flaky(1, OscError("bad header"))
    with pytest.raises(OscError):
        session.run(fn, retry=True)
    session.run(lambda o: None, retry=True)
    assert calls["n"] == 1
    assert len(factory.created) == 1


def test_reconnects_on_next_call_after_failed_call():
    factory = Factory(fail_first=OscNotFoundError("No USBTMC device found."))
    session = Session(factory)
    with pytest.raises(OscNotFoundError):
        session.run(lambda o: None, retry=True)
    fn, _ = flaky(1)
    with pytest.raises(OscTransportError):
        session.run(fn, retry=False)  # cable pulled mid-call
    assert session.run(lambda o: "back", retry=True) == "back"
    assert len(factory.created) == 2


def test_restore_header_after_success_and_after_error():
    factory = Factory()
    session = Session(factory)
    session.run(lambda o: o.write("CHDR OFF"), retry=False, restore_header=True)
    assert factory.created[0].writes[-2:] == ["CHDR OFF", "CHDR SHORT"]

    def boom(o):
        o.write("CHDR LONG")
        raise OscError("rejected")

    with pytest.raises(OscError):
        session.run(boom, retry=False, restore_header=True)
    assert factory.created[0].writes[-1] == "CHDR SHORT"


def test_timeout_override_is_scoped_to_the_call():
    factory = Factory()
    session = Session(factory)
    seen = session.run(lambda o: o.timeout_ms, retry=False, timeout_ms=120000)
    assert seen == 120000
    assert factory.created[0].timeout_ms == 5000


def test_busy_when_lock_not_released_in_time():
    session = Session(Factory(), lock_timeout_s=0.05)
    started = threading.Event()

    def slow(o):
        started.set()
        time.sleep(0.3)

    t = threading.Thread(target=session.run, args=(slow,), kwargs={"retry": False})
    t.start()
    started.wait()
    with pytest.raises(ScopeBusy):
        session.run(lambda o: None, retry=True)
    t.join()


def test_concurrent_runs_are_serialized():
    session = Session(Factory())
    events = []

    def work(o, name):
        events.append(("enter", name))
        time.sleep(0.02)
        events.append(("exit", name))

    threads = [threading.Thread(target=session.run, args=(work, n), kwargs={"retry": False})
               for n in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for i in range(0, len(events), 2):
        assert events[i][0] == "enter" and events[i + 1] == ("exit", events[i][1])


def test_remember_mode_only_tracks_continuous_modes():
    session = Session(Factory())
    session.remember_mode("norm")
    session.remember_mode("SINGLE")
    session.remember_mode(None)
    assert session.last_continuous_mode == "NORM"


def test_close_disconnects():
    factory = Factory()
    session = Session(factory)
    session.run(lambda o: None, retry=True)
    session.close()
    assert factory.created[0].closed
