import tempfile
from pathlib import Path

try:
    from contextlib import asynccontextmanager
except ImportError:
    from async_generator import asynccontextmanager

import pytest
import tus
from aiohttp import web
from aiohttp.test_utils import TestClient

from aiohttp_tus import setup_tus
from aiohttp_tus.constants import APP_TUS_CONFIG_KEY
from aiohttp_tus.data import TusConfig


TEST_DATA_PATH = Path(__file__).parent / "test-data"


@pytest.fixture
def aiohttp_test_client(aiohttp_client):
    @asynccontextmanager
    async def factory(*, upload_url: str, upload_suffix: str = None) -> TestClient:
        with tempfile.TemporaryDirectory(prefix="aiohttp_tus") as temp_path:
            base_path = Path(temp_path)
            app = setup_tus(
                web.Application(),
                upload_path=base_path / upload_suffix if upload_suffix else base_path,
                upload_url=upload_url,
            )
            yield await aiohttp_client(app)

    return factory


@pytest.mark.parametrize(
    "upload_url, upload_suffix, tus_upload_url, match_info",
    (
        ("/uploads", None, "/uploads", {}),
        (r"/user/{username}/uploads", None, "/user/playpauseanddtop/uploads", {}),
        (
            r"/user/{username}/uploads",
            r"{username}",
            "/user/playpauseandstop/uploads",
            {"username": "playpauseandstop"},
        ),
    ),
)
async def test_upload(
    aiohttp_test_client, loop, upload_url, upload_suffix, tus_upload_url, match_info,
):
    async with aiohttp_test_client(
        upload_url=upload_url, upload_suffix=upload_suffix
    ) as client:
        upload_url = f"http://{client.host}:{client.port}{tus_upload_url}"
        test_upload_path = TEST_DATA_PATH / "hello.txt"

        with open(test_upload_path, "rb") as handler:
            await loop.run_in_executor(None, tus.upload, handler, upload_url)

        config: TusConfig = client.app[APP_TUS_CONFIG_KEY]
        expected_upload_path = config.resolve_upload_path(match_info) / "hello.txt"
        assert expected_upload_path.exists()
        assert expected_upload_path.read_bytes() == test_upload_path.read_bytes()
