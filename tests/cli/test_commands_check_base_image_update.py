"""Consolidated tests for check-base-image-update command."""

import re
from unittest.mock import patch

import pytest

from src.presentation.cli.commands import app

# Pré-compile le regex ANSI une seule fois pour éviter le coût par appel
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi_codes(text: str) -> str:
    """Supprime tous les codes d'échappement ANSI (utilisés pour la couleur) d'une chaîne."""
    return ANSI_ESCAPE_RE.sub("", text)


@pytest.mark.parametrize(
    "first_result,confirm,result2,expects",
    [
        ({"error": "API fail"}, False, None, ["API fail"]),
        (
            {"current_version": "1", "latest_version": "1", "update_available": False},
            False,
            None,
            ["déjà à jour"],
        ),
        (
            {"current_version": "1", "latest_version": "2", "update_available": True},
            False,
            None,
            ["Nouvelle version", "Mise à jour annulée"],
        ),
        (
            {"current_version": "1", "latest_version": "2", "update_available": True},
            True,
            {"updated": True, "new_image": "img:2"},
            ["mis à jour vers", "img:2"],
        ),
        (
            {"current_version": "1", "latest_version": "2", "update_available": True},
            True,
            {"error": "write failed"},
            ["Erreur lors de la mise à jour", "write failed"],
        ),
        (
            {"current_version": "1", "latest_version": "2", "update_available": True},
            True,
            {"updated": False},
            [],
        ),
    ],
)
@patch("src.services.docker_service.DockerService.check_base_image_update")
@patch("typer.confirm")
def test_check_base_image_update(
    mock_confirm, mock_check, cli, first_result, confirm, result2, expects
):
    if result2 is None:
        mock_check.return_value = first_result
    else:
        mock_check.side_effect = [first_result, result2]
    # If an update is available and user confirms first prompt, the CLI will ask a second confirmation
    # to build images. We simulate both confirmations returning the same 'confirm' value for simplicity.
    if first_result.get("update_available") and confirm:
        mock_confirm.side_effect = [True, True]
    elif first_result.get("update_available") and not confirm:
        mock_confirm.side_effect = [False]
    else:
        mock_confirm.return_value = confirm

    res = cli.invoke(app, ["check-base-image-update"])
    assert res.exit_code == 0

    # Supprimer les codes ANSI pour faciliter la comparaison
    clean_stdout = strip_ansi_codes(res.stdout)

    # Vérification des assertions
    for e in expects:
        assert e in clean_stdout, f"Expected '{e}' to be in '{clean_stdout}'"

    if first_result.get("update_available"):
        # If an update was available we expect at least one confirmation (update prompt).
        # If the update was applied and user agreed, a second confirmation (build prompt) may also occur.
        assert mock_confirm.call_count >= 1
    else:
        mock_confirm.assert_not_called()


# New test for branch 144->exit (user declines build after update)
@patch("src.services.docker_service.DockerService.build_runner_images")
@patch("src.services.docker_service.DockerService.check_base_image_update")
@patch("typer.confirm")
def test_check_base_image_update_decline_build(
    mock_confirm, mock_check, mock_build, cli
):
    """Test branch where user declines to build images after update (branch 144->exit)."""
    # First call: update available, user accepts update
    # Second call: user declines build
    mock_check.side_effect = [
        {"current_version": "1", "latest_version": "2", "update_available": True},
        {"updated": True, "new_image": "img:2"},
    ]
    mock_confirm.side_effect = [True, False]

    res = cli.invoke(app, ["check-base-image-update"])
    assert res.exit_code == 0
    clean_stdout = strip_ansi_codes(res.stdout)
    # Should mention update, but not build success or skipped lines
    assert "mis à jour vers" in clean_stdout
    assert "img:2" in clean_stdout
    # Should NOT call build_runner_images
    mock_build.assert_not_called()
    # Should not print build success message
    assert "buildée depuis" not in clean_stdout
