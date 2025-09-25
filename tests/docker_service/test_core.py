from unittest.mock import MagicMock, mock_open, patch

import docker
import pytest

from src.services import ConfigService, DockerService


@pytest.fixture
def config_service(valid_config):
    service = MagicMock(spec=ConfigService)
    service.load_config.return_value = valid_config
    return service


@pytest.fixture
def docker_service(config_service):
    return DockerService(config_service)


@pytest.fixture
def mock_docker_client():
    with patch("docker.from_env") as mock_docker:
        client = MagicMock()
        mock_docker.return_value = client
        yield client


@pytest.mark.parametrize("exists", [True, False])
def test_container_exists(docker_service, mock_docker_client, exists):
    if exists:
        mock_docker_client.containers.get.return_value = MagicMock()
    else:
        mock_docker_client.containers.get.side_effect = Exception("not found")
    assert docker_service.container_exists("c") is exists


def test_container_exists_notfound(docker_service, mock_docker_client):
    mock_docker_client.containers.get.side_effect = docker.errors.NotFound("nf")
    assert docker_service.container_exists("c") is False


@pytest.mark.parametrize(
    "status,expected", [("running", True), ("stopped", False), (None, False)]
)
def test_container_running(docker_service, mock_docker_client, status, expected):
    if status is None:
        mock_docker_client.containers.get.side_effect = Exception("nf")
    else:
        cont = MagicMock()
        cont.status = status
        mock_docker_client.containers.get.return_value = cont
    assert docker_service.container_running("c") is expected


@pytest.mark.parametrize("present", [True, False])
def test_image_exists(docker_service, mock_docker_client, present):
    mock_docker_client.images.list.return_value = [MagicMock()] if present else []
    assert docker_service.image_exists("img") is present


@patch("subprocess.run")
def test_run_command(mock_run, docker_service):
    docker_service.run_command(["echo", "hi"])
    mock_run.assert_called_once()


def test_container_running_notfound(docker_service, mock_docker_client):
    mock_docker_client.containers.get.side_effect = docker.errors.NotFound("nf")
    assert docker_service.container_running("c") is False


def test_image_exists_exception(docker_service, mock_docker_client):
    mock_docker_client.images.list.side_effect = Exception("boom")
    assert docker_service.image_exists("img") is False


def test_build_image_happy_path(docker_service):
    with (
        patch("docker.from_env") as mock_docker,
        patch("builtins.open", mock_open(read_data=b"")),
    ):
        client = MagicMock()
        api_client = MagicMock()
        client.api = api_client
        mock_docker.return_value = client
        docker_service.build_image(
            image_tag="itroom/python:3.11-2.300.0",
            dockerfile_path="config/Dockerfile.node20",
            build_dir="config",
            build_args={"BASE_IMAGE": "ghcr.io/actions/runner:2.300.0"},
        )
        api_client.build.assert_called_once()
        args, kwargs = api_client.build.call_args
        assert kwargs["path"] == "config"
        assert kwargs["dockerfile"] == "Dockerfile.node20"
        assert kwargs["tag"] == "itroom/python:3.11-2.300.0"
        assert kwargs["buildargs"] == {"BASE_IMAGE": "ghcr.io/actions/runner:2.300.0"}


def test_run_container_command_building(docker_service):
    with patch.object(docker_service, "run_command") as mock_run:
        docker_service.run_container(
            name="r1",
            image="itroom/python:3.11-2.300.0",
            command="echo hi",
            env_vars={"A": "1", "B": "2"},
            detach=True,
        )
        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[:2] == ["docker", "run"]
        assert "-d" in called_cmd
        assert "--name" in called_cmd and "r1" in called_cmd
        assert "--restart" in called_cmd and "always" in called_cmd
        assert "-e" in called_cmd and "A=1" in called_cmd and "B=2" in called_cmd
        assert "itroom/python:3.11-2.300.0" in called_cmd
        assert (
            "/bin/bash" in called_cmd and "-c" in called_cmd and "echo hi" in called_cmd
        )


def test_run_container_no_command_no_detach(docker_service):
    with patch.object(docker_service, "run_command") as mock_run:
        docker_service.run_container(
            name="r2",
            image="img:latest",
            command="",
            env_vars={},
            detach=False,
        )
        called_cmd = mock_run.call_args[0][0]
        assert "-d" not in called_cmd
        assert "/bin/bash" not in called_cmd


def test_list_containers_filtering(docker_service):
    with patch("docker.from_env") as mock_docker:
        client = MagicMock()
        mock_docker.return_value = client
        c1 = MagicMock()
        c1.name = "foo-1"
        c2 = MagicMock()
        c2.name = "bar-1"
        client.containers.list.return_value = [c1, c2]
        all_names = docker_service.list_containers()
        assert set(all_names) == {"foo-1", "bar-1"}
        filtered = docker_service.list_containers("foo-")
        assert filtered == ["foo-1"]
