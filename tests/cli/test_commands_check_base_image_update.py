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
        # Ajoute un True supplémentaire pour le prompt de déploiement
        mock_confirm.side_effect = [True, True, True]
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


# Nouveau: couverture du prompt de déploiement et des sorties started/restarted/running/removed
@patch("src.services.docker_service.DockerService.start_runners")
@patch("src.services.docker_service.DockerService.build_runner_images")
@patch("src.services.docker_service.DockerService.check_base_image_update")
@patch("typer.confirm")
@pytest.mark.parametrize(
    "start_result, expected_snippets, deploy_confirm",
    [
        (  # user refuse le déploiement -> aucune ligne de déploiement
            {},
            [],
            False,
        ),
        (  # started
            {"started": [{"name": "runner-a"}]},
            ["runner-a démarré avec succès"],
            True,
        ),
        (  # restarted
            {"restarted": [{"name": "runner-b"}]},
            ["runner-b existant mais stoppé"],
            True,
        ),
        (  # running
            {"running": [{"name": "runner-c"}]},
            ["runner-c déjà démarré"],
            True,
        ),
        (  # removed
            {"removed": [{"name": "runner-d"}]},
            ["runner-d n'est plus requis"],
            True,
        ),
    ],
)
def test_check_base_image_update_deploy_branches(
    mock_confirm,
    mock_check,
    mock_build,
    mock_start,
    cli,
    start_result,
    expected_snippets,
    deploy_confirm,
):
    """Couvre:
    - Refus du déploiement (ligne 172 -> exit)
    - Affichage des messages started / restarted / running / removed
    """
    # 1ère invocation: update disponible; 2ème: mise à jour appliquée
    mock_check.side_effect = [
        {"current_version": "1", "latest_version": "2", "update_available": True},
        {"updated": True, "new_image": "img:2"},
    ]
    # Build retourne une image pour activer la branche de déploiement potentielle
    mock_build.return_value = {
        "built": [{"id": "grp", "image": "custom:latest", "dockerfile": "Dockerfile"}],
        "skipped": [],
        "errors": [],
    }
    mock_start.return_value = {
        "started": [],
        "restarted": [],
        "running": [],
        "removed": [],
        "errors": [],
        **start_result,
    }

    # Séquence des confirmations:
    # 1) update yes
    # 2) build yes
    # 3) deploy yes/no selon le paramètre
    mock_confirm.side_effect = [True, True, deploy_confirm]

    res = cli.invoke(app, ["check-base-image-update"])
    assert res.exit_code == 0
    clean_stdout = strip_ansi_codes(res.stdout)

    # Si l'utilisateur refuse le déploiement, rien de spécifique ne doit apparaître
    if not deploy_confirm:
        for snippet in [
            "démarré avec succès",
            "existant mais stoppé",
            "déjà démarré",
            "n'est plus requis",
        ]:
            assert snippet not in clean_stdout
        return

    for snippet in expected_snippets:
        assert (
            snippet in clean_stdout
        ), f"Snippet attendu manquant: {snippet}\nSortie: {clean_stdout}"
