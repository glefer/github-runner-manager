"""
Unit tests for src.presentation.cli.webhook_commands (prompt logic, error handling, and result display).
Optimized for clarity and maintainability.
"""

import types

import pytest

from src.presentation.cli import webhook_commands


@pytest.fixture
def dummy_config():
    class DummyConfig:
        def __init__(self, enabled=True, providers=None, events=None):
            self.webhooks = types.SimpleNamespace(
                enabled=enabled,
                dict=lambda: {},
                model_dump=lambda: {},
            )
            self.webhooks.dict = lambda: {}
            self.webhooks.model_dump = lambda: {}
            self.webhooks.enabled = enabled
            self.webhooks.slack = types.SimpleNamespace(
                enabled=True, events=events or [], templates={}
            )

    return DummyConfig


@pytest.fixture
def dummy_webhook_service():
    class DummyWebhookService:
        def __init__(self, providers=None):
            self.providers = providers or {}
            self._send_notification = lambda *a, **k: True

        def notify(self, event_type, data, provider=None):
            return {provider or "slack": True}

    return DummyWebhookService


def test_event_type_default_non_interactive(
    monkeypatch, dummy_config, dummy_webhook_service
):
    """Test event_type default when not interactive."""

    def load_config():
        return dummy_config()

    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: dummy_webhook_service(providers={"slack": {}}),
    )
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    result = webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type=None,
        interactive=False,
        console=console,
    )
    assert result["event_type"] == "runner_started"


def test_interactive_event_type_prompt(
    monkeypatch, dummy_config, dummy_webhook_service
):
    """Test Prompt.ask for event_type selection when interactive."""

    def load_config():
        return dummy_config()

    called = {}

    def fake_prompt_ask(msg, choices, default):
        called["asked"] = True
        assert "Choose an event type" in msg
        return "runner_started"

    monkeypatch.setattr(
        webhook_commands, "Prompt", types.SimpleNamespace(ask=fake_prompt_ask)
    )
    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: dummy_webhook_service(providers={"slack": {}}),
    )
    monkeypatch.setattr(
        webhook_commands, "typer", types.SimpleNamespace(confirm=lambda *a, **k: True)
    )
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type=None,
        interactive=True,
        console=console,
    )
    assert called["asked"]


def test_interactive_provider_prompt(monkeypatch, dummy_config, dummy_webhook_service):
    """Test Prompt.ask for provider selection when multiple providers are available."""

    def load_config():
        return dummy_config()

    called = {"asked": False}

    def fake_prompt_ask(msg, choices, default):
        called["asked"] = True
        assert "provider" in msg
        return "slack"

    providers = {"slack": {}, "teams": {}}
    monkeypatch.setattr(
        webhook_commands, "Prompt", types.SimpleNamespace(ask=fake_prompt_ask)
    )
    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: dummy_webhook_service(providers=providers),
    )
    monkeypatch.setattr(
        webhook_commands, "typer", types.SimpleNamespace(confirm=lambda *a, **k: True)
    )
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type="runner_started",
        provider=None,
        interactive=True,
        console=console,
    )
    assert called["asked"] is True


def test_interactive_confirm_cancel(monkeypatch, dummy_config, dummy_webhook_service):
    """Test cancel confirmation when typer.confirm returns False."""

    def load_config():
        return dummy_config()

    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: dummy_webhook_service(providers={"slack": {}}),
    )
    monkeypatch.setattr(
        webhook_commands, "typer", types.SimpleNamespace(confirm=lambda *a, **k: False)
    )
    monkeypatch.setattr(
        webhook_commands,
        "Prompt",
        types.SimpleNamespace(ask=lambda *a, **k: "runner_started"),
    )
    printed = {}

    def fake_print(msg, *a, **k):
        if "Sending cancelled" in str(msg):
            printed["cancel"] = True

    console = types.SimpleNamespace(print=fake_print)
    result = webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type=None,
        interactive=True,
        console=console,
    )
    assert result.get("cancelled") is True
    assert printed.get("cancel")


def test_affichage_resultats(monkeypatch, dummy_config, dummy_webhook_service):
    """Test result display for success and failure notifications."""

    def load_config():
        return dummy_config()

    class DummyWS:
        providers = {"slack": {}}

        def notify(self, event_type, data, provider=None):
            return {"slack": True, "teams": False}

    monkeypatch.setattr(webhook_commands, "WebhookService", lambda *a, **k: DummyWS())
    monkeypatch.setattr(
        webhook_commands, "typer", types.SimpleNamespace(confirm=lambda *a, **k: True)
    )
    monkeypatch.setattr(
        webhook_commands,
        "Prompt",
        types.SimpleNamespace(ask=lambda *a, **k: "runner_started"),
    )
    printed = {"success": 0, "fail": 0}

    def fake_print(msg, *a, **k):
        if "Notification sent successfully" in str(msg):
            printed["success"] += 1
        if "Sending failed" in str(msg):
            printed["fail"] += 1

    console = types.SimpleNamespace(print=fake_print)
    webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type=None,
        interactive=True,
        console=console,
    )
    assert printed["success"] == 1
    assert printed["fail"] == 1


def test_debug_test_all_templates_error_config(monkeypatch):
    # Couvre l'erreur "Aucune configuration webhook trouvée" (ligne 212-215)
    def load_config():
        return types.SimpleNamespace()

    console = types.SimpleNamespace(print=lambda *a, **k: None)
    result = webhook_commands.debug_test_all_templates(
        config_service=types.SimpleNamespace(load_config=load_config),
        provider=None,
        console=console,
    )
    assert "error" in result


def test_debug_test_all_templates_error_provider(monkeypatch):
    # Couvre l'erreur "Aucun provider activé" (ligne 222-225)
    def load_config():
        c = DummyConfig()
        return c

    class DummyWS:
        providers = {}

    monkeypatch.setattr(webhook_commands, "WebhookService", lambda *a, **k: DummyWS())
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    result = webhook_commands.debug_test_all_templates(
        config_service=types.SimpleNamespace(load_config=load_config),
        provider=None,
        console=console,
    )
    assert "error" in result


def test_debug_test_all_templates_affichage_echec(monkeypatch):
    # Couvre l'affichage de l'échec d'envoi (ligne 273)
    def load_config():
        c = DummyConfig()
        return c

    class DummyWS:
        providers = {"slack": {"events": ["runner_started"]}}

        def _send_notification(
            self, provider_name, event_type, mock_data, provider_config
        ):
            return False

    monkeypatch.setattr(webhook_commands, "WebhookService", lambda *a, **k: DummyWS())
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    res = webhook_commands.debug_test_all_templates(
        config_service=types.SimpleNamespace(load_config=load_config),
        provider="slack",
        console=console,
    )
    assert "slack" in res


class DummyConfig:
    def __init__(self, enabled=True, providers=None, events=None):
        self.webhooks = types.SimpleNamespace(
            enabled=enabled,
            dict=lambda: {},
            model_dump=lambda: {},
        )
        self.webhooks.dict = lambda: {}
        self.webhooks.model_dump = lambda: {}
        self.webhooks.enabled = enabled
        self.webhooks.slack = types.SimpleNamespace(
            enabled=True, events=events or [], templates={}
        )


class DummyWebhookService:
    def __init__(self, providers=None):
        self.providers = providers or {}
        self._send_notification = lambda *a, **k: True

    def notify(self, event_type, data, provider=None):
        return {provider or "slack": True}


@pytest.mark.parametrize("enabled", [False, True])
def test_test_webhooks_config_missing(monkeypatch, enabled):
    # config sans webhooks
    def load_config():
        return types.SimpleNamespace()

    console = types.SimpleNamespace(print=lambda *a, **k: None)
    result = webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type="runner_started",
        interactive=False,
        console=console,
    )
    assert "error" in result

    # webhooks désactivés
    def load_config2():
        c = DummyConfig(enabled=False)
        return c

    monkeypatch.setattr(
        webhook_commands, "typer", types.SimpleNamespace(confirm=lambda *a, **k: False)
    )
    result = webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config2),
        event_type="runner_started",
        interactive=True,
        console=console,
    )
    assert "error" in result


def test_test_webhooks_provider_not_activated(monkeypatch):
    # Aucun provider activé
    def load_config():
        c = DummyConfig()
        return c

    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: DummyWebhookService(providers={}),
    )
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    result = webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type="runner_started",
        interactive=False,
        console=console,
    )
    assert "error" in result


def test_test_webhooks_event_type_invalid(monkeypatch):
    # event_type non valide
    def load_config():
        c = DummyConfig()
        return c

    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: DummyWebhookService(providers={"slack": {}}),
    )
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    result = webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type="not_an_event",
        interactive=False,
        console=console,
    )
    assert "error" in result


def test_test_webhooks_success(monkeypatch):
    # Succès, tous les providers
    def load_config():
        c = DummyConfig()
        return c

    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: DummyWebhookService(providers={"slack": {}}),
    )
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    result = webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type="runner_started",
        interactive=False,
        console=console,
    )
    assert result["event_type"] == "runner_started"
    assert result["provider"] == "all"
    assert result["results"] == {"slack": True}


def test_test_webhooks_cancel(monkeypatch):
    # Annulation par confirmation
    def load_config():
        c = DummyConfig()
        return c

    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: DummyWebhookService(providers={"slack": {}}),
    )
    monkeypatch.setattr(
        webhook_commands, "typer", types.SimpleNamespace(confirm=lambda *a, **k: False)
    )
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    result = webhook_commands.test_webhooks(
        config_service=types.SimpleNamespace(load_config=load_config),
        event_type="runner_started",
        interactive=True,
        console=console,
    )
    assert result.get("cancelled") is True


def test_debug_test_all_templates(monkeypatch):
    # Cas provider non configuré, succès, et event non configuré
    def load_config():
        c = DummyConfig()
        return c

    # provider non configuré
    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: DummyWebhookService(
            providers={"slack": {"events": ["runner_started"]}}
        ),
    )
    console = types.SimpleNamespace(print=lambda *a, **k: None)
    # provider non existant
    webhook_commands.debug_test_all_templates(
        config_service=types.SimpleNamespace(load_config=load_config),
        provider="notfound",
        console=console,
    )
    # succès
    res2 = webhook_commands.debug_test_all_templates(
        config_service=types.SimpleNamespace(load_config=load_config),
        provider="slack",
        console=console,
    )
    assert "slack" in res2
    # event non configuré
    monkeypatch.setattr(
        webhook_commands,
        "WebhookService",
        lambda *a, **k: DummyWebhookService(providers={"slack": {"events": []}}),
    )
    res3 = webhook_commands.debug_test_all_templates(
        config_service=types.SimpleNamespace(load_config=load_config),
        provider="slack",
        console=console,
    )
    assert "slack" in res3
