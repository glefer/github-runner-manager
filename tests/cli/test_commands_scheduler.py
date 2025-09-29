"""Tests for CLI commands."""

from unittest import mock

from src.presentation.cli.commands import console, scheduler, scheduler_service


class TestCommands:
    """Tests for the CLI commands of GitHub Runner Manager."""

    def test_scheduler_normal_execution(self):
        """Test normal execution of the scheduler command."""
        scheduler_service.start = mock.MagicMock()

        scheduler()

        scheduler_service.start.assert_called_once()

    def test_scheduler_keyboard_interrupt(self):
        """Test the scheduler command with KeyboardInterrupt."""
        scheduler_service.start = mock.MagicMock(side_effect=KeyboardInterrupt())
        scheduler_service.stop = mock.MagicMock()
        console.print = mock.MagicMock()

        scheduler()

        scheduler_service.start.assert_called_once()
        scheduler_service.stop.assert_called_once()
        console.print.assert_called_once_with(
            "[yellow]Scheduler stopped manually.[/yellow]"
        )

    def test_scheduler_exception(self):
        """Test the scheduler command with a generic exception."""
        test_exception = Exception("Test error")
        scheduler_service.start = mock.MagicMock(side_effect=test_exception)
        console.print = mock.MagicMock()

        scheduler()

        scheduler_service.start.assert_called_once()
        console.print.assert_called_once_with(
            f"[red]Error in scheduler: {str(test_exception)}[/red]"
        )
