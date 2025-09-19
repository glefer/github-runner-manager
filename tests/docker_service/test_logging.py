from unittest.mock import MagicMock, patch

from src.services import ConfigService, DockerService


def _build_stream(lines):
    for line in lines:
        yield {"stream": line + "\n"}


def test_build_image_quiet_logger_filters():
    stream_lines = [
        "",
        "   ",
        "# random comment that should be skipped",
        "Step 1/12 : FROM python:3.11",
        " ---> Using cache",
        "Step 2/12 : RUN echo hi",
        "Step 3/12 : RUN echo ERROR inside step",
        "some intermediate output",
        "Successfully built deadbeef",
        "Successfully tagged itroom/python:latest",
        "ERROR something failed",
        "SUCCESSFULLY starting deployment",
    ]
    with patch("docker.from_env") as mock_docker, patch("builtins.print") as mock_print:
        client = MagicMock()
        api_client = MagicMock()
        client.api = api_client
        api_client.build.return_value = _build_stream(stream_lines)
        mock_docker.return_value = client
        config_service = MagicMock(spec=ConfigService)
        docker_service = DockerService(config_service)
        docker_service.build_image(
            image_tag="itroom/python:latest",
            dockerfile_path="config/Dockerfile.node20",
            build_dir="config",
            quiet=True,
        )
    printed = [call.args[0] for call in mock_print.call_args_list]
    expected = [
        "Step 1/12 : FROM python:3.11",
        "Step 2/12 : RUN echo hi",
        "Step 3/12 : RUN echo ERROR inside step",
        "Successfully built deadbeef",
        "Successfully tagged itroom/python:latest",
        "ERROR something failed",
        "SUCCESSFULLY starting deployment",
    ]
    assert printed == expected


def test_build_image_uses_docker_build_logger():
    with patch(
        "src.services.docker_logger.DockerBuildLogger.get_logger"
    ) as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        with patch("docker.from_env") as mock_docker:
            client = MagicMock()
            api_client = MagicMock()
            api_client.build.return_value = []
            client.api = api_client
            mock_docker.return_value = client
            config_service = MagicMock(spec=ConfigService)
            docker_service = DockerService(config_service)
            docker_service.build_image(
                image_tag="test:latest",
                dockerfile_path="test/Dockerfile",
                build_dir="test",
                quiet=True,
            )
    mock_get_logger.assert_called_once_with(True)


def test_build_image_default_logger_prints_all():
    stream_lines = ["one", "two", "three"]
    with patch("docker.from_env") as mock_docker, patch("builtins.print") as mock_print:
        client = MagicMock()
        api_client = MagicMock()
        client.api = api_client
        api_client.build.return_value = _build_stream(stream_lines)
        mock_docker.return_value = client
        config_service = MagicMock(spec=ConfigService)
        docker_service = DockerService(config_service)
        docker_service.build_image(
            image_tag="itroom/python:latest",
            dockerfile_path="config/Dockerfile.node20",
            build_dir="config",
            quiet=False,
        )
    printed = [call.args[0] for call in mock_print.call_args_list]
    assert printed == stream_lines


def test_build_image_logger_none_triggers_get_logger():
    with (
        patch(
            "src.services.docker_logger.DockerBuildLogger.get_logger"
        ) as mock_get_logger,
        patch("docker.from_env") as mock_docker,
    ):
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        client = MagicMock()
        api_client = MagicMock()
        api_client.build.return_value = iter(
            [
                {"stream": "Step 1/1 : FROM python:3.11\n"},
                {"stream": "Successfully built abcdef\n"},
            ]
        )
        client.api = api_client
        mock_docker.return_value = client
        config_service = MagicMock(spec=ConfigService)
        docker_service = DockerService(config_service)
        docker_service.build_image(
            image_tag="img:tag",
            dockerfile_path="config/Dockerfile.node20",
            build_dir="config",
            logger=None,
            quiet=True,
            use_progress=False,
        )
        mock_get_logger.assert_called_once_with(True)
        assert mock_logger.call_count == 2


def test_build_image_logger_given_skips_get_logger_and_progress():
    with (
        patch("src.services.docker_service.Progress") as mock_progress_cls,
        patch("docker.from_env") as mock_docker,
    ):
        progress_instance = MagicMock()
        progress_instance.__enter__.return_value = progress_instance
        progress_instance.__exit__.return_value = False
        mock_progress_cls.return_value = progress_instance
        client = MagicMock()
        api_client = MagicMock()
        api_client.build.return_value = iter(
            [
                {"stream": "Step 1/1 : FROM python:3.11\n"},
                {"stream": "Successfully built abcdef\n"},
            ]
        )
        client.api = api_client
        mock_docker.return_value = client
        config_service = MagicMock(spec=ConfigService)
        docker_service = DockerService(config_service)
        custom_logger = MagicMock()
        with patch(
            "src.services.docker_logger.DockerBuildLogger.get_logger"
        ) as mock_get_logger:
            docker_service.build_image(
                image_tag="img:tag",
                dockerfile_path="config/Dockerfile.node20",
                build_dir="config",
                logger=custom_logger,
                quiet=True,
                use_progress=True,
            )
            mock_get_logger.assert_not_called()
        assert mock_progress_cls.called
        assert custom_logger.call_count == 0
