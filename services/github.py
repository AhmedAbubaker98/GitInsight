import os
import tempfile
import subprocess
import shutil
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
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
    """
    Extract owner and repo name from various GitHub URL formats.
    Raises URLParsingError on failure.
    """
    if not isinstance(url, str) or not url:
        raise URLParsingError("URL must be a non-empty string")

    if url.startswith("git@"):
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

    try:
        parsed = urlparse(url)
        # Check if the netloc is a GitHub domain (optional, but good for stricter parsing)
        if not parsed.netloc or "github.com" not in parsed.netloc.lower():
            raise URLParsingError(f"URL does not appear to be a GitHub URL: {url}")

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = path_parts[1].replace(".git", "")
            if not owner or not repo: # Check for empty owner/repo after stripping
                raise URLParsingError(f"Invalid owner or repo name in URL path: {url}")
            return owner, repo
        else:
            raise URLParsingError(f"GitHub URL path must include owner and repository name: {url}")
    except ValueError as e: # Catch parsing errors from urlparse itself
        raise URLParsingError(f"Could not parse GitHub URL '{url}': Invalid URL format.") from e
    except Exception as e: # Catch any other unexpected errors during parsing logic
        # This might be redundant if URLParsingError is raised for all specific cases.
        raise URLParsingError(f"An unexpected error occurred while parsing GitHub URL '{url}': {e}") from e


def clone_repo(url: str, token: str | None = None) -> str:
    """
    Clones the GitHub repository into a temp directory.
    Uses HTTPS for cloning. If a token is provided, it's used for authentication.
    Returns the local path of the cloned repo.
    Raises CloningError on failure.
    """
    temp_dir = tempfile.mkdtemp(prefix="gitinsight_repo_")
    log_url_display = url # For logging, to avoid exposing token

    try:
        owner, repo_name = parse_github_url(url) # Can raise URLParsingError
    except URLParsingError as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        # Re-raise as CloningError because this function's contract is to raise CloningError for failures
        raise CloningError(f"Invalid GitHub URL for cloning: {e}") from e

    base_github_url_path = f"github.com/{owner}/{repo_name}.git"
    env = os.environ.copy()
    git_config_args = []

    if token:
        clone_url_actual = f"https://x-access-token:{token}@{base_github_url_path}"
        log_url_display = f"https://[REDACTED_TOKEN]@{base_github_url_path}" # For logging
        logger.info(f"Attempting authenticated clone for '{owner}/{repo_name}' from '{log_url_display}' into {temp_dir}")
    else:
        clone_url_actual = f"https://{base_github_url_path}"
        log_url_display = clone_url_actual
        env["GIT_TERMINAL_PROMPT"] = "0" # Disable git prompting for credentials
        # Explicitly disable any system/global credential helpers
        git_config_args.extend(["-c", "credential.helper="]) # Empty string to disable
        logger.info(f"Guest mode: Attempting anonymous clone for '{owner}/{repo_name}' from '{log_url_display}' into {temp_dir} (credential helpers explicitly disabled)")

    command = ["git"] + git_config_args + ["clone", "--depth", "1", "--quiet", clone_url_actual, temp_dir]

    try:
        process = subprocess.run(
            command,
            check=True,        # Raises CalledProcessError on non-zero exit
            capture_output=True, # Capture stdout and stderr
            text=True,         # Decode stdout/stderr as text
            env=env
        )
        logger.info(f"Successfully cloned repository '{owner}/{repo_name}' to: {temp_dir}")
        return temp_dir
    except subprocess.CalledProcessError as e:
        # Ensure cleanup on failure
        if os.path.exists(temp_dir):
             shutil.rmtree(temp_dir, ignore_errors=True)

        error_message = f"Failed to clone repository '{log_url_display}'. Git command failed (exit code {e.returncode})."
        stderr_output = e.stderr.strip() if e.stderr else "No stderr output."
        
        # Enhance error messages based on common Git errors
        if "Authentication failed" in stderr_output or \
           (not token and "could not read Username" in stderr_output) or \
           (not token and "remote error: Password authentication is not allowed" in stderr_output):
            error_message += " Authentication failed."
            if not token:
                 error_message += " This could be a private repository or require authentication. Please log in with GitHub to analyze private repos, or ensure the repository is public and accessible."
        elif "Repository not found" in stderr_output or "not found" in stderr_output.lower():
            error_message += " Repository not found or access denied."
        elif stderr_output: # Generic Git error
            error_message += f" Git error: {stderr_output[:300]}" # Truncate long errors for client
        
        logger.error(f"CloningError for {log_url_display}: {error_message}. Stderr: {stderr_output}")
        raise CloningError(error_message) from e
    except FileNotFoundError as e: # Git command not found
        if os.path.exists(temp_dir):
             shutil.rmtree(temp_dir, ignore_errors=True)
        msg = f"Git command not found. Please ensure Git is installed and in your system's PATH. Error: {e}"
        logger.critical(msg)
        raise CloningError(msg) from e
    except Exception as e: # Catch any other unexpected errors
        if os.path.exists(temp_dir):
             shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"An unexpected error occurred during cloning of '{log_url_display}': {e}", exc_info=True)
        raise CloningError(f"An unexpected error occurred during cloning: {type(e).__name__}") from e
