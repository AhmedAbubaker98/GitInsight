import os
import json
import shutil
import asyncio
from typing import Optional, AsyncGenerator
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from services.github import parse_github_url, clone_repo, CloningError, URLParsingError
from services.parser import parse_repo
from services.analyzer import generate_summary_stream
from services.db.db_service import log_analysis_request
from core.config import settings

# --- Logging Setup ---
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Analysis Stream Helper ---
async def stream_analysis(
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
