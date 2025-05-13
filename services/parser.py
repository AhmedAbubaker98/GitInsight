import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# --- Custom Exceptions (Optional for this module, as errors are mostly logged) ---
# class ParserError(RuntimeError):
#     """Base exception for parsing errors."""
#     pass

# class FileReadError(ParserError):
#     """Exception raised when a file cannot be read."""
#     pass


# Configuration for parser (could be moved to config.py or a dedicated parser_config.py)
TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".log", ".cfg", ".ini", ".toml", ".yaml", ".yml", ".json"}
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss", ".php", ".rb", ".erb",
    ".java", ".scala", ".kt", ".cpp", ".c", ".h", ".hpp", ".cs", ".go", ".rs", ".swift",
    ".sh", ".bash", ".ps1", ".pl", ".lua", ".r", ".dart", ".sql", ".dockerfile", "Dockerfile",
    ".m", ".mm", ".ino"
}
IMPORTANT_FILES = {
    "readme": ["README.md", "README.rst", "README.txt", "README"],
    "contributing": ["CONTRIBUTING.md", "CONTRIBUTING.rst"],
    "license": ["LICENSE", "LICENSE.md", "COPYING"],
    "setup": [
        "setup.py", "requirements.txt", "Pipfile", "pyproject.toml", "environment.yml",
        "package.json", "yarn.lock", "pnpm-lock.yaml",
        "Gemfile", "Gemfile.lock", "composer.json",
        "pom.xml", "build.gradle", "go.mod", "go.sum",
        "Cargo.toml", "Cargo.lock", "Dockerfile", "docker-compose.yml"
    ],
    "configuration": [".env.example", "config.example.json", "settings.py"],
    "architecture": ["ARCHITECTURE.md"]
}
IGNORE_DIRS = {".git", ".vscode", ".idea", "node_modules", "__pycache__", "build", "dist", "target", "vendor", ".pytest_cache", "venv"}
IGNORE_FILES = {".gitignore", ".gitattributes", ".env", ".DS_Store"}
IGNORE_EXTENSIONS = {".lock", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".map", ".min.js", ".min.css", ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".tar.gz", ".gz", ".rar", ".exe", ".dll", ".so", ".o", ".class", ".jar", ".pyc"}

MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB
MIN_FILE_SIZE_BYTES = 10 # Bytes, ignore very small or empty files

def read_file_content(file_path: Path) -> str | None:
    """Reads file content safely, handling potential errors and size limits."""
    try:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            logger.debug(f"Skipping large file ({size / 1024:.1f} KB): {file_path}")
            return None
        if size < MIN_FILE_SIZE_BYTES:
            logger.debug(f"Skipping tiny file ({size} B): {file_path}")
            return None

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError as e:
        logger.warning(f"OS Error reading file {file_path}: {e}")
        # Not raising FileReadError here to allow parse_repo to continue with other files.
        # If a critical file fails, it might be an issue, but for general parsing, skipping is okay.
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading file {file_path}: {e}", exc_info=True)
        return None

def is_likely_binary(file_path: Path) -> bool:
    """Basic check for binary files based on null bytes in the first 1KB."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except OSError as e:
        logger.warning(f"Could not perform binary check on {file_path} due to OS Error: {e}. Assuming not binary.")
        return False # Error reading, treat as non-binary for safety to attempt parsing

def parse_repo(repo_path: str):
    """
    Traverse a local repo, extract key files, and sample source code.
    """
    parsed_data = {
        "important": {},      # Key: relative_path, Value: content
        "source_files": []    # List of {"path": relative_path, "content": content}
    }
    repo_root = Path(repo_path)
    files_processed_count = 0
    max_source_files_to_include = 100 # Limit to prevent excessive data

    important_filenames_map = {
        name.lower(): category
        for category, filenames_list in IMPORTANT_FILES.items()
        for name in filenames_list
    }

    for current_dir, dir_names, file_names in os.walk(repo_root, topdown=True):
        # Filter out ignored directories
        dir_names[:] = [d_name for d_name in dir_names if d_name not in IGNORE_DIRS and not d_name.startswith('.')]

        current_path_obj = Path(current_dir)

        for file_name in file_names:
            if file_name in IGNORE_FILES or file_name.startswith('.'): # Ignore hidden files not explicitly listed
                continue

            file_path_obj = current_path_obj / file_name
            relative_file_path_str = str(file_path_obj.relative_to(repo_root))
            file_extension = file_path_obj.suffix.lower()

            if file_extension in IGNORE_EXTENSIONS:
                continue

            # Skip likely binary files early if not a known text/code extension
            if not (file_extension in TEXT_EXTENSIONS or file_extension in CODE_EXTENSIONS):
                if is_likely_binary(file_path_obj):
                    logger.debug(f"Skipping likely binary file: {relative_file_path_str}")
                    continue
            
            file_content = read_file_content(file_path_obj)
            if not file_content: # Skips if too large, too small, or read error
                continue

            # Check if it's an important file
            is_important = False
            if file_name.lower() in important_filenames_map:
                # category = important_filenames_map[file_name.lower()] # Not used currently
                if relative_file_path_str not in parsed_data["important"]:
                    parsed_data["important"][relative_file_path_str] = file_content
                    files_processed_count += 1
                    is_important = True
                # Continue to next file, don't also add as generic source if it's important for this logic
                # If you want important files to ALSO be in source_files, remove `is_important` check below
                # and the `continue` statement. For now, assume they are distinct.

            # If not already processed as important, check if it's a source code file
            if not is_important and file_extension in CODE_EXTENSIONS:
                if len(parsed_data["source_files"]) < max_source_files_to_include:
                    parsed_data["source_files"].append({
                        "path": relative_file_path_str,
                        "content": file_content
                    })
                    files_processed_count += 1
                elif len(parsed_data["source_files"]) == max_source_files_to_include:
                    # Log only once when limit is first hit
                    logger.info(f"Reached maximum source file limit ({max_source_files_to_include}). Some source files may be omitted.")
                    # To stop further processing of source files once limit is hit:
                    # you could set a flag, or just let it try to add more but they get ignored.
                    # The current logic will simply not add more beyond this.

    logger.info(f"Parser processed {files_processed_count} relevant files from '{repo_path}'. "
                f"Found {len(parsed_data['important'])} important files and {len(parsed_data['source_files'])} source files.")
    return parsed_data