# tests/services/test_parser.py
import pytest
from pathlib import Path
import os
from services.parser import (
    parse_repo, read_file_content, is_likely_binary,
    TEXT_EXTENSIONS, CODE_EXTENSIONS, IMPORTANT_FILES, IGNORE_DIRS,
    IGNORE_FILES, IGNORE_EXTENSIONS, MAX_FILE_SIZE_BYTES, MIN_FILE_SIZE_BYTES
)

# Fixture to create a mock repository structure
@pytest.fixture
def mock_repo_path(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "mock_repo_fs"
    repo_dir.mkdir()

    # Important files
    (repo_dir / "README.md").write_text("# Project Readme")
    (repo_dir / "LICENSE").write_text("MIT License")
    (repo_dir / "requirements.txt").write_text("fastapi\npytest")

    # Source files
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello')")
    (src_dir / "utils.js").write_text("console.log('world');")
    (src_dir / "style.css").write_text("body { color: red; }") # Should be parsed as source

    # Ignored files and dirs
    (repo_dir / ".git").mkdir()
    (repo_dir / ".gitignore").write_text("*.log")
    (repo_dir / "node_modules").mkdir()
    (repo_dir / "data.log").write_text("some log data") # Ignored by extension
    (repo_dir / "image.png").write_text("binarydata")   # Ignored by extension + binary check

    # Large file
    large_file_content = "a" * (MAX_FILE_SIZE_BYTES + 100)
    (repo_dir / "large_file.txt").write_text(large_file_content)

    # Tiny file
    (repo_dir / "tiny_file.txt").write_text("abc") # Less than MIN_FILE_SIZE_BYTES

    # Binary file (mocked by content)
    (repo_dir / "binary_file.dat").write_bytes(b"prefix\0suffix")

    return repo_dir

class TestReadFileContent:
    def test_read_valid_file(self, tmp_path: Path):
        file = tmp_path / "test.txt"
        file.write_text("Hello World")
        assert read_file_content(file) == "Hello World"

    def test_read_large_file_skipped(self, tmp_path: Path, capsys):
        file = tmp_path / "large.txt"
        file.write_text("a" * (MAX_FILE_SIZE_BYTES + 1))
        assert read_file_content(file) is None
        captured = capsys.readouterr()
        assert "Skipping large file" in captured.out

    def test_read_tiny_file_skipped(self, tmp_path: Path):
        file = tmp_path / "tiny.txt"
        file.write_text("a" * (MIN_FILE_SIZE_BYTES - 1))
        assert read_file_content(file) is None
        # Optional: check capsys output if you add logging for tiny files

    def test_read_non_existent_file(self, tmp_path: Path, capsys):
        file = tmp_path / "non_existent.txt"
        assert read_file_content(file) is None
        captured = capsys.readouterr()
        assert "OS Error reading file" in captured.out # Or similar based on your print

    # Mock open for encoding error test
    @pytest.mark.skip(reason="Complex to mock open for specific encoding error here, cover by integration")
    def test_read_encoding_error(self, tmp_path: Path):
        pass # Covered by errors="ignore"

class TestIsLikelyBinary:
    def test_text_file(self, tmp_path: Path):
        file = tmp_path / "text.txt"
        file.write_text("This is a text file.")
        assert not is_likely_binary(file)

    def test_binary_file_with_null_byte(self, tmp_path: Path):
        file = tmp_path / "binary.dat"
        file.write_bytes(b"This is binary\0data.")
        assert is_likely_binary(file)

    def test_non_existent_file(self, tmp_path: Path):
        file = tmp_path / "non_existent.dat"
        assert not is_likely_binary(file) # Should return False if cannot read

class TestParseRepo:
    def test_parse_repo_structure(self, mock_repo_path: Path):
        result = parse_repo(str(mock_repo_path))

        # Check important files
        assert "README.md" in result["important"]
        assert result["important"]["README.md"] == "# Project Readme"
        assert "LICENSE" in result["important"]
        assert "requirements.txt" in result["important"]

        # Check source files (relative paths)
        source_file_paths = {f["path"] for f in result["source_files"]}
        assert "src/main.py" in source_file_paths
        assert "src/utils.js" in source_file_paths
        assert "src/style.css" in source_file_paths # .css is in CODE_EXTENSIONS

        # Check ignored items are not present
        assert "data.log" not in result["important"] # Ignored by extension
        assert "image.png" not in result["important"]
        assert not any(f["path"] == "data.log" for f in result["source_files"])
        assert not any(f["path"] == "image.png" for f in result["source_files"])
        assert not any(f["path"].startswith(".git/") for f in result["source_files"])
        assert not any(f["path"].startswith("node_modules/") for f in result["source_files"])
        assert ".gitignore" not in result["important"]

        # Check file size limits
        assert "large_file.txt" not in result["important"] # Skipped due to size
        assert not any(f["path"] == "large_file.txt" for f in result["source_files"])
        assert "tiny_file.txt" not in result["important"] # Skipped due to size
        assert not any(f["path"] == "tiny_file.txt" for f in result["source_files"])

        # Check binary file
        assert "binary_file.dat" not in result["important"]
        assert not any(f["path"] == "binary_file.dat" for f in result["source_files"])

    def test_max_source_files_limit(self, tmp_path: Path, capsys):
        repo_dir = tmp_path / "limit_repo"
        repo_dir.mkdir()
        src_dir = repo_dir / "src"
        src_dir.mkdir()

        # Create more files than max_source_files (default 100)
        for i in range(120):
            (src_dir / f"file_{i}.py").write_text(f"print({i})")

        result = parse_repo(str(repo_dir))
        assert len(result["source_files"]) == 100 # Default max_source_files
        captured = capsys.readouterr()
        assert "Reached maximum source file limit" in captured.out

    def test_empty_repo(self, tmp_path: Path):
        empty_repo_dir = tmp_path / "empty_repo"
        empty_repo_dir.mkdir()
        result = parse_repo(str(empty_repo_dir))
        assert not result["important"]
        assert not result["source_files"]