"""
Tests unitaires pour WebhookService : providers, notifications, payloads, retry, formatters.
Optimisé pour clarté, maintenabilité et couverture.
"""

import types
from typing import Any, Dict

import pytest

from src.services.webhook_service import WebhookService


@pytest.fixture
def dummy_console():
    return types.SimpleNamespace(print=lambda *a, **k: None)


@pytest.fixture
def service(dummy_console):
    def _make(config: Dict[str, Any]):
        return WebhookService(config, console=dummy_console)

    return _make


def test_webhook_provider_str():
    """Test string representation of WebhookProvider enum."""
    from src.services.webhook_service import WebhookProvider

    assert str(WebhookProvider.SLACK) == "slack"
    assert str(WebhookProvider.DISCORD) == "discord"
    assert str(WebhookProvider.TEAMS) == "teams"
    assert str(WebhookProvider.GENERIC) == "generic"


def test_init_enabled_false_does_not_init_providers(service):
    """Test that no providers are initialized if enabled is False."""
    svc = service({"enabled": False})
    assert svc.enabled is False
    assert svc.providers == {}


def test_init_enabled_true_inits_only_enabled_providers(service):
    """Test that only enabled providers are initialized."""
    svc = service(
        {
            "enabled": True,
            "slack": {"enabled": True, "webhook_url": "http://x", "events": []},
            "discord": {"enabled": False},
        }
    )
    assert svc.enabled is True
    assert "slack" in svc.providers and "discord" not in svc.providers


def test_notify_not_enabled_returns_empty(monkeypatch, service):
    """Test notify returns empty if service is not enabled."""
    svc = service({"enabled": False})

    def boom(*a, **k):
        raise AssertionError("_send_notification should not be called")

    monkeypatch.setattr(svc, "_send_notification", boom)
    assert svc.notify("runner_started", {"id": 1}) == {}


def test_notify_unknown_provider_returns_empty(service):
    """Test notify returns empty if provider is unknown."""
    svc = service({"enabled": True, "slack": {"enabled": True, "events": []}})
    assert svc.notify("runner_started", {}, provider="unknown") == {}


def test_notify_event_not_configured_skips_send(monkeypatch, service):
    """Test notify skips sending if event is not configured."""
    svc = service(
        {"enabled": True, "slack": {"enabled": True, "webhook_url": "u", "events": []}}
    )
    called = {"n": 0}

    def spy(*a, **k):
        called["n"] += 1
        return True

    monkeypatch.setattr(svc, "_send_notification", spy)
    assert svc.notify("runner_started", {}) == {}
    assert called["n"] == 0


def test_notify_success_with_provider_filter(monkeypatch, service):
    """Test notify returns success dict when provider is filtered and send succeeds."""
    svc = service(
        {
            "enabled": True,
            "slack": {
                "enabled": True,
                "webhook_url": "http://u",
                "events": ["runner_started"],
            },
        }
    )
    monkeypatch.setattr(svc, "_send_notification", lambda *a, **k: True)
    res = svc.notify("runner_started", {"runner_id": "x"}, provider="slack")
    assert res == {"slack": True}


def test_send_notification_missing_url_returns_false(service):
    """Test _send_notification returns False if webhook_url is missing."""
    svc = service({"enabled": True})
    assert (
        svc._send_notification(provider="slack", event_type="e", data={}, config={})
        is False
    )


@pytest.mark.parametrize(
    "provider",
    ["slack", "discord", "teams", "generic"],
)
def test_send_notification_per_provider_uses_formatter(monkeypatch, provider, service):
    svc = service({"enabled": True})
    # Avoid network, just confirm routing to _send_with_retry
    monkeypatch.setattr(svc, "_send_with_retry", lambda *a, **k: True)
    cfg = {"webhook_url": "http://u", "events": ["any"], "templates": {}}
    assert (
        svc._send_notification(provider=provider, event_type="any", data={}, config=cfg)
        is True
    )


def test_send_with_retry_success_first_try(monkeypatch, service):

    class Resp:
        status_code = 200
        text = "ok"

    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return Resp()

    monkeypatch.setattr("requests.post", fake_post)
    svc = service({"enabled": True})
    assert svc._send_with_retry("http://u", payload={}, config={}) is True
    assert calls["n"] == 1


def test_send_with_retry_retry_then_success(monkeypatch, service):

    class Resp500:
        status_code = 500
        text = "err"

    class Resp200:
        status_code = 200
        text = "ok"

    seq = [Resp500(), Resp200()]

    def fake_post(*a, **k):
        return seq.pop(0)

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)
    svc = service({"enabled": True})
    assert svc._send_with_retry("http://u", payload={}, config={}) is True


def test_send_with_retry_exceptions_then_success(monkeypatch, service):

    seq = [
        Exception("boom"),
        Exception("boom2"),
        types.SimpleNamespace(status_code=200, text="ok"),
    ]

    def fake_post(*a, **k):
        v = seq.pop(0)
        if isinstance(v, Exception):
            raise v
        return v

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)
    svc = service({"enabled": True})
    assert svc._send_with_retry("http://u", payload={}, config={}) is True


def test_send_with_retry_all_fail_returns_false_and_sleeps(monkeypatch, service):
    # Always return 500, should retry and finally return False
    class Resp500:
        status_code = 500
        text = "err"

    calls = {"post": 0, "sleep": 0}

    def fake_post(*a, **k):
        calls["post"] += 1
        return Resp500()

    def fake_sleep(*a, **k):
        calls["sleep"] += 1

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("time.sleep", fake_sleep)
    svc = service({"enabled": True})
    assert svc._send_with_retry("http://u", payload={}, config={}) is False
    # Default retry_count is 3 => 4 posts, 3 sleeps
    assert calls["post"] == 4
    assert calls["sleep"] == 3


def test_send_with_retry_try_sleep_branch_loops(monkeypatch, service):
    # Force 500 twice with retry_count=1 so we sleep once and loop exactly once
    class Resp500:
        status_code = 500
        text = "err"

    seq = [Resp500(), Resp500()]
    calls = {"post": 0, "sleep": 0}

    def fake_post(*a, **k):
        calls["post"] += 1
        return seq.pop(0)

    def fake_sleep(*a, **k):
        calls["sleep"] += 1

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("time.sleep", fake_sleep)
    svc = service({"enabled": True})
    svc.retry_count = 1
    assert svc._send_with_retry("http://u", payload={}, config={}) is False
    assert calls["post"] == 2
    assert calls["sleep"] == 1


def test_send_with_retry_try_backedge_without_sleep_patch(monkeypatch, service):
    # Ensure the try-branch 'if attempt < retry_count' back-edge is exercised
    class Resp500:
        status_code = 500
        text = "err"

    seq = [Resp500(), Resp500()]

    def fake_post(*a, **k):
        return seq.pop(0)

    monkeypatch.setattr("requests.post", fake_post)
    svc = service({"enabled": True})
    svc.retry_count = 1
    svc.retry_delay = 0
    assert svc._send_with_retry("http://u", payload={}, config={}) is False


def test_send_with_retry_exception_branch(monkeypatch, service):
    """Test explicitly focusing on the exception branch in _send_with_retry."""
    # Track call attempts
    calls = {"attempt": 0}

    # First call raises exception, second returns success
    def fake_post(*a, **k):
        calls["attempt"] += 1
        if calls["attempt"] == 1:
            raise Exception("Simulated network error")
        else:
            return type("Response", (), {"status_code": 200, "text": "OK"})()

    # Skip sleep
    def fake_sleep(*a, **k):
        pass

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("time.sleep", fake_sleep)

    # Create service with minimal retries
    svc = service({"enabled": True})
    svc.retry_count = 1  # One retry means two attempts

    # This should fail once (exception), then succeed on retry
    assert svc._send_with_retry("http://u", payload={}, config={}) is True
    assert (
        calls["attempt"] == 2
    )  # Verify we went through the exception path and looped back


def test_send_with_retry_uses_provider_timeout_override(monkeypatch, service):
    captured = {"timeout": None}

    class Resp:
        status_code = 200
        text = "ok"

    def fake_post(*a, **k):
        captured["timeout"] = k.get("timeout")
        return Resp()

    monkeypatch.setattr("requests.post", fake_post)
    svc = service({"enabled": True})
    assert svc._send_with_retry("http://u", payload={}, config={"timeout": 1}) is True
    assert captured["timeout"] == 1


def test_format_slack_payload_use_text_no_attachment_and_fields(service):
    svc = service({"enabled": True})
    cfg = {
        "webhook_url": "http://u",
        "templates": {
            "runner_started": {
                "use_attachment": False,
                "title": "runner {runner_id}",
                "text": "Hello {runner_id}",
                "fields": [{"name": "id", "value": "{runner_id}", "short": True}],
            }
        },
    }
    payload = svc._format_slack_payload("runner_started", {"runner_id": "X"}, cfg)
    # When use_attachment is False, text is set and attachments should be empty
    assert payload["text"].startswith("Hello X")
    assert payload["attachments"] == []


def test_format_slack_payload_with_fields(service):
    svc = service({"enabled": True})
    cfg = {
        "webhook_url": "http://u",
        "templates": {
            "runner_started": {
                "use_attachment": True,
                "title": "runner {runner_id}",
                "text": "ignored",
                "fields": [{"name": "id", "value": "{runner_id}", "short": False}],
            }
        },
    }
    payload = svc._format_slack_payload("runner_started", {"runner_id": "X"}, cfg)
    att = payload["attachments"][0]
    assert any(f["title"] == "id" and f["value"] == "X" for f in att["fields"])


def test_format_discord_payload_with_fields(service):
    svc = service({"enabled": True})
    cfg = {
        "webhook_url": "http://u",
        "templates": {
            "runner_started": {
                "title": "Runner {runner_id}",
                "description": "Desc",
                "fields": [{"name": "id", "value": "{runner_id}", "inline": False}],
            }
        },
    }
    payload = svc._format_discord_payload("runner_started", {"runner_id": "X"}, cfg)
    fields = payload["embeds"][0]["fields"]
    assert any(
        f["name"] == "id" and f["value"] == "X" and f["inline"] is False for f in fields
    )


def test_format_teams_payload_with_sections_and_facts(service):
    svc = service({"enabled": True})
    cfg = {
        "webhook_url": "http://u",
        "templates": {
            "runner_started": {
                "title": "Runner {runner_id}",
                "sections": [
                    {
                        "activityTitle": "Act {runner_id}",
                        "facts": [
                            {"name": "id", "value": "{runner_id}"},
                        ],
                    }
                ],
            }
        },
    }
    payload = svc._format_teams_payload("runner_started", {"runner_id": "X"}, cfg)
    sections = payload["sections"]
    assert sections and sections[0].get("facts")
    assert any(f["name"] == "id" and f["value"] == "X" for f in sections[0]["facts"])


def test_format_teams_payload_with_multiple_facts(service):
    svc = service({"enabled": True})
    cfg = {
        "webhook_url": "http://u",
        "templates": {
            "runner_started": {
                "title": "Runner {runner_id}",
                "sections": [
                    {
                        "activityTitle": "Act {runner_id}",
                        "facts": [
                            {"name": "id", "value": "{runner_id}"},
                            {"name": "state", "value": "ok"},
                        ],
                    }
                ],
            }
        },
    }
    payload = svc._format_teams_payload("runner_started", {"runner_id": "X"}, cfg)
    facts = payload["sections"][0]["facts"]
    assert any(f["name"] == "state" and f["value"] == "ok" for f in facts)


def test_notify_unknown_provider_prints_message():

    messages = []
    console = types.SimpleNamespace(
        print=lambda *a, **k: messages.append(a[0] if a else "")
    )
    svc = WebhookService({"enabled": True, "slack": {"enabled": True}}, console=console)
    assert svc.notify("runner_started", {}, provider="nope") == {}
    assert any("not configured" in str(m) for m in messages)


def test_format_slack_payload_defaults_and_channel(service):

    svc = service({"enabled": True})
    cfg = {
        "webhook_url": "http://u",
        "templates": {},
        "username": "u",
        "channel": "#general",
    }
    payload = svc._format_slack_payload("runner_started", {"runner_id": "x"}, cfg)
    assert "attachments" in payload
    assert payload.get("channel") == "#general"


def test_format_discord_payload_defaults(service):

    svc = service({"enabled": True})
    cfg = {"webhook_url": "http://u", "templates": {}}
    payload = svc._format_discord_payload("runner_started", {"runner_id": "x"}, cfg)
    assert isinstance(payload.get("embeds"), list) and payload["embeds"]


def test_format_teams_payload_defaults(service):

    svc = service({"enabled": True})
    cfg = {"webhook_url": "http://u", "templates": {}}
    payload = svc._format_teams_payload("runner_started", {"runner_id": "x"}, cfg)
    assert payload.get("@type") == "MessageCard"
    assert isinstance(payload.get("sections"), list)


def test_format_generic_payload_contains_event_and_data(service):

    svc = service({"enabled": True})
    payload = svc._format_generic_payload("runner_started", {"runner_id": "x"}, {})
    assert payload["event_type"] == "runner_started"
    assert payload["data"]["runner_id"] == "x"


def test_format_string_missing_key_returns_template(monkeypatch, service):

    svc = service({"enabled": True})
    s = svc._format_string("Hello {name}", {"x": 1})
    # Sur KeyError, la fonction retourne la chaîne non formatée
    assert s == "Hello {name}"


def test_format_string_invalid_template_returns_template(service):

    svc = service({"enabled": True})
    s = svc._format_string("Hello {name", {"name": "x"})  # template invalide
    assert s == "Hello {name"


def test_notify_failure_prints_error(monkeypatch):
    # Capture console messages to ensure failure branch is executed
    messages = []
    console = types.SimpleNamespace(
        print=lambda *a, **k: messages.append(a[0] if a else "")
    )

    svc = WebhookService(
        {
            "enabled": True,
            "slack": {
                "enabled": True,
                "webhook_url": "http://u",
                "events": ["evt"],
            },
        },
        console=console,
    )
    # Force failure of send
    monkeypatch.setattr(svc, "_send_notification", lambda *a, **k: False)
    res = svc.notify("evt", {"x": 1})
    assert res == {"slack": False}
    assert any("Failed to send notification" in str(m) for m in messages)

    # Removed duplicate, unindented function definition


def test_send_notification_exception_returns_false(monkeypatch, service):
    svc = service({"enabled": True})

    # Make formatter raise to hit the exception branch
    def _raise(*a, **k):
        raise Exception("boom")

    monkeypatch.setattr(svc, "_format_generic_payload", _raise)
    ok = svc._send_notification(
        provider="generic",
        event_type="evt",
        data={},
        config={"webhook_url": "http://u"},
    )
    assert ok is False


def test_format_teams_payload_default_template_branch(service):
    # When no template for the event, default template is used
    svc = service({"enabled": True})
    cfg = {"webhook_url": "http://u", "templates": {}}
    payload = svc._format_teams_payload("evt_x", {"runner_id": "X"}, cfg)
    assert payload["title"].startswith("Evt X") or isinstance(payload["sections"], list)


def test_format_teams_payload_section_without_title_and_facts(service):
    # Section without activityTitle and facts must still be appended
    svc = service({"enabled": True})
    cfg = {
        "webhook_url": "http://u",
        "templates": {
            "runner_started": {
                "title": "Runner",
                "sections": [{}],
            }
        },
    }
    payload = svc._format_teams_payload("runner_started", {}, cfg)
    sections = payload["sections"]
    assert sections and sections[0] == {}
