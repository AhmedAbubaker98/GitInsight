# tests/services/test_github.py
import pytest
import subprocess
import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock
from services.github import parse_github_url, clone_repo

class TestParseGithubUrl:
    @pytest.mark.parametrize(
        "url, expected_owner, expected_repo",
        [
            ("https://github.com/user/repo", "user", "repo"),
            ("http://github.com/user/repo.git", "user", "repo"),
            ("https://www.github.com/another-user/another-repo", "another-user", "another-repo"),
            ("git@github.com:user/repo.git", "user", "repo"),
            ("git@github.com:org-name/project-name.git", "org-name", "project-name"),
            ("https://github.com/user/repo/tree/main", "user", "repo"),
            ("https://github.com/user/repo.git/blob/dev/file.py", "user", "repo"),
        ],
    )
    def test_valid_urls(self, url, expected_owner, expected_repo):
        owner, repo = parse_github_url(url)
        assert owner == expected_owner
        assert repo == expected_repo

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "https://gitlab.com/user/repo",
            "github.com/user/repo",  # Missing scheme
            "https://github.com/user",  # Missing repo
            "git@github.com:user_repo.git",  # Invalid SSH format (missing /)
            "http://example.com/user/repo.git",
            "",
            None,
            123,
        ],
    )
    def test_invalid_urls(self, invalid_url):
        with pytest.raises(ValueError):
            parse_github_url(invalid_url)

class TestCloneRepo:
    @pytest.fixture
    def mock_temp_dir(self, tmp_path):
        # tmp_path is a pytest fixture providing a temporary directory path
        return str(tmp_path / "cloned_repo")

    @patch("services.github.tempfile.mkdtemp")
    @patch("services.github.subprocess.run")
    @patch("services.github.shutil.rmtree")
    @patch("services.github.parse_github_url", return_value=("test_owner", "test_repo"))
    def test_clone_successful_with_token(
        self, mock_parse_url, mock_rmtree, mock_subprocess_run, mock_mkdtemp, mock_temp_dir
    ):
        mock_mkdtemp.return_value = mock_temp_dir
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Cloned successfully"
        mock_process.stderr = ""
        mock_subprocess_run.return_value = mock_process

        repo_url = "https://github.com/test_owner/test_repo"
        token = "test_token"
        cloned_path = clone_repo(repo_url, token)

        assert cloned_path == mock_temp_dir
        mock_mkdtemp.assert_called_once()
        mock_parse_url.assert_called_with(repo_url)
        expected_clone_url = f"https://x-access-token:{token}@github.com/test_owner/test_repo.git"
        expected_command = ["git", "clone", "--depth", "1", expected_clone_url, mock_temp_dir]
        mock_subprocess_run.assert_called_once()
        called_command = mock_subprocess_run.call_args[0][0]
        assert called_command == expected_command
        mock_rmtree.assert_not_called()  # Not called on success path within clone_repo

    @patch("services.github.tempfile.mkdtemp")
    @patch("services.github.subprocess.run")
    @patch("services.github.shutil.rmtree")
    @patch("services.github.parse_github_url", return_value=("test_owner", "test_repo"))
    def test_clone_successful_guest_mode(
        self, mock_parse_url, mock_rmtree, mock_subprocess_run, mock_mkdtemp, mock_temp_dir
    ):
        mock_mkdtemp.return_value = mock_temp_dir
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_subprocess_run.return_value = mock_process

        repo_url = "https://github.com/test_owner/test_repo"
        cloned_path = clone_repo(repo_url, token=None)

        assert cloned_path == mock_temp_dir
        expected_clone_url = "https://github.com/test_owner/test_repo.git"
        # Check that credential.helper is set correctly
        expected_command_prefix = ["git", "-c", "credential.helper=!false", "clone", "--depth", "1"]
        mock_subprocess_run.assert_called_once()
        called_command = mock_subprocess_run.call_args[0][0]
        assert called_command[:len(expected_command_prefix)] == expected_command_prefix
        assert called_command[-2] == expected_clone_url
        assert called_command[-1] == mock_temp_dir
        # Check GIT_TERMINAL_PROMPT in env
        called_env = mock_subprocess_run.call_args[1].get('env', {})
        assert called_env.get("GIT_TERMINAL_PROMPT") == "0"
        mock_rmtree.assert_not_called()

    @patch("services.github.tempfile.mkdtemp")
    @patch("services.github.subprocess.run")
    @patch("services.github.shutil.rmtree")
    @patch("services.github.parse_github_url", return_value=("test_owner", "test_repo"))
    def test_clone_failure_git_command_error(
        self, mock_parse_url, mock_rmtree, mock_subprocess_run, mock_mkdtemp, mock_temp_dir
    ):
        mock_mkdtemp.return_value = mock_temp_dir
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=128, cmd="git clone ...", stderr="fatal: repository not found"
        )
        repo_url = "https://github.com/test_owner/non_existent_repo"
        with pytest.raises(RuntimeError) as excinfo:
            clone_repo(repo_url, token=None)
        assert "Failed to clone repository" in str(excinfo.value)
        assert "repository not found" in str(excinfo.value)
        mock_rmtree.assert_called_once_with(mock_temp_dir, ignore_errors=True)

    @patch("services.github.tempfile.mkdtemp")
    @patch("services.github.shutil.rmtree")
    @patch("services.github.parse_github_url", side_effect=ValueError("Invalid URL"))
    def test_clone_failure_invalid_url(
        self, mock_parse_url, mock_rmtree, mock_mkdtemp, mock_temp_dir
    ):
        mock_mkdtemp.return_value = mock_temp_dir
        repo_url = "invalid_url_format"
        with pytest.raises(RuntimeError) as excinfo:
            clone_repo(repo_url)
        assert "Invalid GitHub URL for cloning: Invalid URL" in str(excinfo.value)
        mock_rmtree.assert_called_once_with(mock_temp_dir, ignore_errors=True)
        mock_mkdtemp.assert_called_once() # mkdtemp is called before parse_github_url

    @patch("services.github.tempfile.mkdtemp")
    @patch("services.github.subprocess.run")
    @patch("services.github.shutil.rmtree")
    @patch("services.github.parse_github_url", return_value=("test_owner", "test_repo"))
    def test_clone_authentication_failure_guest(
        self, mock_parse_url, mock_rmtree, mock_subprocess_run, mock_mkdtemp, mock_temp_dir
    ):
        mock_mkdtemp.return_value = mock_temp_dir
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=128, cmd="git clone ...", stderr="fatal: could not read Username for 'https://github.com': No such device or address"
        )
        repo_url = "https://github.com/private_owner/private_repo"
        with pytest.raises(RuntimeError) as excinfo:
            clone_repo(repo_url, token=None)
        assert "Authentication failed." in str(excinfo.value)
        assert "This could be a private repository." in str(excinfo.value)
        mock_rmtree.assert_called_once_with(mock_temp_dir, ignore_errors=True)