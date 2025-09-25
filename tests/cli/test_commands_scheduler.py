"""Tests pour les commandes CLI."""

from unittest import mock

from src.presentation.cli.commands import console, scheduler, scheduler_service


class TestCommands:
    """Tests pour les commandes CLI de GitHub Runner Manager."""

    def test_scheduler_normal_execution(self):
        """Test l'exécution normale de la commande scheduler."""
        scheduler_service.start = mock.MagicMock()

        scheduler()

        scheduler_service.start.assert_called_once()

    def test_scheduler_keyboard_interrupt(self):
        """Test la commande scheduler avec KeyboardInterrupt."""
        scheduler_service.start = mock.MagicMock(side_effect=KeyboardInterrupt())
        scheduler_service.stop = mock.MagicMock()
        console.print = mock.MagicMock()

        scheduler()

        scheduler_service.start.assert_called_once()
        scheduler_service.stop.assert_called_once()
        console.print.assert_called_once_with(
            "[yellow]Scheduler arrêté manuellement.[/yellow]"
        )

    def test_scheduler_exception(self):
        """Test la commande scheduler avec une exception générique."""
        test_exception = Exception("Test error")
        scheduler_service.start = mock.MagicMock(side_effect=test_exception)
        console.print = mock.MagicMock()

        scheduler()

        scheduler_service.start.assert_called_once()
        console.print.assert_called_once_with(
            f"[red]Erreur dans le scheduler: {str(test_exception)}[/red]"
        )
