"""Consolidated tests for build/start/stop/remove commands.
Covers success, empty, skipped, and error branches with parametrization.
"""

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
