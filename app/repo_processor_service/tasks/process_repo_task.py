# repo_processor_service/tasks/process_repo_task.py
import os
from pathlib import Path
import logging
import shutil # For cleaning up temporary directories
from typing import Dict, Any, Optional

# --- Third-party imports ---
from git import Repo, exc as GitExceptions # For cloning
from redis import Redis # For connecting to Redis
from rq import Queue # For enqueuing tasks

# --- Project-specific imports ---
# Import settings specific to this service
from repo_processor_service.core.config import settings as rps_settings

logger = logging.getLogger(__name__)

# --- Constants (Copied from your original file) ---
TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".log", ".cfg", ".ini", ".toml", ".yaml", ".yml", ".json", ".xml", ".html", ".css", ".js", ".py", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".php", ".rb", ".swift", ".kt", ".scala", ".sh", ".ps1", ".bat", "dockerfile", ".sql", ".ts"}
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss", ".php", ".rb", ".erb",
    ".java", ".scala", ".kt", ".cpp", ".c", ".h", ".hpp", ".cs", ".go", ".rs", ".swift",
    ".sh", ".bash", ".ps1", ".pl", ".lua", ".r", ".dart", ".sql", "dockerfile", "Dockerfile",
    ".m", ".mm", ".ino", ".vb", ".fs", ".groovy", ".perl", ".pas"
}
IMPORTANT_FILES = {
    "readme": ["README.md", "README.rst", "README.txt", "README", "readme.md"],
    "contributing": ["CONTRIBUTING.md", "CONTRIBUTING.rst"],
    "license": ["LICENSE", "LICENSE.md", "COPYING", "license.txt"],
    "setup": [
        "setup.py", "requirements.txt", "Pipfile", "pyproject.toml", "environment.yml",
        "package.json", "yarn.lock", "pnpm-lock.yaml", "webpack.config.js", "babel.config.js",
        "Gemfile", "Gemfile.lock", "composer.json", "pom.xml", "build.gradle", "settings.gradle",
        "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "Makefile", "CMakeLists.txt",
        "Dockerfile", "docker-compose.yml", "Jenkinsfile", ".travis.yml", ".gitlab-ci.yml"
    ],
    "configuration": [".env.example", "config.example.json", "settings.py", "appsettings.json", "web.config"],
    "architecture": ["ARCHITECTURE.md", "DESIGN.md"]
}
IGNORE_DIRS = {".git", ".vscode", ".idea", "node_modules", "__pycache__", "build", "dist", "target", "vendor", ".pytest_cache", "venv", "env", "docs", "examples", "tests", "test", "samples"}
IGNORE_FILES = {".gitignore", ".gitattributes", ".env", ".DS_Store", ".project", ".classpath", ".settings"}
IGNORE_EXTENSIONS = {".lock", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".map", ".min.js", ".min.css", ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".tar.gz", ".gz", ".rar", ".exe", ".dll", ".so", ".o", ".class", ".jar", ".pyc", ".webm", ".mp4", ".mp3", ".wav", ".obj", ".bin", ".dat", ".iso", ".img"}

MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB
MIN_FILE_SIZE_BYTES = 10 # Bytes

# --- Helper Functions for Parsing (Copied from your original file) ---
def read_file_content(file_path: Path) -> str | None:
    try:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            logger.debug(f"Parser: Skipping large file ({size / 1024:.1f} KB): {file_path}")
            return None
        if size < MIN_FILE_SIZE_BYTES:
            logger.debug(f"Parser: Skipping tiny file ({size} B): {file_path}")
            return None

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError as e:
        logger.warning(f"Parser: OS Error reading file {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Parser: Unexpected error reading file {file_path}: {e}", exc_info=True)
        return None

def is_likely_binary(file_path: Path) -> bool:
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024) # Read first 1KB
            return b'\0' in chunk # Null byte is a strong indicator of binary
    except OSError:
        return False

# --- Core Parsing Logic (Copied from your original file) ---
def parse_repo_content(repo_path: str) -> Dict[str, Any]: # Renamed for clarity, was parse_repo
    parsed_data = {"important": {}, "source_files": []}
    repo_root = Path(repo_path)
    files_processed_count = 0
    max_source_files_to_include = 150

    important_filenames_map = {
        name.lower(): category
        for category, filenames_list in IMPORTANT_FILES.items()
        for name in filenames_list
    }

    for current_dir, dir_names, file_names in os.walk(repo_root, topdown=True):
        dir_names[:] = [d_name for d_name in dir_names if d_name.lower() not in IGNORE_DIRS and not d_name.startswith('.')]
        
        current_path_obj = Path(current_dir)
        for file_name in file_names:
            if file_name.lower() in IGNORE_FILES or file_name.startswith('.'):
                continue

            file_path_obj = current_path_obj / file_name
            relative_file_path_str = str(file_path_obj.relative_to(repo_root))
            file_extension = file_path_obj.suffix.lower()

            if file_extension in IGNORE_EXTENSIONS:
                continue
            
            if not (file_extension in TEXT_EXTENSIONS or file_extension in CODE_EXTENSIONS):
                if is_likely_binary(file_path_obj):
                    logger.debug(f"Parser: Skipping likely binary file: {relative_file_path_str}")
                    continue
            
            file_content = read_file_content(file_path_obj)
            if not file_content:
                continue

            is_important = False
            if file_name.lower() in important_filenames_map:
                if relative_file_path_str not in parsed_data["important"]:
                    parsed_data["important"][relative_file_path_str] = file_content
                    files_processed_count += 1
                    is_important = True
            
            if not is_important and file_extension in CODE_EXTENSIONS:
                if len(parsed_data["source_files"]) < max_source_files_to_include:
                    parsed_data["source_files"].append({
                        "path": relative_file_path_str,
                        "content": file_content
                    })
                    files_processed_count += 1
                elif len(parsed_data["source_files"]) == max_source_files_to_include:
                    logger.info(f"Parser: Reached source file limit ({max_source_files_to_include}).")

    logger.info(f"Parser: Processed {files_processed_count} files from '{repo_path}'. "
                f"Important: {len(parsed_data['important'])}, Source: {len(parsed_data['source_files'])}")
    return parsed_data

# --- Helper function to send status updates/results ---
def _send_to_queue(queue_name: str, task_function_path: str, payload: Dict[str, Any], analysis_id: int):
    """Helper to enqueue data to a specified queue."""
    try:
        # Each task function should manage its own Redis connection context if possible,
        # or RQ's default connection can be used if Connection(redis_conn) is active in the worker.
        # For simplicity here, creating a short-lived connection.
        with Redis.from_url(str(rps_settings.REDIS_URL)) as redis_conn:
            q = Queue(queue_name, connection=redis_conn)
            q.enqueue(task_function_path, payload)
            logger.info(f"[Analysis ID: {analysis_id}] Enqueued to '{queue_name}': {task_function_path} with partial payload keys: {list(payload.keys())}")
    except Exception as e:
        logger.error(f"[Analysis ID: {analysis_id}] Failed to enqueue to '{queue_name}': {e}", exc_info=True)
        # This is a critical failure if we can't report back.
        # Depending on the error, this might indicate a problem with Redis itself.

def _send_status_update(analysis_id: int, result_queue_name: str, status: str, message: Optional[str] = None, error_message: Optional[str] = None, data: Optional[Dict] = None):
    """Sends a status update or final result to the central result queue."""
    payload = {
        "analysis_id": analysis_id,
        "status": status,
    }
    if message:
        payload["message"] = message
    if error_message:
        payload["error_message"] = error_message
    if data: # For sending final summary_content, etc.
        payload.update(data)

    # The task consuming this in api_service needs to be defined.
    # Assuming it's 'api_service.tasks.result_consumer.process_analysis_result'
    _send_to_queue(
        queue_name=result_queue_name,
        task_function_path="api_service.tasks.result_consumer.process_analysis_result",
        payload=payload,
        analysis_id=analysis_id
    )

# --- RQ Task Function ---
def process_repo_task(analysis_id: int, repository_url: str, github_token: Optional[str],
                      analysis_parameters: Dict[str, Any], result_queue_name: str):
    """
    RQ task to clone, parse a repository, and enqueue parsed data for AI analysis.
    It also sends status updates back to the main result queue.
    """
    logger.info(f"[Analysis ID: {analysis_id}] Received task for repository: {repository_url}")

    # Define a temporary directory for cloning
    # CLONE_TEMP_DIR_BASE should be defined in repo_processor_service.core.config.settings
    base_temp_dir = Path(rps_settings.CLONE_TEMP_DIR_BASE)
    temp_clone_dir = base_temp_dir / f"analysis_{analysis_id}_{os.urandom(4).hex()}"

    try:
        # 0. Send "processing_repo" status update
        _send_status_update(
            analysis_id=analysis_id,
            result_queue_name=result_queue_name,
            status="processing_repo", # Make sure this status string matches your db_models.AnalysisStatus enum
            message="Starting repository cloning and parsing."
        )

        # 1. Create temporary directory
        os.makedirs(temp_clone_dir, exist_ok=True)
        logger.info(f"[Analysis ID: {analysis_id}] Created temp directory: {temp_clone_dir}")

        # 2. Clone the repository
        logger.info(f"[Analysis ID: {analysis_id}] Cloning {repository_url} into {temp_clone_dir}...")
        try:
            # Note: github_token is not directly used by clone_from here.
            # For private repos via HTTPS, the token would need to be embedded in the URL
            # or Git credential helper configured. For SSH, SSH keys are needed.
            # For public repos, it might help with rate limits if used with GitHub API calls,
            # but not directly with a simple `git clone`.
            Repo.clone_from(repository_url, str(temp_clone_dir), depth=1) # Shallow clone
            logger.info(f"[Analysis ID: {analysis_id}] Successfully cloned repository.")
        except GitExceptions.GitCommandError as e:
            logger.error(f"[Analysis ID: {analysis_id}] Failed to clone repository {repository_url}: {e.stderr}", exc_info=True)
            _send_status_update(
                analysis_id=analysis_id,
                result_queue_name=result_queue_name,
                status="failed",
                error_message=f"Failed to clone repository: {e.stderr[:500]}" # Truncate long errors
            )
            return # Stop processing

        # 3. Parse the cloned repository content
        logger.info(f"[Analysis ID: {analysis_id}] Parsing cloned repository at {temp_clone_dir}")
        parsed_data = parse_repo_content(str(temp_clone_dir))
        logger.info(f"[Analysis ID: {analysis_id}] Successfully parsed repository content.")

        # 4. Enqueue the parsed data for AI analysis
        # The AI_ANALYSIS_QUEUE is defined in this service's settings (rps_settings)
        ai_task_payload = {
            "analysis_id": analysis_id,
            "parsed_repo_content": parsed_data, # This might be large!
            "analysis_parameters": analysis_parameters,
            "result_queue_name": result_queue_name # AI worker needs this for the final result
        }
        
        # Placeholder for the AI analyzer task path. You'll need to create this service and task.
        ai_task_function_path = "ai_analyzer_service.tasks.ai_task.analyze_content_task"
        
        _send_to_queue(
            queue_name=rps_settings.AI_ANALYSIS_QUEUE,
            task_function_path=ai_task_function_path,
            payload=ai_task_payload,
            analysis_id=analysis_id
        )
        logger.info(f"[Analysis ID: {analysis_id}] Enqueued data for AI analysis to '{rps_settings.AI_ANALYSIS_QUEUE}'.")
        
        # Optionally, send another status update indicating handoff to AI
        # _send_status_update(
        #     analysis_id=analysis_id,
        #     result_queue_name=result_queue_name,
        #     status="processing_ai", # Make sure this status string matches your db_models.AnalysisStatus enum
        #     message="Repository processing complete. Handed off for AI analysis."
        # )

    except Exception as e:
        logger.error(f"[Analysis ID: {analysis_id}] Unhandled error in process_repo_task for {repository_url}: {e}", exc_info=True)
        _send_status_update(
            analysis_id=analysis_id,
            result_queue_name=result_queue_name,
            status="failed",
            error_message=f"Internal error during repository processing: {str(e)[:500]}"
        )
    finally:
        # 5. Clean up the temporary clone directory
        if temp_clone_dir.exists():
            try:
                shutil.rmtree(temp_clone_dir)
                logger.info(f"[Analysis ID: {analysis_id}] Cleaned up temporary directory: {temp_clone_dir}")
            except Exception as e_clean:
                logger.error(f"[Analysis ID: {analysis_id}] Error cleaning up temporary directory {temp_clone_dir}: {e_clean}", exc_info=True)

    logger.info(f"[Analysis ID: {analysis_id}] Finished task for repository: {repository_url}")