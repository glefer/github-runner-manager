import types
from unittest.mock import patch

import pytest

from src.services.config_schema import (
    FullConfig,
    RunnerConfig,
    RunnersDefaults,
    SlackConfig,
    WebhooksConfig,
)

# --- Shared fixtures to avoid Dummy* duplication in tests ---


@pytest.fixture
def empty_config_service():
    class DummyConfigService:
        def load_config(self):
            return type("C", (), {})()

    return DummyConfigService()


@pytest.fixture
def enabled_webhooks_config_service():
    class DummyWebhooks:
        enabled = True

        def model_dump(self):
            return {}

    class DummyConfigService:
        def load_config(self):
            return type("C", (), {"webhooks": DummyWebhooks()})()

    return DummyConfigService()


@pytest.fixture
def disabled_webhooks_config_service():
    class DummyWebhooks:
        enabled = False

        def model_dump(self):
            return {"enabled": False}

    class DummyConfigService:
        def load_config(self):
            return type("C", (), {"webhooks": DummyWebhooks()})()

    return DummyConfigService()


def test_init_webhooks_enabled_calls_build_and_register(
    monkeypatch, enabled_webhooks_config_service
):
    # Patch build_and_register in the module where it's used, before importing NotificationService
    called = {}

    def fake_build_and_register(ws):
        called["ok"] = ws

    monkeypatch.setattr(
        "src.services.notification_service.build_and_register", fake_build_and_register
    )
    from src.services.notification_service import NotificationService

    NotificationService(enabled_webhooks_config_service)
    assert "ok" in called


def test_init_no_webhooks(monkeypatch, empty_config_service):
    # Couvre la sortie anticipée si pas d'attribut webhooks (ligne 47)
    from src.services.notification_service import NotificationService

    ns = NotificationService(empty_config_service)
    assert ns.webhook_service is None


def test_init_webhooks_disabled_does_not_call_build_and_register(
    monkeypatch, disabled_webhooks_config_service
):
    # Couvre la branche "exit" de la condition if self.webhook_service.enabled (ligne 51)
    called = {"called": False}

    def fake_build_and_register(ws):
        called["called"] = True

    # Patch la fonction là où elle est utilisée
    monkeypatch.setattr(
        "src.services.notification_service.build_and_register", fake_build_and_register
    )

    # Patch WebhookService pour garantir enabled=False
    class FakeWebhookService:
        def __init__(self, cfg, console):
            self.enabled = False

    monkeypatch.setattr(
        "src.services.notification_service.WebhookService", FakeWebhookService
    )
    from src.services.notification_service import NotificationService

    ns = NotificationService(disabled_webhooks_config_service)
    assert ns.webhook_service is not None
    assert called["called"] is False


def test_emit_no_webhook_service(empty_config_service):
    from src.services.notification_service import NotificationService

    # Couvre la sortie anticipée de _emit si webhook_service absent (ligne 57)
    ns = NotificationService(empty_config_service)
    ns.webhook_service = None
    ns.dispatcher = types.SimpleNamespace(
        dispatch_many=lambda e: (_ for _ in ()).throw(Exception("Should not be called"))
    )
    ns._emit([1, 2])  # Ne doit rien faire


def test_emit_webhook_service_disabled(empty_config_service):
    from src.services.notification_service import NotificationService

    # Couvre la sortie anticipée de _emit si webhook_service désactivé (ligne 57)
    class DummyWebhook:
        enabled = False

    ns = NotificationService(empty_config_service)
    ns.webhook_service = DummyWebhook()
    ns.dispatcher = types.SimpleNamespace(
        dispatch_many=lambda e: (_ for _ in ()).throw(Exception("Should not be called"))
    )
    ns._emit([1, 2])  # Ne doit rien faire


def test_notify_build_completed_calls_emit(
    monkeypatch, enabled_webhooks_config_service
):
    from src.services.notification_service import NotificationService

    # Couvre notify_build_completed (ligne 117)
    ns = NotificationService(enabled_webhooks_config_service)
    called = {}
    ns.webhook_service = type("W", (), {"enabled": True})()
    ns.dispatcher = types.SimpleNamespace(
        dispatch_many=lambda events: called.setdefault("ok", True)
    )
    ns.notify_build_completed({"image_name": "img", "dockerfile": "df", "id": "id"})
    assert called["ok"]


def test_notify_build_failed_calls_emit(monkeypatch, enabled_webhooks_config_service):
    from src.services.notification_service import NotificationService

    # Couvre notify_build_failed (ligne 130)
    ns = NotificationService(enabled_webhooks_config_service)
    called = {}
    ns.webhook_service = type("W", (), {"enabled": True})()
    ns.dispatcher = types.SimpleNamespace(
        dispatch_many=lambda events: called.setdefault("ok", True)
    )
    ns.notify_build_failed({"id": "id", "error_message": "fail"})
    assert called["ok"]


def test_notify_update_applied_calls_emit(monkeypatch, enabled_webhooks_config_service):
    from src.services.notification_service import NotificationService

    # Couvre notify_update_applied (ligne 165)
    ns = NotificationService(enabled_webhooks_config_service)
    called = {}
    ns.webhook_service = type("W", (), {"enabled": True})()
    ns.dispatcher = types.SimpleNamespace(
        dispatch_many=lambda events: called.setdefault("ok", True)
    )
    ns.notify_update_applied(
        {
            "runner_type": "base",
            "from_version": "1",
            "to_version": "2",
            "image_name": "img",
        }
    )
    assert called["ok"]


def test_notify_from_docker_result_no_webhook(empty_config_service):
    from src.services.notification_service import NotificationService

    # Couvre la sortie anticipée de notify_from_docker_result (ligne 189)
    ns = NotificationService(empty_config_service)
    ns.webhook_service = None
    ns.notify_from_docker_result("op", {})  # Ne doit rien faire


def test_notify_from_docker_result_webhook_disabled(empty_config_service):
    from src.services.notification_service import NotificationService

    # Couvre la sortie anticipée de notify_from_docker_result (ligne 189)
    class DummyWebhook:
        enabled = False

    ns = NotificationService(empty_config_service)
    ns.webhook_service = DummyWebhook()
    ns.notify_from_docker_result("op", {})  # Ne doit rien faire


def test_webhook_test_calls_test_webhooks(monkeypatch):
    from src.presentation.cli import commands

    called = {}

    def fake_test_webhooks(config_service, event_type, provider, interactive, console):
        called.update(locals())

    monkeypatch.setattr(commands, "test_webhooks", fake_test_webhooks)
    # Patch console
    monkeypatch.setattr(commands, "console", types.SimpleNamespace())
    # Appel
    commands.webhook_test(event_type="evt", provider="prov")
    assert called["event_type"] == "evt"
    assert called["provider"] == "prov"
    assert called["interactive"] is True
    assert called["console"] is not None


def test_webhook_test_all_calls_debug_test_all_templates(monkeypatch):
    from src.presentation.cli import commands

    called = {}

    def fake_debug_test_all_templates(config_service, provider, console):
        called.update(locals())

    monkeypatch.setattr(
        commands, "debug_test_all_templates", fake_debug_test_all_templates
    )
    # Patch console
    monkeypatch.setattr(commands, "console", types.SimpleNamespace())
    # Appel
    commands.webhook_test_all(provider="prov")
    assert called["provider"] == "prov"
    assert called["console"] is not None


def test_build_runners_images_runs_without_notify_build_started(monkeypatch):
    """Vérifie que build_runners_images ne plante pas sans notify_build_started."""
    from src.presentation.cli import commands

    # Patch notification_service sans notify_build_started
    ns = types.SimpleNamespace(
        notify_from_docker_result=lambda *a, **k: None,
    )
    monkeypatch.setattr(commands, "notification_service", ns)

    # Patch config_service pour retourner deux runners
    class DummyRunner:
        def __init__(self, id, build_image):
            self.id = id
            self.build_image = build_image
            self.techno = "py"
            self.techno_version = "3.12"

    class DummyConfig:
        runners = [DummyRunner("a", True), DummyRunner("b", False)]
        runners_defaults = types.SimpleNamespace(base_image="base")

    monkeypatch.setattr(
        commands,
        "config_service",
        types.SimpleNamespace(load_config=lambda: DummyConfig()),
    )
    # Patch docker_service pour ne rien faire
    monkeypatch.setattr(
        commands,
        "docker_service",
        types.SimpleNamespace(
            build_runner_images=lambda quiet, use_progress: {
                "built": [],
                "skipped": [],
                "errors": [],
            }
        ),
    )
    # Patch console
    monkeypatch.setattr(
        commands, "console", types.SimpleNamespace(print=lambda *a, **k: None)
    )
    # Appel
    commands.build_runners_images()
    # Si aucune exception, le test passe


def _run_remove_runners(monkeypatch, deleted, skipped):
    """Helper pour patcher l'environnement et exécuter remove_runners."""
    from src.presentation.cli import commands

    notified = []
    printed = []

    # Patch notification_service
    monkeypatch.setattr(
        commands,
        "notification_service",
        types.SimpleNamespace(notify_runner_removed=lambda d: notified.append(d)),
    )
    # Patch config_service/dummy
    monkeypatch.setattr(
        commands, "config_service", types.SimpleNamespace(load_config=lambda: None)
    )
    # Patch docker_service pour retourner deleted et skipped
    monkeypatch.setattr(
        commands,
        "docker_service",
        types.SimpleNamespace(
            remove_runners=lambda: {
                "deleted": deleted,
                "skipped": skipped,
                "errors": [],
            }
        ),
    )
    # Patch console
    monkeypatch.setattr(
        commands,
        "console",
        types.SimpleNamespace(print=lambda *a, **k: printed.append(a[0] if a else "")),
    )
    # Appel
    commands.remove_runners()
    return notified, printed


@pytest.mark.parametrize(
    "deleted, skipped, expected_deleted_id, expected_deleted_name, expected_skipped_name",
    [
        (
            [{"id": "x", "name": "foo"}],
            [{"name": "bar"}],
            "x",
            "foo",
            "bar",
        ),
        (
            [{"id": "y", "name": "baz"}],
            [{"name": "qux"}],
            "y",
            "baz",
            "qux",
        ),
    ],
)
def test_remove_runners_deleted_and_not_available(
    monkeypatch,
    deleted,
    skipped,
    expected_deleted_id,
    expected_deleted_name,
    expected_skipped_name,
):
    """Vérifie la notification sur deleted et l'affichage suppression indisponible (paramétré)."""
    notified, printed = _run_remove_runners(monkeypatch, deleted, skipped)

    # Vérifie notification
    assert any(
        d.get("runner_id") == expected_deleted_id
        and d.get("runner_name") == expected_deleted_name
        for d in notified
    )
    # Vérifie affichage suppression indisponible
    assert any(
        f"{expected_skipped_name} n'est pas disponible à la suppression" in s
        for s in printed
    )


@pytest.fixture
def mock_webhook_service():
    with patch("src.services.notification_service.WebhookService") as mock:
        yield mock


@pytest.fixture
def notification_service(mock_config_service, mock_webhook_service):
    from src.services.notification_service import NotificationService

    # Construire une config avec webhooks activés pour que NotificationService
    # initialise WebhookService et appelle notify.
    config = FullConfig(
        runners_defaults=RunnersDefaults(
            base_image="ghcr.io/actions/runner:2.300.0",
            org_url="https://github.com/test-org",
        ),
        runners=[
            RunnerConfig(
                id="t",
                name_prefix="t-runner",
                labels=["test"],
                nb=1,
                build_image=None,
                techno=None,
                techno_version=None,
            )
        ],
        webhooks=WebhooksConfig(
            enabled=True,
            slack=SlackConfig(
                enabled=True,
                webhook_url="https://example.com/webhook",
                events=["runner_started"],
                templates={},
            ),
        ),
    )
    mock_config_service.load_config.return_value = config
    return NotificationService(mock_config_service)


def test_notify_runner_started_does_not_call_real_webhook(
    notification_service, mock_webhook_service
):
    runner_data = {"runner_id": "test", "runner_name": "Test Runner"}
    notification_service.notify_runner_started(runner_data)
    # Vérifie que le mock a bien été appelé, mais pas le vrai webhook
    assert mock_webhook_service.return_value.notify.called
    mock_webhook_service.return_value.notify.assert_called_with(
        "runner_started", runner_data
    )


def test_dispatcher_supports_filters(notification_service, mock_webhook_service):
    """Vérifie que le dispatcher n'invoque que les canaux dont supports(event) == True."""
    from unittest.mock import patch

    from src.notifications.channels.base import channels as real_channels

    class SupportingChannel:
        name = "supporting"

        def __init__(self):
            self.sent = False

        def supports(self, event):
            return True

        def send(self, event):
            self.sent = True

    class NonSupportingChannel:
        name = "non_supporting"

        def __init__(self):
            self.sent = False

        def supports(self, event):
            return False

        def send(self, event):  # pragma: no cover - ne devrait pas être appelé
            self.sent = True

    supporting = SupportingChannel()
    non_supporting = NonSupportingChannel()

    runner_data = {"runner_id": "filter-test", "runner_name": "Filter Runner"}

    # Compose une liste de canaux: custom + ceux déjà enregistrés (webhook) pour vérifier aussi l'appel d'origine
    patched_list = [supporting, non_supporting] + real_channels()

    with patch("src.notifications.dispatcher.channels", return_value=patched_list):
        notification_service.notify_runner_started(runner_data)

    assert supporting.sent is True
    assert non_supporting.sent is False
    # Le canal webhook mock doit aussi avoir été invoqué (via registration initiale)
    assert mock_webhook_service.return_value.notify.called
