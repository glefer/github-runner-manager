import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.services import ConfigService
from src.services.config_schema import FullConfig


def test_init_default_path():
    service = ConfigService()
    assert service._path == Path("runners_config.yaml")


def test_init_custom_path():
    service = ConfigService("/custom/path.yaml")
    assert service._path == Path("/custom/path.yaml")


def test_load_config(config_file, valid_config):
    service = ConfigService(config_file)
    config = service.load_config()

    assert isinstance(config, FullConfig)
    assert config.model_dump() == valid_config.model_dump()


def test_load_config_file_not_found():
    service = ConfigService("/non/existent/path.yaml")
    with pytest.raises(FileNotFoundError):
        service.load_config()


def test_load_config_empty_file(tmp_path):
    empty_path = tmp_path / "empty.yaml"
    with open(empty_path, "w") as f:
        f.write("")
    service = ConfigService(str(empty_path))
    with pytest.raises(ValidationError):
        service.load_config()


def test_save_config_with_pydantic_model(tmp_path, valid_config):
    config_path = tmp_path / "save_test_pydantic.yaml"
    service = ConfigService(str(config_path))
    service.save_config(valid_config)
    assert config_path.exists()
    with open(config_path, "r") as f:
        saved_config = yaml.safe_load(f)
    assert saved_config == valid_config.model_dump()


def test_save_config_with_dict(tmp_path):
    config_path = tmp_path / "save_test.yaml"
    service = ConfigService(str(config_path))
    test_config = {
        "runners_defaults": {
            "base_image": "new-image:2.0.0",
            "org_url": "https://github.com/test-org",
        },
        "runners": [
            {
                "id": "test",
                "name_prefix": "test-runner",
                "labels": ["test-label"],
                "nb": 1,
                "build_image": "./Dockerfile.test",
                "techno": "python",
                "techno_version": "3.11",
            }
        ],
    }
    service.save_config(test_config)
    assert config_path.exists()
    with open(config_path, "r") as f:
        saved_config = yaml.safe_load(f)
    assert saved_config == test_config


def test_get_config_path():
    with tempfile.NamedTemporaryFile() as temp:
        service = ConfigService(temp.name)
        path = service.get_config_path()
        assert path == str(Path(temp.name).absolute())
