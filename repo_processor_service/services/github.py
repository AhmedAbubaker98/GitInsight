# This is a copy of the original services/github.py
# Ensure any imports like `from core.config import settings` are updated if needed,
# or that this service's config provides necessary values if github.py used them.
# For this refactor, assuming github.py is self-contained or uses universally available modules.
import os
import tempfile
import subprocess
import shutil
from urllib.parse import urlparse
import logging

# from repo_processor_service.core.config import settings # If needed

logger = logging.getLogger(__name__)

class GitHubServiceError(RuntimeError):
    """Base exception for GitHub service errors."""
    pass

class CloningError(GitHubServiceError):
    """Exception raised for errors during repository cloning."""
    pass

class URLParsingError(GitHubServiceError):
    """Exception raised for errors during GitHub URL parsing."""
    pass


def parse_github_url(url: str) -> tuple[str, str]:
    if not isinstance(url, str) or not url:
        raise URLParsingError("URL must be a non-empty string")

    if url.startswith("git@"): # SSH URL
        path_part = url.split(":", 1)[-1]
        parts = path_part.split("/")
        if len(parts) >= 2:
            owner = parts[0]
            repo = parts[1].replace(".git", "")
            if not owner or not repo:
                 raise URLParsingError(f"Invalid owner or repo name in SSH URL: {url}")
            return owner, repo
        else:
            raise URLParsingError(f"Invalid SSH URL format: {url}")
    
    try: # HTTPS or other web URLs
        parsed = urlparse(url)
        if not parsed.netloc or "github.com" not in parsed.netloc.lower():
            raise URLParsingError(f"URL does not appear to be a GitHub URL: {url}")

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = path_parts[1].replace(".git", "")
            if not owner or not repo:
                raise URLParsingError(f"Invalid owner or repo name in URL path: {url}")
            return owner, repo
        else:
            raise URLParsingError(f"GitHub URL path must include owner/repo: {url}")
    except ValueError as e:
        raise URLParsingError(f"Could not parse GitHub URL '{url}': {e}") from e


def clone_repo(url: str, token: str | None = None, base_temp_dir: str = "/tmp") -> str:
    """
    Clones the GitHub repository.
    Returns the local path of the cloned repo.
    Raises CloningError on failure.
    `base_temp_dir` is the root for tempfile.mkdtemp.
    """
    # Ensure the base temp directory exists, mkdtemp might not create parent dirs.
    os.makedirs(base_temp_dir, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="gitinsight_repo_", dir=base_temp_dir)
    
    log_url_display = url 

    try:
        owner, repo_name = parse_github_url(url)
    except URLParsingError as e:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir, ignore_errors=True)
        raise CloningError(f"Invalid GitHub URL for cloning: {e}") from e

    base_github_url_path = f"github.com/{owner}/{repo_name}.git"
    env = os.environ.copy()
    git_config_args = []

    if token:
        clone_url_actual = f"https://x-access-token:{token}@{base_github_url_path}"
        log_url_display = f"https://[REDACTED_TOKEN]@{base_github_url_path}"
        logger.info(f"Attempting authenticated clone for '{owner}/{repo_name}' into {temp_dir}")
    else:
        clone_url_actual = f"https://{base_github_url_path}"
        log_url_display = clone_url_actual
        env["GIT_TERMINAL_PROMPT"] = "0" 
        git_config_args.extend(["-c", "credential.helper="]) 
        logger.info(f"Guest mode: Attempting anonymous clone for '{owner}/{repo_name}' into {temp_dir}")

    command = ["git"] + git_config_args + ["clone", "--depth", "1", "--quiet", clone_url_actual, temp_dir]

    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
        logger.info(f"Successfully cloned repository '{owner}/{repo_name}' to: {temp_dir}")
        return temp_dir
    except subprocess.CalledProcessError as e:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir, ignore_errors=True)
        error_message = f"Failed to clone repository '{log_url_display}'. Git command failed (exit {e.returncode})."
        stderr_output = e.stderr.strip() if e.stderr else "No stderr output."
        if "Authentication failed" in stderr_output or \
           (not token and "could not read Username" in stderr_output):
            error_message += " Authentication failed."
            if not token: error_message += " This may be a private repository."
        elif "Repository not found" in stderr_output:
            error_message += " Repository not found or access denied."
        elif stderr_output:
            error_message += f" Git error: {stderr_output[:200]}"
        logger.error(f"CloningError for {log_url_display}: {error_message}. Stderr: {stderr_output}")
        raise CloningError(error_message) from e
    except FileNotFoundError as e: # Git command not found
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir, ignore_errors=True)
        msg = f"Git command not found. Ensure Git is installed. Error: {e}"
        logger.critical(msg)
        raise CloningError(msg) from e
    except Exception as e:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Unexpected error cloning '{log_url_display}': {e}", exc_info=True)
        raise CloningError(f"Unexpected error during cloning: {type(e).__name__}") from e