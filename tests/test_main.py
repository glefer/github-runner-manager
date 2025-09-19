from unittest.mock import patch

import pytest

import main


@patch("main.console")
@patch("src.presentation.cli.commands.app")
def test_main_success(mock_app, mock_console):
    main.main()
    mock_app.assert_called_once()
    mock_console.print.assert_called()


@patch("main.console")
@patch("src.presentation.cli.commands.app")
def test_main_keyboard_interrupt(mock_app, mock_console):
    mock_app.side_effect = KeyboardInterrupt()
    with pytest.raises(SystemExit) as excinfo:
        main.main()
    assert excinfo.value.code == 0
    mock_console.print.assert_called_with("\nGoodbye!", style="yellow")


@patch("main.console")
@patch("src.presentation.cli.commands.app")
def test_main_exception(mock_app, mock_console):
    mock_app.side_effect = ValueError("Test error")
    with pytest.raises(SystemExit) as excinfo:
        main.main()
    assert excinfo.value.code == 1
    mock_console.print.assert_called_with(
        "An error occurred: Test error", style="bold red"
    )
