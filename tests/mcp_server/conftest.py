import pytest

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from siglent_mcp.server import create_server  # noqa: E402
from siglent_mcp.session import Session  # noqa: E402
from siglent_mcp.storage import Storage  # noqa: E402
from tests.fakes import FakeOscilloscope  # noqa: E402


@pytest.fixture
def fake():
    return FakeOscilloscope()


@pytest.fixture
def storage(tmp_path):
    return Storage(root=tmp_path / "data", keep=3)


@pytest.fixture
def server(fake, storage):
    return create_server(session=Session(lambda: fake), storage=storage, max_samples=2_000_000)


@pytest.fixture
async def client(server):
    async with Client(server) as c:
        yield c


async def call(client, name, **arguments):
    """Call a tool and fail the test with the tool's message if it errored."""
    result = await client.call_tool(name, arguments)
    assert not result.is_error, result.content[0].text
    return result
