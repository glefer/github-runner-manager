from unittest.mock import MagicMock, patch

from src.services import ConfigService, DockerService


def _single_step_stream():
    yield {"stream": "Step 3/10 : RUN echo 'hi'\n"}
    yield {"stream": "Step 4/10 : RUN echo 'bye'\n"}


def test_quiet_logger_early_return():
    with patch("docker.from_env") as mock_docker, patch("builtins.print") as mock_print:
        client = MagicMock()
        api_client = MagicMock()
        client.api = api_client
        api_client.build.return_value = _single_step_stream()
        mock_docker.return_value = client
        config_service = MagicMock(spec=ConfigService)
        docker_service = DockerService(config_service)
        docker_service.build_image(
            image_tag="img:tag",
            dockerfile_path="config/Dockerfile.node20",
            build_dir="config",
            quiet=True,
        )
    printed = [call.args[0] for call in mock_print.call_args_list]
    assert printed == [
        "Step 3/10 : RUN echo 'hi'",
        "Step 4/10 : RUN echo 'bye'",
    ]
