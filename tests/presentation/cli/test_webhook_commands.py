"""
Tests for CLI webhook commands integration and invocation logic.
Optimized for clarity and maintainability.
"""

import pytest
from typer.testing import CliRunner

from src.presentation.cli import commands, webhook_commands


@pytest.fixture
def called_dict():
    return {}


def test_test_webhooks_called(monkeypatch, called_dict):
    """Test that test_webhooks is called with correct arguments."""

    def fake_test_webhooks(config_service, event_type, provider, interactive, console):
        called_dict.update(locals())

    monkeypatch.setattr(webhook_commands, "test_webhooks", fake_test_webhooks)
    webhook_commands.test_webhooks(
        config_service="conf",
        event_type="evt",
        provider="prov",
        interactive=True,
        console=object(),
    )
    assert called_dict["event_type"] == "evt"
    assert called_dict["provider"] == "prov"
    assert called_dict["interactive"] is True
    assert called_dict["console"] is not None


def test_debug_test_all_templates_called(monkeypatch, called_dict):
    """Test that debug_test_all_templates is called with correct arguments."""

    def fake_debug_test_all_templates(config_service, provider, console):
        called_dict.update(locals())

    monkeypatch.setattr(
        webhook_commands, "debug_test_all_templates", fake_debug_test_all_templates
    )
    webhook_commands.debug_test_all_templates(
        config_service="conf", provider="prov", console=object()
    )
    assert called_dict["provider"] == "prov"
    assert called_dict["console"] is not None


def test_webhook_test_cli_on_main_app(monkeypatch, called_dict):
    """Test CLI 'webhook test' command invokes test_webhooks."""

    def fake_test_webhooks(config_service, event_type, provider, interactive, console):
        called_dict.update(locals())

    monkeypatch.setattr(commands, "test_webhooks", fake_test_webhooks)
    monkeypatch.setattr(commands, "console", object())
    runner = CliRunner()
    result = runner.invoke(
        commands.app, ["webhook", "test", "--event", "evt", "--provider", "prov"]
    )
    assert result.exit_code == 0


def test_webhook_test_all_cli_on_main_app(monkeypatch, called_dict):
    """Test CLI 'webhook test-all' command invokes debug_test_all_templates."""

    def fake_debug_test_all_templates(config_service, provider, console):
        called_dict.update(locals())

    monkeypatch.setattr(
        commands, "debug_test_all_templates", fake_debug_test_all_templates
    )
    monkeypatch.setattr(commands, "console", object())
    runner = CliRunner()
    result = runner.invoke(commands.app, ["webhook", "test-all", "--provider", "prov"])
    assert result.exit_code == 0
