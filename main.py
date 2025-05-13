from services.parser import parse_repo
from services.github import (CloningError, URLParsingError, clone_repo,
                             parse_github_url)
from services.db_service import (get_analysis_by_id, get_analysis_history,
                                 get_db_session, init_db, log_analysis_request)
from services.db_service import engine as db_engine
from services.db_models import AnalysisHistory as DBAnalysisHistory_model
from services.analyzer import generate_summary_stream
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json
import logging  # Added for logging
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
# load_dotenv removed, handled by config.py
from pydantic import BaseModel, HttpUrl
from starlette.middleware.sessions import SessionMiddleware

# --- Configuration (Centralized) ---
from core.config import settings  # Import centralized settings

# --- Logging Setup ---
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Database Imports ---

# --- Service Imports ---
# Import custom exceptions from services

# from services.analyzer import AISummaryError # If _stream_analysis were to catch it directly

# --- Validate Critical Configurations ---
if not settings.SESSION_SECRET:
    # This case should ideally be caught by Pydantic during Settings instantiation
    # if the field is not Optional and has no default.
    logger.critical(
        "SESSION_SECRET environment variable not set. Please generate a strong secret key.")
    raise ValueError("SESSION_SECRET environment variable not set.")

if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
    logger.warning(
        "GitHub OAuth credentials (GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET) not found. Login feature will be disabled.")

# --- Lifespan for DB connection ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if settings.MY_DATABASE_URL:
        logger.info(
            "MY_DATABASE_URL is set, attempting to initialize database...")
        await init_db()
    else:
        logger.warning(
            "MY_DATABASE_URL not set, database features (history) will be disabled.")
    yield
    # Shutdown
    if db_engine:
        logger.info("Disposing database connection pool...")
        await db_engine.dispose()
        logger.info("Database connection pool disposed.")

# --- App Setup ---
app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET,
                   https_only=False)  # Use settings

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

oauth = OAuth()
if settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET:
    oauth.register(
        name='github',
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'read:user user:email repo'},
    )
else:
    logger.info(
        "GitHub OAuth is not configured as GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET are missing.")


# --- Pydantic Models ---
class RepoRequest(BaseModel):
    url: str
    lang: str = "en"
    size: str = "medium"
    technicality: str = "technical"

# --- Helper Functions ---


async def get_user(request: Request) -> dict | None:
    return request.session.get("user")


async def get_token(request: Request) -> str | None:
    return request.session.get("github_token")

# --- Routes ---


@app.get("/", response_class=HTMLResponse)
async def route_root(request: Request, user: dict | None = Depends(get_user)):
    db_enabled = bool(settings.MY_DATABASE_URL)
    if user:
        return templates.TemplateResponse("app.html", {"request": request, "user": user, "is_guest": False, "db_enabled": db_enabled})
    return templates.TemplateResponse("index.html", {"request": request, "github_enabled": bool(settings.GITHUB_CLIENT_ID)})


@app.get("/guest", response_class=HTMLResponse)
async def route_guest_mode(request: Request):
    if "user" in request.session or "github_token" in request.session:
        request.session.pop("user", None)
        request.session.pop("github_token", None)
        logger.info("Entered Guest Mode: Cleared active session tokens.")
    else:
        logger.info("Entered Guest Mode: No active session tokens to clear.")
    return templates.TemplateResponse("app.html", {"request": request, "user": None, "is_guest": True, "db_enabled": False})


@app.get("/login/github")
async def login_with_github(request: Request):
    if not settings.GITHUB_CLIENT_ID:
        logger.warning(
            "GitHub login attempt failed: GitHub OAuth not configured.")
        return RedirectResponse("/?error=GitHub%20Login%20is%20not%20configured")
    redirect_uri = request.url_for("auth_github")
    logger.info(f"Initiating GitHub login. Redirect URI: {redirect_uri}")
    return await oauth.github.authorize_redirect(request, redirect_uri)


@app.get("/auth/github")
async def auth_github(request: Request):
    if not settings.GITHUB_CLIENT_ID:
        logger.error("GitHub auth callback received but OAuth not configured.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="GitHub Login is not configured")
    try:
        if "error" in request.query_params:
            error = request.query_params.get("error", "Unknown error")
            error_desc = request.query_params.get(
                "error_description", "Authorization failed.")
            logger.warning(
                f"GitHub OAuth error during authorization: {error} - {error_desc}")
            return RedirectResponse(f"/?error={error_desc}")

        token_data = await oauth.github.authorize_access_token(request)
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error(
                "GitHub OAuth error: Access token not found in GitHub response.")
            return RedirectResponse("/?error=Failed%20to%20retrieve%20access%20token")

        resp = await oauth.github.get("user", token={'access_token': access_token})
        resp.raise_for_status()
        profile = resp.json()

        request.session["user"] = profile
        request.session["github_token"] = access_token
        logger.info(
            f"User {profile.get('login')} logged in successfully via GitHub.")
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    except OAuthError as e:
        logger.error(
            f"OAuth Error during GitHub authentication: {e.error} - {e.description}", exc_info=True)
        return RedirectResponse(f"/?error=OAuth%20Error:%20{e.description or e.error}")
    except Exception as e:
        logger.error(
            f"Unexpected error during GitHub auth: {e}", exc_info=True)
        return RedirectResponse("/?error=An%20unexpected%20error%20occurred%20during%20login")


@app.get("/logout")
async def logout(request: Request):
    user_login = request.session.get("user", {}).get("login", "Unknown user")
    request.session.pop("user", None)
    request.session.pop("github_token", None)
    logger.info(f"User {user_login} logged out.")
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


# --- Analysis Stream Helper ---
async def _stream_analysis(
    repo_url: str,
    lang: str,
    size: str,
    technicality: str,
    token: str | None,
    user_github_id: Optional[str],
    db_session: Optional[AsyncSession]
) -> AsyncGenerator[str, None]:
    local_repo_path = None
    final_summary_str = None
    error_from_analyzer = False
    analysis_params_for_log = {"url": repo_url, "lang": lang, "size": size,
                               "technicality": technicality, "user": user_github_id or "guest"}

    logger.info(f"Starting analysis for: {analysis_params_for_log}")
    try:
        # 1. Validate URL
        yield json.dumps({"status": "Validating URL...", "step": 1, "total_steps": 4}) + "\n"
        await asyncio.sleep(0.1)  # Simulate work
        try:
            owner, repo_name = parse_github_url(repo_url)
            logger.info(f"Validated URL for {owner}/{repo_name}")
        except URLParsingError as e:
            logger.warning(f"Invalid GitHub URL '{repo_url}': {e}")
            yield json.dumps({"error": f"Invalid GitHub URL: {e}", "step": 1}) + "\n"
            return

        # 2. Clone Repository
        yield json.dumps({"status": f"Cloning {owner}/{repo_name}...", "step": 2, "total_steps": 4}) + "\n"
        try:
            local_repo_path = await asyncio.to_thread(clone_repo, repo_url, token)
            logger.info(
                f"Cloned repository {owner}/{repo_name} to: {local_repo_path}")
        except CloningError as e:
            logger.error(
                f"Error cloning repository '{repo_url}': {e}", exc_info=settings.LOG_LEVEL.upper() == "DEBUG")
            yield json.dumps({"error": str(e), "step": 2}) + "\n"
            return
        except Exception as e:  # Catch other unexpected errors during cloning
            logger.error(
                f"Unexpected error during cloning of '{repo_url}': {e}", exc_info=True)
            yield json.dumps({"error": f"Error during cloning: {type(e).__name__}: {e}", "step": 2}) + "\n"
            return

        # 3. Parse Repository
        yield json.dumps({"status": "Parsing repository files...", "step": 3, "total_steps": 4}) + "\n"
        try:
            parsed_content = await asyncio.to_thread(parse_repo, local_repo_path)
            text_parts = [f"# {k}\n{v}" for k, v in parsed_content.get("important", {}).items()] + \
                         [f"# {f['path']}\n{f['content']}" for f in parsed_content.get(
                             "source_files", [])]
            full_text = "\n\n".join(text_parts)
            if not full_text.strip():
                logger.warning(
                    f"No relevant text content found in repository '{repo_url}' at {local_repo_path}")
                yield json.dumps({"error": "No relevant text content found in the repository.", "step": 3}) + "\n"
                return
            logger.info(
                f"Parsed repository {owner}/{repo_name}, total text length: {len(full_text)}")
        except Exception as e:  # Catch errors from parse_repo or text processing
            logger.error(
                f"Error during parsing repository '{repo_url}': {e}", exc_info=True)
            yield json.dumps({"error": f"Error during parsing: {type(e).__name__}: {e}", "step": 3}) + "\n"
            return

        # 4. Generate Summary
        yield json.dumps({"status": "Generating summary with AI...", "step": 4, "total_steps": 4}) + "\n"
        try:
            async for item in generate_summary_stream(full_text, lang=lang, size=size, technicality=technicality):
                if isinstance(item, dict):
                    yield json.dumps(item) + "\n"
                    if "error" in item:
                        logger.warning(
                            f"Error from AI analyzer for '{repo_url}': {item['error']}")
                        error_from_analyzer = True
                        return  # Error already yielded by analyzer stream
                elif isinstance(item, str):
                    final_summary_str = item  # This is the final summary

            if final_summary_str and not error_from_analyzer:
                yield json.dumps({"summary": final_summary_str, "status": "Completed!", "step": 4}) + "\n"
                logger.info(f"Successfully generated summary for {repo_url}")
                if db_session and user_github_id and settings.MY_DATABASE_URL:
                    try:
                        params_for_db = {
                            "lang": lang, "size": size, "technicality": technicality}
                        await log_analysis_request(
                            db=db_session,
                            user_github_id=user_github_id,
                            repository_url=repo_url,
                            parameters_used=params_for_db,
                            summary_content=final_summary_str
                        )
                        # log_analysis_request already logs success/failure
                    except Exception as db_exc:
                        logger.error(
                            f"Database logging error for user {user_github_id}, repo {repo_url}: {db_exc}", exc_info=True)
                        # Non-critical, don't yield error to client for this
            elif not error_from_analyzer:  # No summary string but no explicit error from analyzer
                logger.error(
                    f"Summary generation for {repo_url} finished, but no summary content was produced by AI.")
                yield json.dumps({"error": "Summary generation finished, but no summary content was produced.", "step": 4}) + "\n"

        except Exception as e:  # Errors from iterating generate_summary_stream or logic here
            logger.error(
                f"Error processing AI summary stream for '{repo_url}': {e}", exc_info=True)
            yield json.dumps({"error": f"Error processing summary stream: {type(e).__name__}: {e}", "step": 4}) + "\n"
            return

    except Exception as e:  # Catch-all for unexpected errors in _stream_analysis
        logger.critical(
            f"An unexpected error occurred during analysis of '{repo_url}': {e}", exc_info=True)
        yield json.dumps({"error": f"An unexpected server error occurred: {type(e).__name__}"}) + "\n"
    finally:
        if local_repo_path and os.path.exists(local_repo_path):
            try:
                await asyncio.to_thread(shutil.rmtree, local_repo_path)
                logger.info(
                    f"Cleaned up temporary directory: {local_repo_path}")
            except Exception as e:
                logger.error(
                    f"Error cleaning up temporary directory {local_repo_path}: {e}", exc_info=True)
        logger.info(f"Finished analysis stream for: {analysis_params_for_log}")


# --- API Endpoint ---
@app.post("/analyze/repo")
async def analyze_repo_endpoint(
    request_data: RepoRequest,
    request: Request,
    db: Optional[AsyncSession] = Depends(get_db_session)
):
    user_profile = await get_user(request)
    user_token = await get_token(request)
    user_github_id = str(
        user_profile["id"]) if user_profile and "id" in user_profile else None

    if not user_profile:
        logger.info(
            f"Analysis request from guest user for URL: {request_data.url}. History will not be saved.")
    elif user_github_id:
        logger.info(
            f"Analysis request from user: {user_profile.get('login', 'Unknown')} (ID: {user_github_id}) for URL: {request_data.url}")

    effective_db_session = db if settings.MY_DATABASE_URL and db else None
    if user_profile and not effective_db_session and settings.MY_DATABASE_URL:
        logger.warning(
            f"User {user_github_id} is logged in, MY_DATABASE_URL is set, but no DB session available for history logging.")

    return StreamingResponse(
        _stream_analysis(
            repo_url=request_data.url,
            lang=request_data.lang,
            size=request_data.size,
            technicality=request_data.technicality,
            token=user_token,
            user_github_id=user_github_id,
            db_session=effective_db_session
        ),
        media_type="application/x-ndjson"
    )

# --- History Pydantic Models ---


class AnalysisHistoryItemBase(BaseModel):
    id: int
    repository_url: str
    timestamp: datetime
    parameters_used: Dict[str, Any]

    class Config:
        orm_mode = True  # Pydantic V1, for V2 use from_attributes = True


class AnalysisHistoryItem(AnalysisHistoryItemBase):
    pass


class AnalysisHistoryDetail(AnalysisHistoryItemBase):
    summary_content: Optional[str]

# --- History API Endpoints ---


@app.get("/history", response_model=List[AnalysisHistoryItem])
async def get_user_history_endpoint(
    request: Request,
    user: dict | None = Depends(get_user),
    db: Optional[AsyncSession] = Depends(get_db_session)
):
    if not settings.MY_DATABASE_URL:
        logger.warning(
            "Attempt to access history endpoint but MY_DATABASE_URL is not configured.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="History service is not configured.")
    if not user:
        logger.info("Unauthorized attempt to access history endpoint.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not db:  # Should be caught by the MY_DATABASE_URL check if db_service behaves as expected
        logger.error(
            "History endpoint: Database connection not available despite MY_DATABASE_URL being set.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database connection not available.")

    user_github_id = str(user.get("id"))
    if not user_github_id:  # Should not happen if user object is valid
        logger.error(
            f"User {user.get('login')} has no 'id' field in session for history.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="User ID not found in session.")

    logger.debug(f"Fetching history for user_id: {user_github_id}")
    history_records = await get_analysis_history(db, user_github_id)
    return history_records


@app.get("/history/{history_id}", response_model=AnalysisHistoryDetail)
async def get_history_item_detail_endpoint(
    history_id: int,
    request: Request,
    user: dict | None = Depends(get_user),
    db: Optional[AsyncSession] = Depends(get_db_session)
):
    if not settings.MY_DATABASE_URL:
        logger.warning(
            f"Attempt to access history item {history_id} but MY_DATABASE_URL is not configured.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="History service is not configured.")
    if not user:
        logger.info(
            f"Unauthorized attempt to access history item {history_id}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not db:
        logger.error(
            f"History item {history_id}: Database connection not available despite MY_DATABASE_URL being set.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database connection not available.")

    user_github_id = str(user.get("id"))
    if not user_github_id:
        logger.error(
            f"User {user.get('login')} has no 'id' field in session for history item {history_id}.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="User ID not found in session.")

    logger.debug(
        f"Fetching history item id: {history_id} for user_id: {user_github_id}")
    history_item = await get_analysis_by_id(db, history_id, user_github_id)
    if not history_item:
        logger.warning(
            f"History item id: {history_id} not found or access denied for user_id: {user_github_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="History item not found or access denied.")
    return history_item


@app.get("/me")  # Example endpoint, can be removed if not used
async def read_users_me(user: dict | None = Depends(get_user)):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

# --- Run Server (for development) ---
if __name__ == "__main__":
    import uvicorn
    logger.info(
        f"Starting Uvicorn server on 0.0.0.0:8000 with log level {settings.LOG_LEVEL.upper()}")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
