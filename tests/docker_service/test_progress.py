from unittest.mock import MagicMock, patch

import pytest

from src.services import ConfigService, DockerService


@pytest.fixture
def config_service(valid_config):
    svc = MagicMock(spec=ConfigService)
    svc.load_config.return_value = valid_config
    return svc


@pytest.fixture
def docker_service(config_service):
    return DockerService(config_service)


def _progress_stream_success():
    yield None
    yield {"stream": "Step 1/3 : FROM base\n"}
    yield {"stream": "Step 2/3 : RUN echo hi\n"}
    yield {"stream": "Some other output\n"}
    yield {"status": "Downloading", "progress": "[=====>     ]"}
    yield {"status": "Pull complete"}
    yield {"foo": "bar"}
    yield "raw-line"


class DummyStream:
    def __init__(self, inner):
        self._inner = iter(inner())

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._inner)

    def close(self):
        raise Exception("close boom")


def test_build_image_progress_success(docker_service):
    with (
        patch("docker.from_env") as mock_docker,
        patch("src.services.docker_service.Progress") as mock_progress_cls,
    ):
        client = MagicMock()
        api_client = MagicMock()
        client.api = api_client
        mock_docker.return_value = client
        progress_instance = MagicMock()
        progress_instance.__enter__.return_value = progress_instance
        progress_instance.__exit__.return_value = False
        mock_progress_cls.return_value = progress_instance
        api_client.build.return_value = DummyStream(_progress_stream_success)
        docker_service.build_image(
            image_tag="img:tag",
            dockerfile_path="config/Dockerfile.node20",
            build_dir="config",
            use_progress=True,
        )


def _progress_stream_error():
    yield {"stream": "Step 1/2 : FROM base\n"}
    yield {"stream": "Step 2/2 : RUN something\n"}
    yield {"error": "Docker build failed"}


class DummyErrStream(DummyStream):
    def __init__(self):
        super().__init__(_progress_stream_error)


def test_build_image_progress_error(docker_service):
    with (
        patch("docker.from_env") as mock_docker,
        patch("src.services.docker_service.Progress") as mock_progress_cls,
    ):
        client = MagicMock()
        api_client = MagicMock()
        client.api = api_client
        mock_docker.return_value = client
        progress_instance = MagicMock()
        progress_instance.__enter__.return_value = progress_instance
        progress_instance.__exit__.return_value = False
        mock_progress_cls.return_value = progress_instance
        api_client.build.return_value = DummyErrStream()
        with pytest.raises(Exception) as exc:
            docker_service.build_image(
                image_tag="img:tag",
                dockerfile_path="config/Dockerfile.node20",
                build_dir="config",
                use_progress=True,
            )
        assert "Docker build failed" in str(exc.value)


class NonProgressStream:
    def __init__(self, chunks):
        self._chunks = iter(chunks)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._chunks)

    def close(self):
        raise Exception("close failure")


@patch("src.services.docker_service.docker.from_env")
def test_build_image_nonprogress_error_path(mock_from_env, docker_service):
    chunks = [
        None,
        {"status": "Downloading", "progress": "[====]"},
        {"status": "Pull complete"},
        {"error": "boom"},
    ]
    client = MagicMock()
    api_client = MagicMock()
    client.api = api_client
    mock_from_env.return_value = client
    api_client.build.return_value = NonProgressStream(chunks)
    with pytest.raises(Exception) as exc:
        docker_service.build_image(
            image_tag="img:tag",
            dockerfile_path="config/Dockerfile.node20",
            build_dir="config",
        )
    assert "boom" in str(exc.value)


@patch("src.services.docker_service.docker.from_env")
@patch("builtins.print")
def test_build_image_nonprogress_fallback_and_nondict(
    mock_print, mock_from_env, docker_service
):
    chunks = [
        {"foo": "bar"},
        "raw-line",
    ]
    client = MagicMock()
    api_client = MagicMock()
    client.api = api_client
    mock_from_env.return_value = client
    api_client.build.return_value = NonProgressStream(chunks)
    docker_service.build_image(
        image_tag="img:tag",
        dockerfile_path="config/Dockerfile.node20",
        build_dir="config",
    )
    printed = [c.args[0] for c in mock_print.call_args_list]
    assert printed == ["{'foo': 'bar'}", "raw-line"]
