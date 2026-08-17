import pytest
import httpx


API_BASE_URL = "http://localhost:8000"


@pytest.fixture
def client():
    with httpx.Client(
        base_url=API_BASE_URL,
        timeout=120.0,
    ) as http_client:
        yield http_client