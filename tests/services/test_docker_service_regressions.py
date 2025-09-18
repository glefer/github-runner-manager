from unittest.mock import MagicMock, mock_open, patch

import pytest


@pytest.mark.isolated
@patch("src.services.docker_service.DockerService.image_exists", return_value=False)
@patch("src.services.docker_service.DockerService.build_image")
def test_start_runners_build_image_missing_techno(
    mock_build, _img, docker_service, config_service
):
    """
    Optimized test for build image with missing techno with explicit isolation.
    """
    # Reset complet pour éviter les effets de bord
    cfg = config_service.load_config.return_value
    cfg.runners[0].techno = None
    cfg.runners[0].techno_version = None
    mock_build.side_effect = Exception("fail")

    # Exécution du test
    res = docker_service.start_runners()

    # Assertion
    assert any("Build failed" in e["reason"] for e in res["errors"])


@pytest.mark.isolated
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
    """Parametrized: ensure unwanted containers are detected/removed in similar edge cases."""
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.build_image = MagicMock()
    docker_service.list_containers = MagicMock(return_value=containers)
    docker_service.container_running = MagicMock(return_value=False)
    docker_service.remove_container = MagicMock()
    docker_service.exec_command = MagicMock()

    # Configuration explicite pour ce test
    config_service.load_config.return_value.runners[0].nb = 1

    # Exécution
    res = docker_service.start_runners()

    assert any(r.get("name") == "test-runner-2" for r in res["removed"]) or any(
        r.get("id") == "test-runner-2" for r in res["removed"]
    )


@pytest.mark.isolated
@patch("pathlib.Path.exists", return_value=False)
def test_start_runners_removal_exception(
    _mock_path_exists, docker_service, config_service
):
    """
    Optimized test for removal exception case with explicit isolation to avoid side effects.
    """
    # Reset complet des mocks pour éviter les effets de bord
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.build_image = MagicMock()
    docker_service.list_containers = MagicMock(return_value=["test-runner-2"])
    docker_service.container_running = MagicMock(return_value=False)
    docker_service.remove_container = MagicMock(side_effect=Exception("remove failed"))
    docker_service.exec_command = MagicMock()

    # Configuration explicite pour ce test
    config_service.load_config.return_value.runners[0].nb = 1

    # Exécution du test
    res = docker_service.start_runners()

    # Assertions
    assert any(
        r.get("operation") == "removal" and "remove failed" in r.get("reason", "")
        for r in res["errors"]
    )


@pytest.mark.isolated
def test_start_runners_running_and_restarted(docker_service, config_service):
    """
    Optimized test for start runners with running and restarted runners with explicit isolation.
    """
    # Reset complet pour éviter les effets de bord
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.build_image = MagicMock()
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(side_effect=[True, False])
    docker_service.start_container = MagicMock()

    # Configuration
    config_service.load_config.return_value.runners[0].nb = 2

    # Exécution
    res = docker_service.start_runners()

    # Assertions
    assert any(r["name"].startswith("test-runner") for r in res["running"]) and any(
        r["name"].startswith("test-runner") for r in res["restarted"]
    )


@pytest.mark.isolated
def test_list_runners_status_stopped(docker_service, config_service):
    """
    Optimized test for list runners status stopped with explicit isolation.
    """
    # Reset complet pour éviter les effets de bord
    docker_service.list_containers = MagicMock(return_value=["test-runner-1"])
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(return_value=False)

    # Configuration
    config_service.load_config.return_value.runners[0].nb = 1

    # Exécution
    res = docker_service.list_runners()

    # Assertion
    assert res["groups"][0]["runners"][0]["status"] == "stopped"


@pytest.mark.isolated
def test_list_runners_extra_runners(docker_service, config_service):
    """
    Optimized test for list runners with extra runners with explicit isolation.
    """
    # Reset complet pour éviter les effets de bord
    docker_service.list_containers = MagicMock(
        return_value=["foo", "test-runner-2", "test-runner-3"]
    )
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(
        side_effect=[False, False, False, False, True, False]
    )

    # Configuration
    config_service.load_config.return_value.runners[0].nb = 1

    # Exécution
    res = docker_service.list_runners()
    extra = res["groups"][0]["extra_runners"]

    # Assertions
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


@pytest.fixture(autouse=False)
def _unused_config_fixture():
    """Legacy placeholder removed; tests should use `config_service_factory`."""
    yield


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
