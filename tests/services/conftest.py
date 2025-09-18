"""Configuration de tests spécifique au dossier services.

Ce module fournit des fixtures et des hooks pour les tests dans le dossier services.
"""

import sys

import pytest


def pytest_configure(config):
    """Ajout du marqueur isolated pour isoler certains tests sensibles aux effets de bord."""
    config.addinivalue_line(
        "markers", "isolated: mark test as isolated to avoid side effects"
    )


@pytest.fixture(autouse=True)
def ensure_isolated(request, monkeypatch):
    """If a test is marked `isolated`, ensure environment isolation and remove
    any previously imported `docker` module to avoid side effects.

    This replaces manual pytest hooks and sys/os manipulation.
    """
    if "isolated" in request.keywords:
        # Ensure docker module is reimported cleanly
        sys.modules.pop("docker", None)
        monkeypatch.setenv("PYTEST_ISOLATED_TEST", "1")
    yield
