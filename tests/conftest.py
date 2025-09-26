"""Global fixtures and pytest configuration.

- Provides shared mocked services
- Exposes a factory to quickly create a mocked ConfigService with a given config
- Exposes a shared CliRunner for CLI tests
"""

from copy import deepcopy
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import yaml
from typer.testing import CliRunner

from src.services import ConfigService, DockerService
from src.services.config_schema import FullConfig


@pytest.fixture(autouse=True)
def block_real_webhook_requests():
    """Prevent any outgoing HTTP requests via requests.post (webhooks) during tests."""
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "MOCKED"
        yield mock_post


@pytest.fixture(autouse=True)
def mock_webhook_service():
    """Global patch of WebhookService to disable real notifications in all tests."""
    with patch("src.services.notification_service.WebhookService") as mock:
        yield mock


@pytest.fixture
def valid_config():
    """Fixture for a valid runners configuration."""
    return FullConfig.model_validate(
        {
            "runners_defaults": {
                "base_image": "ghcr.io/actions/runner:2.300.0",
                "org_url": "https://github.com/test-org",
            },
            "runners": [
                {
                    "id": "test-php",
                    "name_prefix": "test-runner-php",
                    "labels": ["test-label-php", "php8.2"],
                    "nb": 2,
                    "techno": "php",
                    "techno_version": "8.2",
                    "build_image": "./config/Dockerfile.php82",
                },
                {
                    "id": "test-node",
                    "name_prefix": "test-runner-node",
                    "labels": ["test-label-node", "node18"],
                    "nb": 1,
                    "techno": "node",
                    "techno_version": "18",
                    "build_image": "./config/Dockerfile.node18",
                },
            ],
        }
    )


@pytest.fixture
def config_file(valid_config, tmp_path):
    """Fixture for a temporary configuration file."""
    config_path = tmp_path / "test_config.yaml"
    # valid_config est un FullConfig, on le convertit en dict pour YAML
    with open(config_path, "w") as f:
        yaml.dump(valid_config.model_dump(), f)
    return str(config_path)


@pytest.fixture
def mock_config_service(valid_config):
    """Fixture for a mocked configuration service."""
    service = create_autospec(ConfigService, spec_set=True)
    service.load_config.return_value = valid_config
    return service


@pytest.fixture
def config_service_factory(valid_config):
    """Factory to create a mocked ConfigService with overrides.

    Example usage:
        service = config_service_factory({"runners": [...]})
    """

    def _factory(overrides: dict | None = None) -> MagicMock:
        cfg = deepcopy(valid_config)
        if overrides:
            # Merge naïf et récursif minimal
            def _merge(dst, src):
                for k, v in src.items():
                    if isinstance(v, dict) and isinstance(dst.get(k), dict):
                        _merge(dst[k], v)
                    else:
                        dst[k] = v
                return dst

            cfg = _merge(cfg, deepcopy(overrides))

        service = create_autospec(ConfigService, spec_set=True)
        service.load_config.return_value = cfg
        return service

    return _factory


@pytest.fixture
def config_service(config_service_factory):
    """Compatibility alias for tests still expecting `config_service`."""
    return config_service_factory()


@pytest.fixture(autouse=True)
def mock_docker_client():
    """Global patch of docker.from_env to prevent any real Docker access."""
    with patch("docker.from_env") as mock_docker:
        client = MagicMock()
        mock_docker.return_value = client
        yield client


@pytest.fixture(autouse=True)
def isolate_env_and_sleep(monkeypatch):
    """Quick isolation: no GitHub token or blocking sleep by default.

    - Removes GITHUB_TOKEN to force the short path in _get_registration_token.
    - Neutralizes time.sleep in the docker_service module to avoid any waiting.
    """
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # Neutraliser exclusivement le sleep utilisé dans docker_service
    monkeypatch.setattr(
        "src.services.docker_service.time.sleep",
        lambda *_args, **_kwargs: None,
        raising=False,
    )


@pytest.fixture
def docker_service(config_service):
    """Fixture for the Docker service with mocked config (uses shared config_service)."""
    return DockerService(config_service)


@pytest.fixture(autouse=True)
def enforce_autospec_on_service_mocks(request):
    """If a test uses `docker_service` or `config_service` and assigns
    plain MagicMock objects to methods, replace those mocks by autospecced
    mocks (create_autospec with spec_set=True) so invalid method calls
    are detected.

    This is a low-risk, backward-compatible enforcement: it only replaces
    MagicMocks already attached to the service instance.
    """
    from unittest.mock import MagicMock

    try:
        docker = request.getfixturevalue("docker_service")
    except Exception:
        docker = None

    try:
        cfgs = request.getfixturevalue("config_service")
    except Exception:
        cfgs = None

    def _wrap_object(obj, klass):
        if obj is None:
            return
        for name in dir(klass):
            if name.startswith("_"):
                continue
            # only consider callables defined on the class
            try:
                attr = getattr(klass, name)
            except AttributeError:
                continue
            if not callable(attr):
                continue
            if not hasattr(obj, name):
                continue
            current = getattr(obj, name)
            # replace plain MagicMock without a spec by an autospecced mock
            # If the attribute is a bare MagicMock without a spec, replace it
            if (
                isinstance(current, MagicMock)
                and getattr(current, "_spec_class", None) is None
            ):
                try:
                    new = MagicMock(spec_set=attr)
                    if hasattr(current, "return_value"):
                        new.return_value = current.return_value
                    if hasattr(current, "side_effect"):
                        new.side_effect = current.side_effect
                    setattr(obj, name, new)
                    continue
                except Exception:
                    pass

            # If attribute is a plain callable (function) assigned on the instance
            # replace it with a MagicMock(spec_set=attr) to enforce the API.
            if (
                callable(current)
                and not hasattr(current, "__get__")
                and not isinstance(current, MagicMock)
            ):
                try:
                    new = MagicMock(spec_set=attr)
                    setattr(obj, name, new)
                except Exception:
                    pass

    _wrap_object(docker, DockerService)
    _wrap_object(cfgs, ConfigService)
    yield


@pytest.fixture
def real_config_service(config_file):
    """Fixture for a real configuration service with a temporary file."""
    return ConfigService(config_file)


@pytest.fixture
def real_docker_service(real_config_service):
    """Fixture for a real Docker service with a temporary configuration file."""
    return DockerService(real_config_service)


@pytest.fixture(scope="session")
def cli():
    """Shared CliRunner for all CLI tests."""
    return CliRunner()
