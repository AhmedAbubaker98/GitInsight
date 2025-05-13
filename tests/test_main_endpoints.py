# tests/test_main_endpoints.py
import asyncio  # For asyncio.sleep if used in the stream
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

# --- Test Root and Guest Endpoints ---


@pytest.mark.asyncio
async def test_route_root_no_user(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert "Welcome to GitInsight" in response.text  # From index.html
    # Assuming GITHUB_CLIENT_ID is not set or mocked as such
    assert "Login with GitHub" in response.text


@pytest.mark.asyncio
async def test_route_root_with_user(client: AsyncClient, mock_user_session):
    # Simulate a logged-in user by setting session cookies
    # A more robust way is to patch `get_user` dependency for the route.
    with patch("main.get_user", return_value=mock_user_session["user"]):
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK
        assert "Analyze a GitHub Repository" in response.text  # From app.html
        assert f"Welcome, {mock_user_session['user']['login']}!" in response.text


@pytest.mark.asyncio
async def test_route_guest_mode(client: AsyncClient):
    # First, set some session data to test if it gets cleared
    async with AsyncClient(
        base_url="http://test",
        cookies={"some_session_cookie": "value"}
    ) as temp_client:
        # Patch session access for this specific test
        mock_session = {"user": {"login": "olduser"},
                        "github_token": "oldtoken"}

        async def mock_request_session_get(key, default=None):
            return mock_session.get(key, default)

        async def mock_request_session_pop(key, default=None):
            return mock_session.pop(key, default)

        with patch("fastapi.Request.session", new_callable=MagicMock) as mock_req_session_attr:
            # Configure the mock_req_session_attr to behave like a dictionary for get and pop
            # This is a simplification. Real SessionMiddleware interaction is more complex.
            # For this test, let's assume the print statements in the route are indicative enough
            # or we check the template context.
            # No direct way to inject session here for clearing check easily
            response = await temp_client.get("/guest")

    # For the actual response check, use the standard client
    response = await client.get("/guest")
    assert response.status_code == status.HTTP_200_OK
    assert "Analyze a GitHub Repository" in response.text  # app.html
    assert "Guest Mode" in response.text
    assert "Login with GitHub" in response.text  # Link to go back to login

# --- Test Auth Endpoints ---


@pytest.mark.asyncio
async def test_login_github_redirect(client: AsyncClient, monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test_id")  # Ensure it's "enabled"
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test_secret")
    # We need to re-register oauth if it's done at import time in main.py
    # This is a bit tricky. A better design would be to have oauth setup within a lifespan event or factory.
    # For now, let's assume the test_app fixture in conftest correctly re-initializes or patches `main.oauth`.

    # Mock the oauth client's authorize_redirect
    with patch("main.oauth.github.authorize_redirect", new_callable=AsyncMock) as mock_auth_redirect:
        mock_auth_redirect.return_value = MagicMock(status_code=302, headers={
                                                    "location": "https://github.com/login/oauth/authorize?..."})
        response = await client.get("/login/github")
        # Or whatever mock_auth_redirect returns
        assert response.status_code == status.HTTP_302_FOUND
        mock_auth_redirect.assert_called_once()
        assert "github.com/login/oauth/authorize" in response.headers["location"]


@pytest.mark.asyncio
async def test_login_github_not_configured(client: AsyncClient, monkeypatch):
    # Ensure it's "disabled"
    monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
    response = await client.get("/login/github")
    assert response.status_code == status.HTTP_302_FOUND  # Redirects to root with error
    assert "error=GitHub%20Login%20is%20not%20configured" in response.headers["location"]


@pytest.mark.asyncio
async def test_auth_github_success(client: AsyncClient, monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test_id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test_secret")

    mock_token_data = {
        "access_token": "fake_github_access_token", "token_type": "bearer"}
    mock_user_profile = {"login": "testuser", "id": 12345, "name": "Test User"}

    with patch("main.oauth.github.authorize_access_token", AsyncMock(return_value=mock_token_data)) as mock_auth_token, \
            patch("main.oauth.github.get", AsyncMock()) as mock_oauth_get:
        # Mock the response from oauth.github.get("user", ...)
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = mock_user_profile
        mock_user_response.raise_for_status = MagicMock()  # Does nothing if status is OK
        mock_oauth_get.return_value = mock_user_response

        response = await client.get("/auth/github?code=somecode")
        # Need to follow redirects to check session
        # The client needs to handle cookies for session to persist across redirects
        # By default, AsyncClient does not store cookies across requests unless you manage them.
        # Let's check the immediate redirect and assume session is set.
        assert response.status_code == status.HTTP_302_FOUND
        assert response.headers["location"] == "/"  # Redirects to root

        # To properly test session:
        # 1. Use `client.cookies` if the client supports it across redirects (httpx.AsyncClient does)
        # 2. Or, make a subsequent request and check if the user is logged in (e.g., to `/me` or `/`)

        # Follow up request to check session (requires client to handle cookies)
        # We need to use a client instance that persists cookies
        async with AsyncClient(
            base_url="http://test",
            follow_redirects=False
        ) as session_client:
            # This sets the session cookie
            auth_response = await session_client.get("/auth/github?code=somecode")
            assert auth_response.status_code == status.HTTP_302_FOUND

            # Now make a request to an endpoint that uses the session
            root_response = await session_client.get("/", cookies=auth_response.cookies)
            assert root_response.status_code == status.HTTP_200_OK
            assert f"Welcome, {mock_user_profile['login']}" in root_response.text


@pytest.mark.asyncio
async def test_auth_github_oauth_error(client: AsyncClient, monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test_id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test_secret")
    from authlib.integrations.starlette_client import OAuthError

    with patch("main.oauth.github.authorize_access_token", AsyncMock(side_effect=OAuthError(error="access_denied", description="User denied access"))) as mock_auth_token:
        response = await client.get("/auth/github?code=somecode")
        assert response.status_code == status.HTTP_302_FOUND
        assert "error=OAuth%20Error:%20User%20denied%20access" in response.headers["location"]


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, mock_user_session):
    # To test logout, we first need a "logged-in" state.
    # This is tricky with stateless test client. We'll assume the session pop works.
    # We can patch `request.session.pop` or check the redirect.
    # A simplified way: just call logout and check redirect.
    # To verify session clearing, you'd need a request that sets session, then logout, then a request that checks.
    # Simulate being logged in
    response = await client.get("/logout", cookies={"session": "fake_session_id"})
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/"
    # To truly verify, you'd need to check that a subsequent request to a protected route is denied or shows guest view.


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, mock_user_session):
    with patch("main.get_user", return_value=mock_user_session["user"]):
        response = await client.get("/me")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["login"] == mock_user_session["user"]["login"]


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    with patch("main.get_user", return_value=None):  # Ensure get_user returns None
        response = await client.get("/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

# --- Test Analysis Endpoint ---


@pytest.mark.asyncio
@patch("main._stream_analysis")  # Mock the core analysis stream generator
async def test_analyze_repo_endpoint_success(mock_stream_analysis: AsyncMock, client: AsyncClient, mock_user_session):
    repo_url = "https://github.com/test/repo"

    # Define what the mock stream should yield
    async def mock_stream_generator(*args, **kwargs):
        yield json.dumps({"status": "Cloning...", "step": 1, "total_steps": 3}) + "\n"
        await asyncio.sleep(0.01)  # Simulate async work
        yield json.dumps({"status": "Parsing...", "step": 2, "total_steps": 3}) + "\n"
        await asyncio.sleep(0.01)
        yield json.dumps({"summary": "This is a mock summary.", "status": "Completed!", "step": 3, "total_steps": 3}) + "\n"
    mock_stream_analysis.side_effect = mock_stream_generator

    # Simulate logged-in user for token
    with patch("main.get_token", AsyncMock(return_value=mock_user_session["github_token"])), \
            patch("main.get_user", AsyncMock(return_value=mock_user_session["user"])):
        response = await client.post("/analyze/repo", json={
            "url": repo_url,
            "lang": "en",
            "size": "medium",
            "technicality": "technical"
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/x-ndjson"

        # Consume the streaming response
        content_chunks = []
        async for line in response.aiter_lines():
            content_chunks.append(json.loads(line))

        assert len(content_chunks) == 3
        assert content_chunks[0]["status"] == "Cloning..."
        assert content_chunks[1]["status"] == "Parsing..."
        assert content_chunks[2]["summary"] == "This is a mock summary."

        mock_stream_analysis.assert_called_once()
        call_args = mock_stream_analysis.call_args[0]
        assert call_args[0] == repo_url  # repo_url
        assert call_args[4] == mock_user_session["github_token"]  # token


@pytest.mark.asyncio
@patch("main._stream_analysis")
async def test_analyze_repo_endpoint_guest(mock_stream_analysis: AsyncMock, client: AsyncClient):
    repo_url = "https://github.com/public/repo"

    async def mock_stream_generator_guest(*args, **kwargs):
        assert kwargs.get("token") is None  # Assert token is None for guest
        yield json.dumps({"status": "Validating URL...", "step": 1, "total_steps": 4}) + "\n"
        yield json.dumps({"summary": "Guest summary.", "status": "Completed!", "step": 4}) + "\n"
    mock_stream_analysis.side_effect = mock_stream_generator_guest

    # Simulate guest user (no token, no user in session)
    with patch("main.get_token", AsyncMock(return_value=None)), \
            patch("main.get_user", AsyncMock(return_value=None)):
        # Minimal valid payload
        response = await client.post("/analyze/repo", json={"url": repo_url})
        assert response.status_code == status.HTTP_200_OK

        content_chunks = []
        async for line in response.aiter_lines():
            content_chunks.append(json.loads(line))

        assert any(chunk.get("summary") ==
                   "Guest summary." for chunk in content_chunks)
        mock_stream_analysis.assert_called_once()
        assert mock_stream_analysis.call_args[0][0] == repo_url
        # Check token argument specifically
        assert mock_stream_analysis.call_args[1]['token'] is None


@pytest.mark.asyncio
async def test_analyze_repo_invalid_payload(client: AsyncClient):
    # Invalid field name
    response = await client.post("/analyze/repo", json={"urll": "missing_url_field"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

# --- Test _stream_analysis (Integration-style for the orchestrator) ---
# This is more complex to unit test in full isolation as it calls other async functions.
# Mocking each sub-call (parse_github_url, clone_repo, parse_repo, generate_summary_stream) is key.


@pytest.mark.asyncio
async def test_stream_analysis_full_flow_success():
    from main import \
        _stream_analysis  # Import here to avoid issues with module-level mocks if any
    repo_url = "https://github.com/fake/repo"
    mock_local_path = "/tmp/fake_repo_path_123"

    with patch("main.parse_github_url", return_value=("fake", "repo")) as mock_parse_gh_url, \
            patch("main.clone_repo", AsyncMock(return_value=mock_local_path)) as mock_clone, \
            patch("main.parse_repo", AsyncMock(return_value={
                "important": {"README.md": "Test Readme"},
                "source_files": [{"path": "main.py", "content": "print(1)"}]
            })) as mock_parse_contents, \
            patch("main.generate_summary_stream", new_callable=AsyncMock) as mock_gen_summary, \
            patch("main.shutil.rmtree", MagicMock()) as mock_rmtree, \
            patch("main.os.path.exists", MagicMock(return_value=True)) as mock_exists:

        # Ensure cleanup path is tested
        async def summary_gen_mock(*args, **kwargs):
            yield {"status": "AI processing...", "component": "analyzer"}
            yield " Final Summary HTML "
        mock_gen_summary.side_effect = summary_gen_mock

        results = []
        async for item_json_str in _stream_analysis(repo_url, "en", "medium", "technical", "fake_token"):
            results.append(json.loads(item_json_str))

        # Validate, Clone, Parse, AI Status, AI Result
        assert len(results) >= 5
        # Check for key steps
        assert any(r.get("status") == "Validating URL..." for r in results)
        assert any(r.get("status")
                   and "Cloning fake/repo..." in r["status"] for r in results)
        assert any(r.get("status") ==
                   "Parsing repository files..." for r in results)
        assert any(r.get("status") ==
                   "Generating summary with AI..." for r in results)
        assert any(r.get("status") == "AI processing..." and r.get(
            "component") == "analyzer" for r in results)
        assert any(r.get("summary") == " Final Summary HTML " for r in results)

        mock_parse_gh_url.assert_called_with(repo_url)
        mock_clone.assert_called_with(repo_url, "fake_token")
        mock_parse_contents.assert_called_with(mock_local_path)
        # Check that the text passed to generate_summary_stream is correct
        expected_full_text = "# README.md\nTest Readme\n\n# main.py\nprint(1)"
        mock_gen_summary.assert_called_once()
        # full_text argument
        assert mock_gen_summary.call_args[0][0] == expected_full_text
        mock_exists.assert_called_with(mock_local_path)
        mock_rmtree.assert_called_with(mock_local_path)


@pytest.mark.asyncio
async def test_stream_analysis_clone_error():
    from main import _stream_analysis
    repo_url = "https://github.com/fail/clone"

    with patch("main.parse_github_url", return_value=("fail", "clone")), \
            patch("main.clone_repo", AsyncMock(side_effect=RuntimeError("Cloning failed badly"))) as mock_clone, \
            patch("main.shutil.rmtree"), \
            patch("main.os.path.exists", return_value=False):  # Assume dir not created or cleaned before error
        results = []
        async for item_json_str in _stream_analysis(repo_url, "en", "medium", "technical", None):
            results.append(json.loads(item_json_str))

        assert any(r.get("error") == "Cloning failed badly" and r.get(
            "step") == 2 for r in results)
        mock_clone.assert_called_once()
