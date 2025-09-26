"""Simplified configuration service."""

from pathlib import Path
from typing import Any

import yaml

from .config_schema import FullConfig


class ConfigService:
    """Load runner configuration from a YAML file."""

    def __init__(self, path: str = "runners_config.yaml"):
        self._path = Path(path)

    def load_config(self) -> FullConfig:
        """
        Load and validate configuration from the YAML file.
        """
        if not self._path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self._path}")
        with self._path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return FullConfig.model_validate(raw)

    def save_config(self, config: Any) -> None:
        """
        Save configuration to the YAML file.
        """
        if hasattr(config, "model_dump"):
            config = config.model_dump()
        with self._path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

    def get_config_path(self) -> str:
        """
        Return the absolute path to the configuration file.
        """
        return str(self._path.absolute())
