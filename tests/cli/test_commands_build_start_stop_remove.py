"""Consolidated tests for build/start/stop/remove commands."""

from unittest.mock import patch

import pytest

from src.presentation.cli.commands import app


@pytest.mark.parametrize(
    "result_data,expected",
    [
        (
            {
                "built": [{"image": "img", "dockerfile": "Df", "id": "x"}],
                "skipped": [],
                "errors": [],
            },
            ["SUCCESS", "img", "Df"],
        ),
        (
            {
                "built": [],
                "skipped": [{"id": "x", "reason": "No build_image"}],
                "errors": [],
            },
            ["INFO", "Pas d'image", "No build_image"],
        ),
        (
            {
                "built": [],
                "skipped": [],
                "errors": [{"id": "x", "reason": "Build failed"}],
            },
            ["ERREUR", "x", "Build failed"],
        ),
        (
            {"built": [], "skipped": [], "errors": []},
            [],
        ),
    ],
)
@patch("src.services.docker_service.DockerService.build_runner_images")
def test_build_runners_images(mock_build, cli, result_data, expected):
    mock_build.return_value = result_data
    res = cli.invoke(app, ["build-runners-images"])
    assert res.exit_code == 0
    for text in expected:
        assert text in res.stdout


@pytest.mark.parametrize(
    "result_data,expected",
    [
        (
            {
                "started": [{"name": "r1"}],
                "restarted": [],
                "running": [],
                "removed": [],
                "errors": [],
            },
            ["r1", "démarré"],
        ),
        (
            {
                "started": [],
                "restarted": [{"name": "r2"}],
                "running": [],
                "removed": [],
                "errors": [],
            },
            ["r2", "Redémarrage"],
        ),
        (
            {
                "started": [],
                "restarted": [],
                "running": [{"name": "r3"}],
                "removed": [],
                "errors": [],
            },
            ["r3", "déjà démarré"],
        ),
        (
            {
                "started": [],
                "restarted": [],
                "running": [],
                "removed": [{"name": "old"}],
                "errors": [],
            },
            ["old", "n'est plus requis"],
        ),
        (
            {
                "started": [],
                "restarted": [],
                "running": [],
                "removed": [],
                "errors": [{"id": "e", "reason": "fail"}],
            },
            ["ERREUR", "e", "fail"],
        ),
        (
            {
                "started": [],
                "restarted": [],
                "running": [],
                "removed": [],
                "errors": [],
            },
            [],
        ),
    ],
)
@patch("src.services.docker_service.DockerService.start_runners")
def test_start_runners(mock_start, cli, result_data, expected):
    mock_start.return_value = result_data
    res = cli.invoke(app, ["start-runners"])
    assert res.exit_code == 0
    for text in expected:
        assert text in res.stdout


@pytest.mark.parametrize(
    "result_data,expected",
    [
        (
            {"stopped": [{"name": "r1"}], "skipped": [], "errors": []},
            ["r1", "arrêté"],
        ),
        (
            {"stopped": [], "skipped": [{"name": "r2"}], "errors": []},
            ["r2", "n'est pas en cours"],
        ),
        (
            {"stopped": [], "skipped": [], "errors": [{"name": "e", "reason": "fail"}]},
            ["ERREUR", "e", "fail"],
        ),
        (
            {"stopped": [], "skipped": [], "errors": []},
            [],
        ),
    ],
)
@patch("src.services.docker_service.DockerService.stop_runners")
def test_stop_runners(mock_stop, cli, result_data, expected):
    mock_stop.return_value = result_data
    res = cli.invoke(app, ["stop-runners"])
    assert res.exit_code == 0
    for text in expected:
        assert text in res.stdout


@pytest.mark.parametrize(
    "result_data,expected_present,expected_absent",
    [
        (
            {"removed": [{"container": "c1"}], "skipped": [], "errors": []},
            ["c1", "supprimé avec succès"],
            [],
        ),
        (
            {"removed": [{"name": "r"}], "skipped": [], "errors": []},
            [],
            ["supprimé avec succès"],  # message container non attendu
        ),
        (
            {
                "removed": [],
                "skipped": [{"name": "s", "reason": "déjà supprimé"}],
                "errors": [],
            },
            ["déjà supprimé"],
            [],
        ),
        (
            {"removed": [], "skipped": [], "errors": [{"name": "e", "reason": "fail"}]},
            ["ERREUR", "e", "fail"],
            [],
        ),
        (
            {"removed": [], "skipped": [], "errors": []},
            [],
            [],
        ),
    ],
)
@patch("src.services.docker_service.DockerService.remove_runners")
def test_remove_runners(
    mock_remove, cli, result_data, expected_present, expected_absent
):
    mock_remove.return_value = result_data
    res = cli.invoke(app, ["remove-runners"])
    assert res.exit_code == 0
    for text in expected_present:
        assert text in res.stdout
    for text in expected_absent:
        assert text not in res.stdout


@patch("src.presentation.cli.commands.docker_service.build_runner_images")
@patch("src.presentation.cli.commands.docker_service.check_base_image_update")
@patch("src.presentation.cli.commands.typer.confirm")
def test_check_base_image_update_build_outputs(
    mock_confirm, mock_check_update, mock_build, cli
):
    """Covers lines printing skipped and error cases after building images inside check_base_image_update interactive flow."""
    # Two confirmations: update then build
    mock_confirm.side_effect = [True, True]
    # First call: update available
    first_result = {
        "current_version": "2.300.0",
        "latest_version": "2.301.0",
        "update_available": True,
        "error": None,
    }
    # Second call: after auto_update
    second_result = {
        **first_result,
        "updated": True,
        "new_image": "ghcr.io/actions/runner:2.301.0",
    }
    mock_check_update.side_effect = [first_result, second_result]
    mock_build.return_value = {
        "built": [],
        "skipped": [{"id": "r1", "reason": "No build_image specified"}],
        "errors": [{"id": "r2", "reason": "Build failed"}],
    }

    res = cli.invoke(app, ["check-base-image-update"])
    assert res.exit_code == 0
    # Assert skipped line (line ~158) content fragments
    assert "Pas d'image à builder" in res.stdout
    assert "r1" in res.stdout
    # Assert error line (line ~163) content fragments
    assert "ERREUR" in res.stdout
    assert "r2" in res.stdout
    assert "Build failed" in res.stdout
