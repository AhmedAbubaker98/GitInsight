# tests/conftest.py
import pytest
import pytest_asyncio
import os
from fastapi import FastAPI
from httpx import AsyncClient
from starlette.middleware.sessions import SessionMiddleware

# Import the app from main.py
# To make this work, ensure your project root is in PYTHONPATH or use relative imports if structured as a package.
# For simplicity here, assuming direct import works if tests are run from project root.
from main import app as main_app, SESSION_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest_asyncio.fixture(scope="function")
async def test_app() -> FastAPI:
    # Configure a test-specific app if needed, or use the main app
    # For session middleware, ensure a secret key is set for tests
    if not SESSION_SECRET:
        raise ValueError("SESSION_SECRET must be set for tests (e.g., in a .env.test or os.environ)")

    # If you want to test with GitHub OAuth disabled for some tests:
    # You could patch GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET here or per test
    # For now, we assume they might be set or not, and tests will handle both.

    # The app instance from main.py should already have middleware.
    # If you were creating a new app instance here, you'd add it:
    # test_app_instance = FastAPI()
    # test_app_instance.add_middleware(SessionMiddleware, secret_key="test_secret")
    # ... add routes ...
    # return test_app_instance
    return main_app

@pytest_asyncio.fixture(scope="function")
async def client(test_app: FastAPI) -> AsyncClient:
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    # Ensure essential env vars are set for testing, can be overridden by actual .env
    monkeypatch.setenv("SESSION_SECRET", "test_super_secret_key_for_pytest")

    # For GitHub OAuth, tests can mock these or test paths where they are not set.
    # monkeypatch.setenv("GITHUB_CLIENT_ID", "test_github_id")
    # monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test_github_secret")

    # For Google API Key, it should always be mocked in analyzer tests.
    # monkeypatch.setenv("MY_GOOGLE_API_KEY", "test_google_api_key_will_be_mocked")
    pass

@pytest.fixture
def mock_user_session():
    return {"user": {"login": "testuser", "id": 123}, "github_token": "test_github_token"}