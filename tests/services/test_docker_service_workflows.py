"""Consolidated workflow/branch tests for DockerService covering runner lifecycle, list, and image update cases."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.services.config_schema import FullConfig

# use shared `docker_service` fixture from tests/conftest.py


# build_runner_images branches
@patch("src.services.docker_service.DockerService.build_image")
def test_build_runner_images_branches(
    mock_build, docker_service, config_service, valid_config
):
    # build a fresh config based on the valid_config fixture and ensure the
    # first runner has no build_image so the branch is exercised
    cfg_data = valid_config.model_dump()
    cfg_data["runners"][0]["build_image"] = None
    cfg = FullConfig.model_validate(cfg_data)
    config_service.load_config.return_value = cfg
    # ensure docker_service has the same mocked return value
    try:
        docker_service.config_service.load_config.return_value = cfg
    except Exception:
        # if docker_service was initialized with a different object, set directly
        docker_service.config_service = config_service
    # debug: ensure change applied
    runner0 = config_service.load_config.return_value.runners[0]
    assert getattr(runner0, "build_image", "MISSING") is None
    res = docker_service.build_runner_images()
    assert res["skipped"]
    cfg.runners[0].build_image = "Df"
    cfg.runners[0].techno = None
    res = docker_service.build_runner_images()
    assert res["errors"]
    cfg.runners[0].techno = "python"
    mock_build.side_effect = Exception("fail")
    res = docker_service.build_runner_images()
    assert res["errors"]


# start_runners mixed behavior
def test_start_runners_branches(docker_service, config_service):
    """
    Optimized test for start_runners branches using direct instance mocking
    instead of multiple decorator patches.
    """
    # Configure mocks directly on the instance
    docker_service.image_exists = MagicMock(return_value=False)
    docker_service.build_image = MagicMock(side_effect=Exception("fail"))
    docker_service.list_containers = MagicMock(
        return_value=["test-runner-1", "test-runner-X"]
    )
    docker_service.container_running = MagicMock(side_effect=[True, False])
    docker_service.container_exists = MagicMock(side_effect=[True, False])
    docker_service._get_registration_token = MagicMock(return_value="tok")
    docker_service.run_container = MagicMock()

    # Set test configuration
    config_service.load_config.return_value.runners[0].nb = 1

    # Execute test
    res = docker_service.start_runners()

    # Assert expected outcomes
    assert "errors" in res and "started" in res


@pytest.mark.isolated
@patch("pathlib.Path.exists", return_value=True)
@patch("src.services.docker_service.shutil.rmtree")
def test_start_runners_removes_extra(
    _mock_rmtree, _mock_path_exists, docker_service, config_service
):
    """
    Optimized test for removal of extra runners with explicit isolation to avoid side effects.
    """
    # Reset complete des mocks pour éviter les effets de bord
    docker_service.list_containers = MagicMock(return_value=["test-runner-3"])
    docker_service.container_running = MagicMock(return_value=True)
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.start_container = MagicMock()
    docker_service.exec_command = MagicMock()
    docker_service.remove_container = MagicMock()

    # Configuration explicite pour ce test
    config_service.load_config.return_value.runners[0].nb = 2

    # Exécution du test
    res = docker_service.start_runners()

    # Assertions
    assert res["removed"]
    assert docker_service.remove_container.called


@pytest.mark.isolated
def test_start_runners_creates_and_starts(docker_service, config_service):
    """
    Optimized test for start runners creates and starts with explicit isolation.
    """
    # Reset complet pour éviter les effets de bord
    docker_service.container_exists = MagicMock(return_value=False)
    docker_service._get_registration_token = MagicMock(return_value="tok")
    docker_service.run_container = MagicMock()
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.list_containers = MagicMock(return_value=[])

    # Configuration
    cfg = config_service.load_config.return_value
    cfg.runners[0].nb = 1

    # Exécution
    res = docker_service.start_runners()

    # Assertion
    assert res["started"]


# stop_runners: stopped, skipped, error
def test_stop_runners_branches(docker_service, config_service):
    """
    Optimized test for stop_runners branches using direct instance mocking
    instead of decorator patches.
    """
    # Configure mocks directly on the instance
    docker_service.container_running = MagicMock(
        side_effect=[True, False, Exception("fail")]
    )
    docker_service.stop_container = MagicMock()

    # Set test configuration
    config_service.load_config.return_value.runners[0].nb = 3

    # Execute test
    res = docker_service.stop_runners()

    # Assert expected outcomes
    assert res["stopped"] and res["skipped"] and res["errors"]


# remove_runners: removed, skipped, errors
def test_remove_runners_branches(docker_service, config_service):
    """
    Optimized test for remove_runners branches using direct instance mocking
    instead of decorator patches.
    """
    # Configure mocks directly on the instance
    docker_service.container_exists = MagicMock(side_effect=[True, False, True])
    docker_service.container_running = MagicMock(return_value=False)
    docker_service.start_container = MagicMock()
    docker_service.exec_command = MagicMock()
    docker_service.remove_container = MagicMock()

    # Set test configuration
    config_service.load_config.return_value.runners[0].nb = 3

    # Execute test
    res = docker_service.remove_runners()

    # Assert expected outcomes
    assert res["removed"] and res["skipped"] and "errors" in res


def test_remove_runners_running_branch(docker_service, config_service):
    """
    Optimized test for remove_runners running branch using direct instance mocking
    instead of decorator patches.
    """
    # Configure mocks directly on the instance
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(return_value=True)
    docker_service.stop_container = MagicMock()
    docker_service.exec_command = MagicMock()
    docker_service.remove_container = MagicMock()

    # Set test configuration
    config_service.load_config.return_value.runners[0].nb = 1

    # Execute test
    res = docker_service.remove_runners()

    # Assert expected outcomes
    assert res["removed"]


def test_remove_runners_error_branch(docker_service, config_service):
    """
    Optimized test for remove_runners error branch using direct instance mocking
    instead of decorator patches.
    """
    # Configure mocks directly on the instance
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(side_effect=Exception("oops"))

    # Set test configuration
    config_service.load_config.return_value.runners[0].nb = 1

    # Execute test
    res = docker_service.remove_runners()

    # Assert expected outcomes
    assert res["errors"]


# list_runners: varied states & extra
def test_list_runners_branches(docker_service, config_service):
    """
    Optimized test for list_runners branches using direct instance mocking
    instead of decorator patches.
    """
    # Configure mocks directly on the instance
    docker_service.list_containers = MagicMock(
        return_value=["test-runner-1", "test-runner-2", "test-runner-X"]
    )
    docker_service.container_exists = MagicMock(
        side_effect=[True, False, True, False, True, False]
    )
    docker_service.container_running = MagicMock(side_effect=[True, False, True, False])

    # Set test configuration
    config_service.load_config.return_value.runners[0].nb = 2

    # Execute test
    res = docker_service.list_runners()

    # Assert expected outcomes
    assert "groups" in res and "total" in res


# check_base_image_update branches
@patch(
    "src.services.docker_service.DockerService.get_latest_runner_version",
    return_value=None,
)
def test_check_base_image_update_branches_none(_latest, docker_service, config_service):
    cfg = config_service.load_config.return_value
    cfg.runners_defaults.base_image = None
    assert docker_service.check_base_image_update()["error"]
    cfg.runners_defaults.base_image = "ghcr.io/actions/runner:2.300.0"
    assert docker_service.check_base_image_update()["error"]


@patch(
    "src.services.docker_service.DockerService.get_latest_runner_version",
    return_value="2.301.0",
)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="base_image: ghcr.io/actions/runner:2.300.0\n",
)
def test_check_base_image_update_auto_update(
    mock_openfile, _latest, docker_service, config_service
):
    config_service.load_config.return_value.runners_defaults.base_image = (
        "ghcr.io/actions/runner:2.300.0"
    )
    assert docker_service.check_base_image_update(auto_update=True)["updated"]
    mock_openfile.side_effect = Exception("fail")
    assert docker_service.check_base_image_update(auto_update=True)["error"]


@patch(
    "src.services.docker_service.DockerService.get_latest_runner_version",
    return_value="2.300.0",
)
def test_check_base_image_update_no_change(_latest, docker_service, config_service):
    config_service.load_config.return_value.runners_defaults.base_image = (
        "ghcr.io/actions/runner:2.300.0"
    )
    res = docker_service.check_base_image_update(auto_update=True)
    assert not res["update_available"] and not res.get("updated")


def test_start_runners_extra_not_removed_when_index_not_greater(
    docker_service, config_service
):
    """
    Optimized test for verifying that runners are not removed when index <= nb
    using direct instance mocking instead of decorator patches.
    """
    # Configure mocks directly on the instance
    docker_service.image_exists = MagicMock(return_value=True)
    docker_service.list_containers = MagicMock(
        return_value=["test-runner-1", "test-runner-2"]
    )
    docker_service.container_exists = MagicMock(return_value=True)
    docker_service.container_running = MagicMock(return_value=True)

    # Set test configuration
    cfg = config_service.load_config.return_value
    cfg.runners[0].nb = 2

    # Execute test
    res = docker_service.start_runners()

    # Assert expected outcomes - No removal since indexes are not greater than nb
    assert res["removed"] == []


@patch(
    "src.services.docker_service.DockerService.get_latest_runner_version",
    return_value="2.301.0",
)
def test_check_base_image_update_available_no_auto_update(
    _latest, docker_service, config_service
):
    config_service.load_config.return_value.runners_defaults.base_image = (
        "ghcr.io/actions/runner:2.300.0"
    )
    res = docker_service.check_base_image_update(auto_update=False)
    assert res["update_available"] is True and res["updated"] is False
