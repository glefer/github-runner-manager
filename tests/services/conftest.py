"""
Configuration for tests in the services folder.

This module provides fixtures and hooks for tests in the services folder.
"""

import sys

import pytest


def pytest_configure(config):
    """Add the isolated marker to isolate certain tests from side effects."""
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
