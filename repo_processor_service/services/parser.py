# This is a copy of the original services/parser.py
# Ensure any imports like `from core.config import settings` are updated if needed.
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

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
        return False # Error reading, assume not binary to be safe

def parse_repo(repo_path: str):
    parsed_data = {"important": {}, "source_files": []}
    repo_root = Path(repo_path)
    files_processed_count = 0
    max_source_files_to_include = 150 # Increased limit slightly

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
            
            # More aggressive binary check if not explicitly text/code
            if not (file_extension in TEXT_EXTENSIONS or file_extension in CODE_EXTENSIONS):
                if is_likely_binary(file_path_obj):
                    logger.debug(f"Parser: Skipping likely binary file: {relative_file_path_str}")
                    continue
            
            file_content = read_file_content(file_path_obj)
            if not file_content:
                continue

            is_important = False
            # Check if it's an important file by exact name first, then by category convention
            if file_name.lower() in important_filenames_map:
                if relative_file_path_str not in parsed_data["important"]: # Avoid duplicates if multiple READMEs
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
                    # Future files of this type will be skipped.

    logger.info(f"Parser: Processed {files_processed_count} files from '{repo_path}'. "
                f"Important: {len(parsed_data['important'])}, Source: {len(parsed_data['source_files'])}")
    return parsed_data