from unittest.mock import MagicMock, mock_open, patch

import pytest


@patch("src.services.docker_service.DockerService.image_exists", return_value=False)
@patch("src.services.docker_service.DockerService.build_image")
def test_start_runners_build_image_missing_techno(
    mock_build, _img, docker_service, config_service
):
    cfg = config_service.load_config.return_value
    cfg.runners[0].techno = None
    cfg.runners[0].techno_version = None
    mock_build.side_effect = Exception("fail")
    res = docker_service.start_runners()
    assert any("Build failed" in e["reason"] for e in res["errors"])


@patch("pathlib.Path.exists", return_value=False)
@pytest.mark.parametrize(
    "containers",
    [
        ["test-runner-X", "test-runner-2"],
        ["foo", "test-runner-2"],
    ],
)
def test_start_runners_removes_expected(
    _mock_path_exists, containers, docker_service, config_service
):
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.build_image = MagicMock()
    docker_service.list_containers = MagicMock(return_value=containers)
    docker_service.container_running = MagicMock(return_value=False)
    docker_service.remove_container = MagicMock()
    docker_service.exec_command = MagicMock()
    config_service.load_config.return_value.runners[0].nb = 1
    res = docker_service.start_runners()
    assert any(r.get("name") == "test-runner-2" for r in res["removed"]) or any(
        r.get("id") == "test-runner-2" for r in res["removed"]
    )


@patch("pathlib.Path.exists", return_value=False)
def test_start_runners_removal_exception(
    _mock_path_exists, docker_service, config_service
):
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.build_image = MagicMock()
    docker_service.list_containers = MagicMock(return_value=["test-runner-2"])
    docker_service.container_running = MagicMock(return_value=False)
    docker_service.remove_container = MagicMock(side_effect=Exception("remove failed"))
    docker_service.exec_command = MagicMock()
    config_service.load_config.return_value.runners[0].nb = 1
    res = docker_service.start_runners()
    assert any(
        r.get("operation") == "removal" and "remove failed" in r.get("reason", "")
        for r in res["errors"]
    )


def test_start_runners_running_and_restarted(
    docker_service, config_service, mock_docker_client
):
    """Checks that one runner already started is classified as running and another is restarted.

    Conditions:
    - Two runners configured (nb=2)
    - Containers already exist
    - The first is running, the second is stopped
    - Images match (no forced redeployment due to image mismatch)
    """
    # Préparation config
    cfg = config_service.load_config.return_value
    cfg.runners[0].nb = 2
    # Construit l'image attendue pour ce runner (avec techno/php déjà dans la config fixture)
    base_image = cfg.runners_defaults.base_image
    m = __import__("re").search(r":([\d.]+)$", base_image)
    runner_version = m.group(1) if m else "latest"
    expected_image = f"itroom/{cfg.runners[0].techno}:{cfg.runners[0].techno_version}-{runner_version}"

    # Mocks
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.build_image = MagicMock()
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(side_effect=[True, False])
    docker_service.start_container = MagicMock()

    # Mock docker.from_env() client (fourni via fixture autouse mock_docker_client)
    class DummyImage:
        def __init__(self, tag):
            self.tags = [tag]

    class DummyContainer:
        def __init__(self, tag):
            self.image = DummyImage(tag)

    # get() doit retourner un container avec la bonne image pour les deux appels
    def get_side_effect(name):
        return DummyContainer(expected_image)

    mock_docker_client.containers.get.side_effect = get_side_effect
    # list() peut être vide (pas d'extra containers)
    mock_docker_client.containers.list.return_value = []

    res = docker_service.start_runners()

    assert any(r["name"].startswith(cfg.runners[0].name_prefix) for r in res["running"])
    assert any(
        r["name"].startswith(cfg.runners[0].name_prefix) for r in res["restarted"]
    )


def test_start_runners_image_mismatch_redeploy(
    docker_service, config_service, mock_docker_client
):
    cfg = config_service.load_config.return_value
    # Restreindre à un seul runner pour éviter appels multiples sur d'autres techno
    cfg.runners = [cfg.runners[0]]
    cfg.runners[0].nb = 1

    class DummyImage:
        def __init__(self, tag):
            self.tags = [tag]

    class DummyContainer:
        def __init__(self, tag):
            self.image = DummyImage(tag)
            self.status = "running"

    mock_docker_client.containers.get.return_value = DummyContainer("old/other:image")
    mock_docker_client.containers.list.return_value = []

    # Mocks sur méthodes utilisées
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(return_value=True)
    docker_service.stop_container = MagicMock()
    docker_service.exec_command = MagicMock(side_effect=Exception("fail remove"))
    docker_service.remove_container = MagicMock()
    docker_service.run_container = MagicMock()
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.build_image = MagicMock()
    # Evite call API token
    docker_service._get_registration_token = MagicMock(return_value="tok123")

    res = docker_service.start_runners()

    # Vérifie qu'on a ajouté un started avec reason image updated
    assert any(r.get("reason") == "image updated" for r in res["started"])
    # stop_container doit être appelé au moins une fois avec le runner cible
    assert any(
        call.args[0] == f"{cfg.runners[0].name_prefix}-1"
        for call in docker_service.stop_container.mock_calls
    )
    docker_service.exec_command.assert_called_once()  # même si exception ignorée
    docker_service.remove_container.assert_called_once()
    docker_service.run_container.assert_called_once()


def test_list_runners_status_stopped(docker_service, config_service):
    docker_service.list_containers = MagicMock(return_value=["test-runner-1"])
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(return_value=False)
    config_service.load_config.return_value.runners[0].nb = 1
    res = docker_service.list_runners()
    assert res["groups"][0]["runners"][0]["status"] == "stopped"


def test_list_runners_extra_runners(docker_service, config_service):
    docker_service.list_containers = MagicMock(
        return_value=["foo", "test-runner-2", "test-runner-3"]
    )
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(
        side_effect=[False, False, False, False, True, False]
    )
    config_service.load_config.return_value.runners[0].nb = 1
    res = docker_service.list_runners()
    extra = res["groups"][0]["extra_runners"]
    assert any(
        e["name"] == "test-runner-2" and e["status"] == "will_be_removed" for e in extra
    )
    assert any(
        e["name"] == "test-runner-3" and e["status"] == "will_be_removed" for e in extra
    )


@patch("requests.get")
def test_get_latest_runner_version_tag_none(mock_get, docker_service):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"tag_name": None}
    mock_get.return_value = resp
    assert docker_service.get_latest_runner_version() is None


@patch(
    "src.services.docker_service.DockerService.get_latest_runner_version",
    return_value="2.301.0",
)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="foo: bar\nbase_image: ghcr.io/actions/runner:2.300.0\nother: val\n",
)
def test_check_base_image_update_else(
    mock_openfile, _latest, docker_service, config_service
):
    config_service.load_config.return_value.runners_defaults.base_image = (
        "ghcr.io/actions/runner:2.300.0"
    )
    res = docker_service.check_base_image_update(auto_update=True)
    assert res["updated"] is True
    handle = mock_openfile()
    writes = [call[0][0] for call in handle.write.call_args_list]
    assert any("foo: bar" in w or "other: val" in w for w in writes)


@patch("requests.post")
def test_get_registration_token_token_not_string(mock_post, docker_service):
    resp = MagicMock()
    resp.status_code = 201
    resp.json.return_value = {"token": 12345}
    mock_post.return_value = resp
    with pytest.raises(Exception) as exc:
        docker_service._get_registration_token(
            "https://github.com/org/test", github_personal_token="tok"
        )
    assert "Token returned by GitHub API is not a string" in str(exc.value)


@patch("requests.get")
def test_get_latest_runner_version_tag_string(mock_get, docker_service):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"tag_name": "v2.301.0"}
    mock_get.return_value = resp
    assert docker_service.get_latest_runner_version() == "2.301.0"
    resp.json.return_value = {"tag_name": "2.301.0"}
    mock_get.return_value = resp
    assert docker_service.get_latest_runner_version() == "2.301.0"
