"""Tests for DockerBuildLogger class."""

from unittest.mock import patch

from src.services.docker_logger import DockerBuildLogger


def test_default_logger():
    """Test that default logger prints all lines."""
    with patch("builtins.print") as mock_print:
        logger = DockerBuildLogger.default_logger
        test_line = "This is a test line"
        logger(test_line)
        mock_print.assert_called_once_with(test_line)


def test_quiet_logger_skips_empty_lines():
    """Test that quiet logger skips empty lines."""
    with patch("builtins.print") as mock_print:
        logger = DockerBuildLogger.quiet_logger
        # Test empty string
        logger("")
        # Test whitespace only
        logger("   ")
        # Verify no prints occurred
        mock_print.assert_not_called()


def test_quiet_logger_prints_step_lines():
    """Test that quiet logger prints step lines."""
    with patch("builtins.print") as mock_print:
        logger = DockerBuildLogger.quiet_logger
        # Test with leading/trailing whitespace to ensure strip and print
        step_line = "   Step 2/5 : RUN echo hello   "
        logger(step_line)
        mock_print.assert_called_once_with("Step 2/5 : RUN echo hello")


def test_quiet_logger_prints_step_lines_exact():
    """Test that quiet logger prints exact step lines (no whitespace)."""
    with patch("builtins.print") as mock_print:
        logger = DockerBuildLogger.quiet_logger
        step_line = "Step 3/7 : COPY . /app"
        logger(step_line)
        mock_print.assert_called_once_with("Step 3/7 : COPY . /app")


def test_quiet_logger_prints_error_lines():
    """Test that quiet logger prints error lines."""
    with patch("builtins.print") as mock_print:
        logger = DockerBuildLogger.quiet_logger

        error_line = "ERROR: Could not find image"
        logger(error_line)
        mock_print.assert_called_once_with(error_line)
        mock_print.reset_mock()

        failed_line = "The command failed with exit code 1"
        logger(failed_line)
        mock_print.assert_called_once_with(failed_line)


def test_quiet_logger_prints_success_lines():
    """Test that quiet logger prints success lines."""
    with patch("builtins.print") as mock_print:
        logger = DockerBuildLogger.quiet_logger

        # Test various success patterns
        success_lines = [
            "Build completed successfully",
            "The operation was a success",
            "Successfully tagged image:latest",
            "Successfully built abc123def456",
        ]

        for line in success_lines:
            logger(line)
            mock_print.assert_called_with(line)
            mock_print.reset_mock()


def test_quiet_logger_successfully_startswith():
    """Test that quiet logger prints lines starting with 'successfully'."""
    with patch("builtins.print") as mock_print:
        logger = DockerBuildLogger.quiet_logger

        # This test specifically targets the condition:
        # stripped_line.lower().startswith("successfully")
        test_line = "SUCCESSFULLY started the process"
        logger(test_line)
        mock_print.assert_called_once_with(test_line)


def test_quiet_logger_skips_other_lines():
    """Test that quiet logger skips other lines."""
    with patch("builtins.print") as mock_print:
        logger = DockerBuildLogger.quiet_logger

        # Regular build output that should be skipped
        lines_to_skip = [
            "---> Using cache",
            "Downloading packages",
            "Extracting archive",
            " ---> abc123def456",
        ]

        for line in lines_to_skip:
            logger(line)

        # Verify no prints occurred
        mock_print.assert_not_called()


def test_logger_factory():
    """Test that get_logger returns the correct logger based on quiet flag."""
    # When quiet=True, should return quiet_logger
    quiet_logger = DockerBuildLogger.get_logger(quiet=True)
    assert quiet_logger == DockerBuildLogger.quiet_logger

    # When quiet=False, should return default_logger
    default_logger = DockerBuildLogger.get_logger(quiet=False)
    assert default_logger == DockerBuildLogger.default_logger
