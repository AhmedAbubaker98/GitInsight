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
            return b'\\0' in chunk # Null byte is a strong indicator of binary
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
        with Redis.from_url(str(rps_settings.REDIS_URL)) as redis_conn:
            q = Queue(queue_name, connection=redis_conn)
            q.enqueue(task_function_path, payload)
            logger.info(f"[Analysis ID: {analysis_id}] Enqueued to '{queue_name}': {task_function_path} with partial payload keys: {list(payload.keys())}")
    except Exception as e:
        logger.error(f"[Analysis ID: {analysis_id}] Failed to enqueue to '{queue_name}': {e}", exc_info=True)

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
    if data: 
        payload.update(data)

    _send_to_queue(
        queue_name=result_queue_name,
        task_function_path="api_service.tasks.result_consumer.process_analysis_result",
        payload=payload,
        analysis_id=analysis_id
    )

# --- RQ Task Function ---
def process_repo_task(analysis_id: int, repository_url: str, github_token: Optional[str],
                      analysis_parameters: Dict[str, Any], result_queue_name: str):
    logger.info(f"[Analysis ID: {analysis_id}] Received task for repository: {repository_url}")

    base_temp_dir = Path(rps_settings.CLONE_TEMP_DIR_BASE)
    temp_clone_dir = base_temp_dir / f"analysis_{analysis_id}_{os.urandom(4).hex()}"

    try:
        _send_status_update(
            analysis_id=analysis_id,
            result_queue_name=result_queue_name,
            status="processing_repo",
            message="Starting repository cloning and parsing."
        )

        os.makedirs(temp_clone_dir, exist_ok=True)
        logger.info(f"[Analysis ID: {analysis_id}] Created temp directory: {temp_clone_dir}")

        logger.info(f"[Analysis ID: {analysis_id}] Cloning {repository_url} into {temp_clone_dir}...")
        try:
            # Construct clone URL, potentially with token for private HTTPS repos
            clone_url = repository_url
            if github_token and repository_url.startswith("https://"):
                # Basic token injection for HTTPS. More robust solutions might use credential helpers.
                url_parts = repository_url.split("://")
                clone_url = f"{url_parts[0]}://oauth2:{github_token}@{url_parts[1]}"
            
            Repo.clone_from(clone_url, str(temp_clone_dir), depth=1)
            logger.info(f"[Analysis ID: {analysis_id}] Successfully cloned repository.")
        except GitExceptions.GitCommandError as e:
            logger.error(f"[Analysis ID: {analysis_id}] Failed to clone repository {repository_url}: {e.stderr}", exc_info=True)
            _send_status_update(
                analysis_id=analysis_id,
                result_queue_name=result_queue_name,
                status="failed",
                error_message=f"Failed to clone repository: {e.stderr[:500]}"
            )
            return

        logger.info(f"[Analysis ID: {analysis_id}] Parsing cloned repository at {temp_clone_dir}")
        parsed_content = parse_repo_content(str(temp_clone_dir)) # Use the local parsing logic
        
        # Prepare a concise version of parsed_content for logging if it's too large
        # For example, log keys and types/lengths of values
        log_parsed_summary = {
            "important_files_count": len(parsed_content.get("important", {})),
            "source_files_count": len(parsed_content.get("source_files", []))
        }
        logger.info(f"[Analysis ID: {analysis_id}] Successfully parsed repository content: {log_parsed_summary}")


        # Instead of sending full parsed_repo_content, which can be large,
        # we'll send a more structured and potentially summarized/concatenated text.
        # For simplicity, let's concatenate important files and a selection of source files.
        # This part needs to be carefully designed based on AI model input limits.

        extracted_text_parts = []
        for path, content in parsed_content.get("important", {}).items():
            extracted_text_parts.append(f"--- File: {path} ---\n{content}\n\n")
        
        for file_info in parsed_content.get("source_files", []):
            extracted_text_parts.append(f"--- File: {file_info['path']} ---\n{file_info['content']}\n\n")
        
        final_extracted_text = "".join(extracted_text_parts)
        
        # Check size of final_extracted_text. If too large, truncate or summarize further.
        # This is a placeholder for actual size management.
        MAX_TEXT_FOR_AI = 500000 # Example: 500k characters
        if len(final_extracted_text) > MAX_TEXT_FOR_AI:
            logger.warning(f"[Analysis ID: {analysis_id}] Extracted text is too large ({len(final_extracted_text)} chars), truncating.")
            final_extracted_text = final_extracted_text[:MAX_TEXT_FOR_AI] + "\n\n--- TRUNCATED DUE TO LENGTH ---"


        ai_task_payload = {
            "analysis_id": analysis_id,
            "extracted_text": final_extracted_text, # Send concatenated text
            "analysis_parameters": analysis_parameters,
            "result_queue_name": result_queue_name
        }
        
        # MODIFIED: Corrected task path for AI analyzer
        ai_task_function_path = "ai_analyzer_service.tasks.analyze_text_task.analyze_text_task"
        
        _send_to_queue(
            queue_name=rps_settings.AI_ANALYSIS_QUEUE,
            task_function_path=ai_task_function_path,
            payload=ai_task_payload,
            analysis_id=analysis_id
        )
        logger.info(f"[Analysis ID: {analysis_id}] Enqueued data for AI analysis to '{rps_settings.AI_ANALYSIS_QUEUE}'.")
        
    except Exception as e:
        logger.error(f"[Analysis ID: {analysis_id}] Unhandled error in process_repo_task for {repository_url}: {e}", exc_info=True)
        _send_status_update(
            analysis_id=analysis_id,
            result_queue_name=result_queue_name,
            status="failed",
            error_message=f"Internal error during repository processing: {str(e)[:500]}"
        )
    finally:
        if temp_clone_dir.exists():
            try:
                shutil.rmtree(temp_clone_dir)
                logger.info(f"[Analysis ID: {analysis_id}] Cleaned up temporary directory: {temp_clone_dir}")
            except Exception as e_clean:
                logger.error(f"[Analysis ID: {analysis_id}] Error cleaning up temporary directory {temp_clone_dir}: {e_clean}", exc_info=True)

    logger.info(f"[Analysis ID: {analysis_id}] Finished task for repository: {repository_url}")
    