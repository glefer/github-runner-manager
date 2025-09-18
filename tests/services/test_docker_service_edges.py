"""Consolidated edge-case tests for DockerService utils and tokens."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.config_service import ConfigService
from src.services.docker_service import DockerService


@pytest.fixture
def config_service():
    return MagicMock(spec=ConfigService)


@pytest.fixture
def docker_service(config_service):
    return DockerService(config_service)


# _get_registration_token success branches (org and repo)
@patch("requests.post")
@patch("os.getenv", return_value="tok")
def test_get_registration_token_org(_getenv, mock_post, docker_service):
    resp = MagicMock()
    resp.status_code = 201
    resp.json.return_value = {"token": "abc"}
    mock_post.return_value = resp
    tok = docker_service._get_registration_token("https://github.com/myorg/")
    assert tok == "abc"
    assert (
        mock_post.call_args[0][0]
        == "https://api.github.com/orgs/myorg/actions/runners/registration-token"
    )


@patch("requests.post")
@patch("os.getenv", return_value="tok")
def test_get_registration_token_repo(_getenv, mock_post, docker_service):
    resp = MagicMock()
    resp.status_code = 201
    resp.json.return_value = {"token": "xyz"}
    mock_post.return_value = resp
    tok = docker_service._get_registration_token("https://github.com/owner/repo")
    assert tok == "xyz"
    assert (
        mock_post.call_args[0][0]
        == "https://api.github.com/repos/owner/repo/actions/runners/registration-token"
    )


# Failures: missing token, bad status, retries
def test_get_registration_token_fail(docker_service):
    """
    Optimized test for token failure cases using context managers and patching time.sleep
    to eliminate wait delays that slow down the test.
    """
    # Patch time.sleep to eliminate delays
    with patch("src.services.docker_service.time.sleep") as mock_sleep:
        # Test case 1: Missing environment token
        with patch("os.getenv", return_value=None):
            with pytest.raises(Exception) as e:
                docker_service._get_registration_token("https://github.com/test-org")
            assert "token GitHub n'est pas défini" in str(e.value)

        # Test case 2: Bad status code - All cases at once
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "fail"

        with (
            patch("os.getenv", return_value="tok"),
            patch("requests.post", return_value=mock_response),
        ):
            with pytest.raises(Exception):
                docker_service._get_registration_token(
                    "https://github.com/test-org", "tok"
                )

            # Make sure sleep was called exactly 3 times (retries)
            assert mock_sleep.call_count == 3


# Utility-level docker ops
def test_exec_start_stop_remove_and_exceptions(docker_service):
    from unittest.mock import mock_open

    with (
        patch("docker.from_env") as mock_docker,
        patch("builtins.open", mock_open(read_data="")),
    ):
        client = MagicMock()
        mock_docker.return_value = client
        cont = MagicMock()
        client.containers.get.return_value = cont
        docker_service.exec_command("c", "ls")
        cont.exec_run.assert_called_once()
        docker_service.start_container("c")
        assert cont.start.called
        docker_service.stop_container("c")
        assert cont.stop.called
        docker_service.remove_container("c")
        assert cont.remove.called
    with patch("docker.from_env") as mock_docker:
        client = MagicMock()
        mock_docker.return_value = client
        client.containers.get.side_effect = Exception("fail")
        with pytest.raises(Exception):
            docker_service.exec_command("c", "ls")
        with pytest.raises(Exception):
            docker_service.start_container("c")
        with pytest.raises(Exception):
            docker_service.stop_container("c")
        with pytest.raises(Exception):
            docker_service.remove_container("c")


# get_latest_runner_version
def test_get_latest_runner_version(docker_service):
    with patch("requests.get") as mock_get:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"tag_name": "v2.300.0"}
        mock_get.return_value = resp
        assert docker_service.get_latest_runner_version() == "2.300.0"
    with patch("requests.get", side_effect=Exception("fail")):
        assert docker_service.get_latest_runner_version() is None
