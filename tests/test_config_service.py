"""Tests pour le service de configuration."""

import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.services import ConfigService
from src.services.config_schema import FullConfig


@pytest.fixture
def valid_config():
    """Fixture pour une configuration valide."""
    return {
        "runners_defaults": {
            "base_image": "test-image:1.0.0",
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


@pytest.fixture
def config_file(valid_config, tmp_path):
    """Fixture pour un fichier de configuration temporaire."""
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(valid_config, f)
    return str(config_path)


def test_init_default_path():
    """Test l'initialisation avec le chemin par défaut."""
    service = ConfigService()
    assert service._path == Path("runners_config.yaml")


def test_init_custom_path():
    """Test l'initialisation avec un chemin personnalisé."""
    service = ConfigService("/custom/path.yaml")
    assert service._path == Path("/custom/path.yaml")


def test_load_config(config_file, valid_config):
    """Test le chargement d'une configuration valide."""
    service = ConfigService(config_file)
    config = service.load_config()
    from src.services.config_schema import FullConfig

    assert isinstance(config, FullConfig)
    assert config.model_dump() == valid_config


def test_load_config_file_not_found():
    """Test le chargement d'une configuration inexistante."""
    service = ConfigService("/non/existent/path.yaml")
    with pytest.raises(FileNotFoundError):
        service.load_config()


def test_load_config_empty_file(tmp_path):
    """Test le chargement d'un fichier de configuration vide."""
    empty_path = tmp_path / "empty.yaml"
    with open(empty_path, "w") as f:
        f.write("")
    service = ConfigService(str(empty_path))
    with pytest.raises(ValidationError):
        service.load_config()


def test_save_config_with_pydantic_model(tmp_path, valid_config):
    """Test la sauvegarde d'une configuration en passant un modèle Pydantic (FullConfig)."""

    config_path = tmp_path / "save_test_pydantic.yaml"
    service = ConfigService(str(config_path))

    model = FullConfig.model_validate(valid_config)
    service.save_config(model)

    assert config_path.exists()
    with open(config_path, "r") as f:
        saved_config = yaml.safe_load(f)
    assert saved_config == valid_config
    """Test la sauvegarde d'une configuration."""
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
    """Test la récupération du chemin absolu du fichier de configuration."""
    with tempfile.NamedTemporaryFile() as temp:
        service = ConfigService(temp.name)
        path = service.get_config_path()
        assert path == str(Path(temp.name).absolute())
