"""Tests pour les commandes CLI."""

from unittest import mock

from src.presentation.cli.commands import console, scheduler, scheduler_service


class TestCommands:
    """Tests pour les commandes CLI de GitHub Runner Manager."""

    def test_scheduler_normal_execution(self):
        """Test l'exécution normale de la commande scheduler."""
        # Mock la méthode start pour éviter l'exécution réelle
        scheduler_service.start = mock.MagicMock()

        # Exécuter la commande
        scheduler()

        # Vérifier que start a été appelé
        scheduler_service.start.assert_called_once()

    def test_scheduler_keyboard_interrupt(self):
        """Test la commande scheduler avec KeyboardInterrupt."""
        # Mock la méthode start pour lever une KeyboardInterrupt
        scheduler_service.start = mock.MagicMock(side_effect=KeyboardInterrupt())
        scheduler_service.stop = mock.MagicMock()
        console.print = mock.MagicMock()

        # Exécuter la commande
        scheduler()

        # Vérifier que les méthodes attendues ont été appelées
        scheduler_service.start.assert_called_once()
        scheduler_service.stop.assert_called_once()
        console.print.assert_called_once_with(
            "[yellow]Scheduler arrêté manuellement.[/yellow]"
        )

    def test_scheduler_exception(self):
        """Test la commande scheduler avec une exception générique."""
        # Mock la méthode start pour lever une exception
        test_exception = Exception("Test error")
        scheduler_service.start = mock.MagicMock(side_effect=test_exception)
        console.print = mock.MagicMock()

        # Exécuter la commande
        scheduler()

        # Vérifier que les méthodes attendues ont été appelées
        scheduler_service.start.assert_called_once()
        console.print.assert_called_once_with(
            f"[red]Erreur dans le scheduler: {str(test_exception)}[/red]"
        )
