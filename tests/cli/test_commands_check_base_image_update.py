"""Consolidated tests for check-base-image-update command."""

import re
from unittest.mock import patch

import pytest

from src.presentation.cli.commands import app

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
    if first_result.get("update_available") and confirm:
        mock_confirm.side_effect = [True, True, True]
    elif first_result.get("update_available") and not confirm:
        mock_confirm.side_effect = [False]
    else:
        mock_confirm.return_value = confirm

    res = cli.invoke(app, ["check-base-image-update"])
    assert res.exit_code == 0

    clean_stdout = strip_ansi_codes(res.stdout)

    for e in expects:
        assert e in clean_stdout, f"Expected '{e}' to be in '{clean_stdout}'"

    if first_result.get("update_available"):
        assert mock_confirm.call_count >= 1
    else:
        mock_confirm.assert_not_called()


@patch("src.services.docker_service.DockerService.build_runner_images")
@patch("src.services.docker_service.DockerService.check_base_image_update")
@patch("typer.confirm")
def test_check_base_image_update_decline_build(
    mock_confirm, mock_check, mock_build, cli
):
    """Test branch where user declines to build images after update (branch 144->exit)."""
    mock_check.side_effect = [
        {"current_version": "1", "latest_version": "2", "update_available": True},
        {"updated": True, "new_image": "img:2"},
    ]
    mock_confirm.side_effect = [True, False]

    res = cli.invoke(app, ["check-base-image-update"])
    assert res.exit_code == 0
    clean_stdout = strip_ansi_codes(res.stdout)
    assert "mis à jour vers" in clean_stdout
    assert "img:2" in clean_stdout
    mock_build.assert_not_called()
    assert "buildée depuis" not in clean_stdout


@patch("src.services.docker_service.DockerService.start_runners")
@patch("src.services.docker_service.DockerService.build_runner_images")
@patch("src.services.docker_service.DockerService.check_base_image_update")
@patch("typer.confirm")
@pytest.mark.parametrize(
    "start_result, expected_snippets, deploy_confirm",
    [
    ({}, [], False),
    ({"started": [{"name": "runner-a"}]}, ["runner-a démarré avec succès"], True),
    ({"restarted": [{"name": "runner-b"}]}, ["runner-b existant mais stoppé"], True),
    ({"running": [{"name": "runner-c"}]}, ["runner-c déjà démarré"], True),
    ({"removed": [{"name": "runner-d"}]}, ["runner-d n'est plus requis"], True),
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


@patch("src.services.webhook_service.WebhookService._send_with_retry")
@patch("src.services.docker_service.DockerService.check_base_image_update")
@patch("typer.confirm")
def test_check_base_image_update_webhook_called(
    mock_confirm, mock_check, mock_webhook_send, cli
):
    """Vérifie que le webhook est bien appelé avec les bonnes infos lors d'une mise à jour."""
    mock_check.side_effect = [
        {
            "current_version": "1",
            "latest_version": "2",
            "update_available": True,
            "image_name": "image:1.0.1",
        },
        {"updated": True, "new_image": "img:2"},
    ]
    # Accepte la mise à jour, refuse le build pour éviter des notifications de build aléatoires
    mock_confirm.side_effect = [True, False]

    res = cli.invoke(app, ["check-base-image-update"])
    assert res.exit_code == 0

    assert mock_webhook_send.called, "Le webhook n'a pas été appelé."

    titles = []
    for call in mock_webhook_send.call_args_list:
        args, _ = call
        payload = args[1]
        if isinstance(payload, dict) and payload.get("attachments"):
            att0 = payload["attachments"][0]
            titles.append(att0.get("title", ""))
            txt = att0.get("text", "") or payload.get("text", "")
            assert "unknown" not in str(txt).lower()
            assert "{" not in str(txt) and "}" not in str(txt)
            for field in att0.get("fields", []):
                val = str(field.get("value", ""))
                assert "unknown" not in val.lower()
                assert "{" not in val and "}" not in val

    assert any(
        t == "Mise à jour disponible" for t in titles
    ), f"Aucune notif 'Mise à jour disponible' dans: {titles}"


def test_webhook_channel_removes_restarted_false(monkeypatch):
    """Couvre la suppression de 'restarted' si False dans WebhookChannel.send."""
    from unittest.mock import MagicMock

    from src.notifications.channels.webhook import WebhookChannel

    # Mock WebhookService
    mock_svc = MagicMock()
    channel = WebhookChannel(mock_svc)

    # Fake event with to_payload returning a dict with 'restarted': False
    class FakeEvent:
        def to_payload(self):
            return {
                "event_type": "runner_started",
                "runner_name": "foo",
                "restarted": False,
            }

    event = FakeEvent()
    channel.send(event)

    # Check that 'restarted' is not in the payload sent to notify
    args, kwargs = mock_svc.notify.call_args
    sent_payload = args[1]
    assert (
        "restarted" not in sent_payload
    ), f"'restarted' should be removed, got: {sent_payload}"


@patch("src.services.docker_service.DockerService.build_runner_images")
@patch("src.services.docker_service.DockerService.check_base_image_update")
@patch("typer.confirm")
def test_check_base_image_update_build_error_printed(
    mock_confirm, mock_check, mock_build, cli
):
    # Simule update disponible, update acceptée, build acceptée
    mock_check.side_effect = [
        {"current_version": "1", "latest_version": "2", "update_available": True},
        {"updated": True, "new_image": "img:2"},
    ]
    mock_confirm.side_effect = [True, True, True]  # update, build, deploy
    mock_build.return_value = {
        "built": [{"id": "grp", "image": "custom:latest", "dockerfile": "Dockerfile"}],
        "skipped": [],
        "errors": [{"id": "grp", "reason": "fail reason"}],
    }

    res = cli.invoke(app, ["check-base-image-update"])
    print(res.stdout)
    assert res.exit_code == 0
    assert "grp: fail reason" in res.stdout


def test_build_runner_images_image_size_exception(monkeypatch):
    """Couvre le except Exception: image_size = 0 dans build_runner_images."""
    from types import SimpleNamespace

    from src.services import DockerService

    class DummyConfig:
        runners = [
            SimpleNamespace(
                build_image="Dockerfile",
                techno="x",
                techno_version="1",
                name_prefix="foo",
            )
        ]
        runners_defaults = SimpleNamespace(base_image="img:1.0.0")

    class DummyConfigService:
        def load_config(self):
            return DummyConfig()

    svc = DockerService(DummyConfigService())
    monkeypatch.setattr(svc, "build_image", lambda **kwargs: None)

    class DummyImages:
        def get(self, tag):
            raise Exception("fail")

    class DummyClient:
        images = DummyImages()

    monkeypatch.setattr("docker.from_env", lambda: DummyClient())
    result = svc.build_runner_images()
    assert result["built"][0]["image_size"] == "0.00 B"


def test_format_size_pb():
    """Couvre le cas PB dans _format_size."""
    from src.services import DockerService

    svc = DockerService(lambda: None)
    # 2**60 = 1 PB
    pb = 2**60
    assert svc._format_size(pb).endswith("PB")
