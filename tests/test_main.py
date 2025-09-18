"""Tests for main.py module."""

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

import main


@pytest.fixture
def mock_console():
    """Mock pour la console Rich."""
    console = MagicMock(spec=Console)
    return console


@patch("main.console")
@patch("src.presentation.cli.commands.app")
def test_main_success(mock_app, mock_console):
    """Test du point d'entrée main() avec succès."""
    # Exécute la fonction main
    main.main()

    # Vérifie que l'application a été lancée
    mock_app.assert_called_once()

    # Vérifie que la console a affiché le panneau de bienvenue
    mock_console.print.assert_called()


@patch("main.console")
@patch("src.presentation.cli.commands.app")
def test_main_keyboard_interrupt(mock_app, mock_console):
    """Test du point d'entrée main() avec interruption clavier."""
    # Configure le mock pour lever une KeyboardInterrupt
    mock_app.side_effect = KeyboardInterrupt()

    # Exécute la fonction main et vérifie qu'elle se termine
    with pytest.raises(SystemExit) as excinfo:
        main.main()

    # Vérifie que le code de sortie est 0 (sortie propre)
    assert excinfo.value.code == 0

    # Vérifie que le message de sortie a été affiché
    mock_console.print.assert_called_with("\nGoodbye!", style="yellow")


@patch("main.console")
@patch("src.presentation.cli.commands.app")
def test_main_exception(mock_app, mock_console):
    """Test du point d'entrée main() avec exception."""
    # Configure le mock pour lever une exception
    mock_app.side_effect = ValueError("Test error")

    # Exécute la fonction main et vérifie qu'elle se termine
    with pytest.raises(SystemExit) as excinfo:
        main.main()

    # Vérifie que le code de sortie est 1 (erreur)
    assert excinfo.value.code == 1

    # Vérifie que le message d'erreur a été affiché
    mock_console.print.assert_called_with(
        "An error occurred: Test error", style="bold red"
    )
