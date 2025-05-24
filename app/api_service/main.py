import logging
import json
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import os
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth, OAuthError
from redis import Redis
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import settings
from .services.db.db_service import (
    init_db, get_db_session, create_analysis_history,
    get_analysis_by_id_for_user, get_analysis_history_for_user, engine as db_engine
)
from .services.db.db_models import AnalysisHistoryItem, AnalysisHistoryDetail, AnalysisStatus # Pydantic models for response

# --- Logging Setup ---
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Global Variables ---
redis_conn = None
repo_processing_q = None
# result_q is handled by the worker process started by start.sh

# --- Lifespan for DB and Redis connections ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_conn, repo_processing_q
    # Startup
    if settings.MY_DATABASE_URL:
        logger.info("API Service: Initializing database...")
        await init_db()
    else:
        logger.warning("API Service: MY_DATABASE_URL not set, DB features disabled.")

    try:
        logger.info(f"API Service: Connecting to Redis at {settings.REDIS_URL}...")
        redis_conn = Redis.from_url(str(settings.REDIS_URL))
        redis_conn.ping() # Check connection
        repo_processing_q = Queue(settings.REPO_PROCESSING_QUEUE, connection=redis_conn)
        # ai_analysis_q = Queue(settings.AI_ANALYSIS_QUEUE, connection=redis_conn) # Not directly used by API
        logger.info("API Service: Connected to Redis and queues initialized.")
    except Exception as e:
        logger.critical(f"API Service: Failed to connect to Redis or initialize queues: {e}", exc_info=True)
        redis_conn = None # Ensure it's None if connection failed
        # App might still run but task queuing will fail. Consider raising to stop app.

    yield
    # Shutdown
    if db_engine:
        logger.info("API Service: Disposing database connection pool...")
        await db_engine.dispose()
    if redis_conn:
        logger.info("API Service: Closing Redis connection...")
        redis_conn.close()

# --- App Setup ---
APP_DIR = os.path.dirname(os.path.abspath(__file__)) # <--- Add this line (resolves to /app/api_service)

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)
app.mount("/static", StaticFiles(directory=os.path.join(APP_DIR, "static")), name="static") # <--- Modified
templates = Jinja2Templates(directory=os.path.join(APP_DIR, "templates")) # <--- Modified

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
    logger.warning("API Service: GitHub OAuth not configured.")

# --- Pydantic Models ---
class AnalyzeRepoRequest(BaseModel):
    url: HttpUrl # Use HttpUrl for basic validation
    lang: str = "en"
    size: str = "medium"
    technicality: str = "technical"
class AnalysisStatusResponse(BaseModel):
    """Response model for analysis status information."""
    analysis_id: int
    status: AnalysisStatus
    repository_url: str
    parameters_used: Dict[str, Any]
    summary_content: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime
    updated_at: datetime
    updated_at: datetime


# --- Helper Functions ---
async def get_current_user(request: Request) -> Optional[Dict]:
    return request.session.get("user")

async def get_github_token(request: Request) -> Optional[str]:
    return request.session.get("github_token")

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def route_root(request: Request, user: Optional[dict] = Depends(get_current_user)):
    db_enabled = bool(settings.MY_DATABASE_URL)
    if user:
        return templates.TemplateResponse("app.html", {"request": request, "user": user, "is_guest": False, "db_enabled": db_enabled})
    return templates.TemplateResponse("index.html", {"request": request, "github_enabled": bool(settings.GITHUB_CLIENT_ID)})

@app.get("/guest", response_class=HTMLResponse)
async def route_guest_mode(request: Request):
    request.session.pop("user", None)
    request.session.pop("github_token", None)
    return templates.TemplateResponse("app.html", {"request": request, "user": None, "is_guest": True, "db_enabled": False})

@app.get("/login/github")
async def login_with_github(request: Request):
    if not oauth.github:
        logger.warning("GitHub login attempt failed: OAuth not configured.")
        return RedirectResponse("/?error=GitHub%20Login%20is%20not%20configured")
    redirect_uri = request.url_for("auth_github")
    return await oauth.github.authorize_redirect(request, redirect_uri)

@app.get("/auth/github")
async def auth_github(request: Request):
    if not oauth.github:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GitHub Login not configured")
    try:
        token_data = await oauth.github.authorize_access_token(request)
        access_token = token_data.get("access_token")
        resp = await oauth.github.get("user", token={'access_token': access_token})
        resp.raise_for_status()
        profile = resp.json()
        request.session["user"] = profile
        request.session["github_token"] = access_token
        logger.info(f"User {profile.get('login')} logged in via GitHub.")
        return RedirectResponse(url="/app", status_code=status.HTTP_302_FOUND) # Redirect to /app
    except OAuthError as e:
        logger.error(f"OAuth Error: {e.error} - {e.description}", exc_info=True)
        return RedirectResponse(f"/?error=OAuth%20Error:%20{e.description or e.error}")
    except Exception as e:
        logger.error(f"Unexpected error during GitHub auth: {e}", exc_info=True)
        return RedirectResponse("/?error=An%20unexpected%20error%20occurred")

@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    request.session.pop("github_token", None)
    logger.info("User logged out.")
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@app.get("/app", response_class=HTMLResponse) # New route for main app page
async def route_app(request: Request, user: Optional[dict] = Depends(get_current_user)):
    db_enabled = bool(settings.MY_DATABASE_URL)
    is_guest = not user
    if is_guest and "user" not in request.session: # Ensure guest status if no user
         request.session.pop("github_token", None) # Clean up token if user somehow disappeared

    return templates.TemplateResponse(
        "app.html",
        {
            "request": request,
            "user": user,
            "is_guest": is_guest,
            "db_enabled": db_enabled
        }
    )


@app.post("/analyze/repo", status_code=status.HTTP_202_ACCEPTED)
async def analyze_repo_endpoint(
    payload: AnalyzeRepoRequest,
    request: Request, # For session access
    db: AsyncSession = Depends(get_db_session),
    user: Optional[dict] = Depends(get_current_user),
    token: Optional[str] = Depends(get_github_token)
):
    # Placeholder for Rate Limiting
    # rate_limit_check(request, user) # This function would raise HTTPException(429) if limit exceeded

    if not redis_conn or not repo_processing_q:
        logger.error("Redis connection or queue not available. Cannot process analysis request.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Analysis service temporarily unavailable.")

    user_github_id = str(user["id"]) if user and "id" in user else None

    if not settings.MY_DATABASE_URL or not db:
        logger.warning("Database not configured. Analysis will proceed without history.")
        # Create a dummy analysis_id or handle differently if DB is mandatory
        # For now, let's require DB for tracking.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service unavailable, cannot track analysis.")

    analysis_parameters = {"lang": payload.lang, "size": payload.size, "technicality": payload.technicality}
    
    history_entry = await create_analysis_history(
        db=db,
        repository_url=str(payload.url),
        parameters_used=analysis_parameters,
        user_github_id=user_github_id
    )

    if not history_entry:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initiate analysis record.")

    task_payload = {
        "analysis_id": history_entry.id,
        "repository_url": str(payload.url),
        "github_token": token, # Can be None for guest
        "analysis_parameters": analysis_parameters,
        "result_queue_name": settings.RESULT_QUEUE # Pass the name of the results queue
    }

    try:
        repo_processing_q.enqueue(
            "repo_processor_service.tasks.process_repo_task.process_repo_task", # Full path to task function
            task_payload,
            job_timeout="10m" # Example timeout
        )
        logger.info(f"Enqueued repo processing task for analysis_id: {history_entry.id}")
    except Exception as e:
        logger.error(f"Failed to enqueue task for analysis_id {history_entry.id}: {e}", exc_info=True)
        # Optionally, update DB status to FAILED here or let a cleanup job handle it
        await db.delete(history_entry) # Rollback the history entry
        await db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to queue analysis task.")

    return {"analysis_id": history_entry.id, "status": AnalysisStatus.QUEUED.value}


@app.get("/analysis/status/{analysis_id}", response_model=Optional[AnalysisStatusResponse])
async def get_analysis_status_endpoint(
    analysis_id: int,
    request: Request, # For session access
    db: AsyncSession = Depends(get_db_session),
    user: Optional[dict] = Depends(get_current_user)
):
    if not settings.MY_DATABASE_URL or not db:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service unavailable.")

    user_github_id = str(user["id"]) if user and "id" in user else None

    # If guest, user_github_id is None. get_analysis_by_id_for_user should allow this
    # or we need another way to authorize guests to see status of jobs they started (e.g. signed ID in cookie).
    # For now, assuming guest can poll if they have the ID.
    analysis_record = await get_analysis_by_id_for_user(db, analysis_id, user_github_id)

    if not analysis_record:
        # If user is logged in and record not found, it's a true 404 or access denied.
        # If guest and not found, it's a 404.
        detail_msg = "Analysis not found or access denied." if user_github_id else "Analysis not found."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail_msg)

    return AnalysisStatusResponse(
        analysis_id=analysis_record.id,
        status=analysis_record.status,
        repository_url=analysis_record.repository_url,
        parameters_used=analysis_record.parameters_used,
        summary_content=analysis_record.summary_content,
        error_message=analysis_record.error_message,
        timestamp=analysis_record.timestamp,
        updated_at=analysis_record.updated_at
    )

@app.get("/history", response_model=List[AnalysisHistoryItem])
async def get_user_history_endpoint(
    db: AsyncSession = Depends(get_db_session),
    user: Optional[dict] = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not settings.MY_DATABASE_URL or not db:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="History service unavailable.")
    
    user_github_id = str(user["id"])
    history_records = await get_analysis_history_for_user(db, user_github_id)
    return [AnalysisHistoryItem.from_orm(record) for record in history_records]


@app.get("/history/{history_id}", response_model=AnalysisHistoryDetail)
async def get_history_item_detail_endpoint(
    history_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: Optional[dict] = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not settings.MY_DATABASE_URL or not db:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="History service unavailable.")

    user_github_id = str(user["id"])
    # Use get_analysis_by_id_for_user to ensure ownership
    history_item = await get_analysis_by_id_for_user(db, history_id, user_github_id)
    if not history_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History item not found or access denied.")
    return AnalysisHistoryDetail.from_orm(history_item)

# The RQ worker for gitinsight_results is started by start.sh
# It will use api_service.tasks.result_consumer.process_analysis_result

if __name__ == "__main__":
    # This block is for local development without Docker/start.sh
    # In Docker, start.sh will run this and the RQ worker.
    import uvicorn
    logger.info(f"Starting Uvicorn server for API service on 0.0.0.0:8000 with log level {settings.LOG_LEVEL.upper()}")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False) # reload=True for dev