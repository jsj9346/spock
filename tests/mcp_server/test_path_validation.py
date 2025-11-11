# tests/mcp_server/test_path_validation.py
"""
Comprehensive tests for path validation functionality

Tests project path restriction, path traversal prevention,
and symlink attack protection.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from mcp_server.utils.validators import (
    validate_project_context,
    validate_file_path,
)
from mcp_server.utils.errors import PathValidationError


class TestValidateProjectContext:
    """Test suite for validate_project_context()"""

    def test_valid_project_path(self):
        """Test validation passes when in allowed project directory"""
        # Get actual current directory and use it as allowed path
        current_dir = os.getcwd()

        # Should not raise any exception
        validate_project_context(current_dir)

    def test_valid_subdirectory(self):
        """Test validation passes when in subdirectory of allowed path"""
        # Create temp directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            sub_dir = project_dir / "subdir"
            sub_dir.mkdir(parents=True)

            # Change to subdirectory
            original_cwd = os.getcwd()
            try:
                os.chdir(sub_dir)
                # Should pass - we're in a subdirectory of allowed path
                validate_project_context(str(project_dir))
            finally:
                os.chdir(original_cwd)

    def test_invalid_outside_project(self):
        """Test validation fails when outside allowed project"""
        # Use /tmp as current directory, /Users/13ruce/spock as allowed
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                with pytest.raises(PathValidationError) as exc_info:
                    validate_project_context("/Users/13ruce/spock")

                # Verify error details
                assert "allowed project path" in exc_info.value.message
                assert exc_info.value.code == "PATH_VALIDATION_ERROR"
                assert "current_path" in exc_info.value.details
                assert "allowed_path" in exc_info.value.details
            finally:
                os.chdir(original_cwd)

    def test_symlink_resolution(self):
        """Test validation resolves symlinks correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project directory and symlink
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            symlink_dir = Path(tmpdir) / "symlink"
            symlink_dir.symlink_to(project_dir)

            original_cwd = os.getcwd()
            try:
                # Change to symlink directory
                os.chdir(symlink_dir)

                # Should pass - symlink points to allowed directory
                validate_project_context(str(project_dir))
            finally:
                os.chdir(original_cwd)

    def test_trailing_slash_handling(self):
        """Test validation handles trailing slashes correctly"""
        current_dir = os.getcwd()

        # Both should work identically
        validate_project_context(current_dir)
        validate_project_context(current_dir + "/")


class TestValidateFilePath:
    """Test suite for validate_file_path()"""

    def test_valid_relative_path(self):
        """Test validation passes for relative path within project"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            test_file = project_dir / "data" / "test.csv"
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.touch()

            original_cwd = os.getcwd()
            try:
                os.chdir(project_dir)
                # Relative path within project should pass
                validate_file_path("data/test.csv", str(project_dir))
            finally:
                os.chdir(original_cwd)

    def test_valid_absolute_path_within_project(self):
        """Test validation passes for absolute path within project"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            test_file = project_dir / "test.txt"
            test_file.touch()

            # Absolute path within project should pass
            validate_file_path(str(test_file), str(project_dir))

    def test_invalid_path_traversal_relative(self):
        """Test validation blocks path traversal with ../"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            original_cwd = os.getcwd()
            try:
                os.chdir(project_dir)

                with pytest.raises(PathValidationError) as exc_info:
                    # Try to access parent directory
                    validate_file_path("../../etc/passwd", str(project_dir))

                assert "allowed project" in exc_info.value.message
                assert exc_info.value.code == "PATH_VALIDATION_ERROR"
            finally:
                os.chdir(original_cwd)

    def test_invalid_absolute_path_outside_project(self):
        """Test validation blocks absolute path outside project"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            with pytest.raises(PathValidationError) as exc_info:
                validate_file_path("/tmp/evil.txt", str(project_dir))

            assert "allowed project" in exc_info.value.message

    def test_symlink_resolution_within_project(self):
        """Test validation resolves symlinks within project"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Create file and symlink within project
            real_file = project_dir / "real.txt"
            real_file.touch()
            symlink_file = project_dir / "link.txt"
            symlink_file.symlink_to(real_file)

            # Should pass - symlink points to file within project
            validate_file_path(str(symlink_file), str(project_dir))

    def test_symlink_attack_outside_project(self):
        """Test validation blocks symlink pointing outside project"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Create file outside project
            outside_file = Path(tmpdir) / "outside.txt"
            outside_file.touch()

            # Create symlink inside project pointing outside
            symlink_file = project_dir / "evil_link.txt"
            symlink_file.symlink_to(outside_file)

            with pytest.raises(PathValidationError) as exc_info:
                validate_file_path(str(symlink_file), str(project_dir))

            assert "allowed project" in exc_info.value.message

    def test_current_directory_reference(self):
        """Test validation handles ./ correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            test_file = project_dir / "test.txt"
            test_file.touch()

            original_cwd = os.getcwd()
            try:
                os.chdir(project_dir)
                # ./file.txt should be same as file.txt
                validate_file_path("./test.txt", str(project_dir))
            finally:
                os.chdir(original_cwd)

    def test_nonexistent_path_validation(self):
        """Test validation works even for nonexistent paths"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            original_cwd = os.getcwd()
            try:
                os.chdir(project_dir)
                # Should pass - path would be within project even if file doesn't exist
                validate_file_path("nonexistent.txt", str(project_dir))
            finally:
                os.chdir(original_cwd)


class TestPathValidationIntegration:
    """Integration tests for path validation"""

    def test_config_environment_variable(self):
        """Test SPOCK_PROJECT_PATH environment variable"""
        from mcp_server.config import Config

        test_path = "/tmp/test_project"

        with patch.dict(os.environ, {"SPOCK_PROJECT_PATH": test_path}):
            config = Config.from_env()
            assert config.allowed_project_path == test_path

    def test_config_default_path(self):
        """Test default allowed_project_path"""
        from mcp_server.config import Config

        # Clear environment variable if it exists
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()
            assert config.allowed_project_path == "/Users/13ruce/spock"

    def test_error_serialization(self):
        """Test PathValidationError serializes correctly to JSON"""
        error = PathValidationError(
            "Test error",
            {"current_path": "/tmp", "allowed_path": "/Users/13ruce/spock"}
        )

        error_dict = error.to_dict()

        assert error_dict["success"] is False
        assert error_dict["error"]["code"] == "PATH_VALIDATION_ERROR"
        assert error_dict["error"]["message"] == "Test error"
        assert "current_path" in error_dict["error"]["details"]
        assert "allowed_path" in error_dict["error"]["details"]
