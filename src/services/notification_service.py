"""Service de notification refactorisé avec événements et dispatcher.

Compatibilité maintenue: les anciennes méthodes ``notify_*`` existent toujours
et délèguent à l'API événementielle interne.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from rich.console import Console

from src.notifications.channels.webhook import build_and_register
from src.notifications.dispatcher import NotificationDispatcher
from src.notifications.events import UpdateApplied  # peut être utilisé si besoin futur
from src.notifications.events import (
    BuildCompleted,
    BuildFailed,
    ImageUpdated,
    RunnerError,
    RunnerRemoved,
    RunnerStarted,
    RunnerStopped,
    UpdateAvailable,
    UpdateError,
)
from src.notifications.factory import events_from_operation
from src.services.config_service import ConfigService
from src.services.webhook_service import WebhookService


class NotificationService:
    """Façade publique stable pour l'envoi de notifications.

    Internellement repose sur un dispatcher + événements typés.
    """

    def __init__(
        self, config_service: ConfigService, console: Optional[Console] = None
    ):
        self.config_service = config_service
        self.console = console or Console()
        self.webhook_service: WebhookService | None = None
        self.dispatcher = NotificationDispatcher()

        config = self.config_service.load_config()
        if hasattr(config, "webhooks") and config.webhooks:
            self.webhook_service = WebhookService(
                config.webhooks.model_dump(), self.console
            )
            if self.webhook_service.enabled:
                build_and_register(self.webhook_service)

    # --- Nouvelles primitives internes ----------------------------------
    def _emit(self, events: Iterable):  # events: Iterable[NotificationEvent]
        if not self.webhook_service or not self.webhook_service.enabled:
            return
        self.dispatcher.dispatch_many(events)

    # --- Méthodes compatibles (gardées pour code existant/tests) ---------
    def notify_runner_started(self, runner_data: Dict[str, Any]) -> None:
        self._emit(
            [
                RunnerStarted(
                    runner_id=runner_data.get("runner_id", runner_data.get("id", "")),
                    runner_name=runner_data.get(
                        "runner_name", runner_data.get("name", "")
                    ),
                    labels=runner_data.get("labels"),
                    techno=runner_data.get("techno"),
                    techno_version=runner_data.get("techno_version"),
                    restarted=runner_data.get("restarted", False),
                )
            ]
        )

    def notify_runner_stopped(self, runner_data: Dict[str, Any]) -> None:
        self._emit(
            [
                RunnerStopped(
                    runner_id=runner_data.get("runner_id", runner_data.get("id", "")),
                    runner_name=runner_data.get(
                        "runner_name", runner_data.get("name", "")
                    ),
                    uptime=runner_data.get("uptime"),
                )
            ]
        )

    def notify_runner_removed(self, runner_data: Dict[str, Any]) -> None:
        self._emit(
            [
                RunnerRemoved(
                    runner_id=runner_data.get("runner_id", runner_data.get("id", "")),
                    runner_name=runner_data.get(
                        "runner_name", runner_data.get("name", "")
                    ),
                )
            ]
        )

    def notify_runner_error(self, runner_data: Dict[str, Any]) -> None:
        self._emit(
            [
                RunnerError(
                    runner_id=runner_data.get("runner_id", runner_data.get("id", "")),
                    runner_name=runner_data.get(
                        "runner_name", runner_data.get("name", "")
                    ),
                    error_message=runner_data.get("error_message", "Unknown error"),
                )
            ]
        )

    def notify_build_completed(self, build_data: Dict[str, Any]) -> None:
        self._emit(
            [
                BuildCompleted(
                    image_name=build_data.get(
                        "image_name", build_data.get("image", "")
                    ),
                    dockerfile=build_data.get("dockerfile"),
                    id=build_data.get("id"),
                )
            ]
        )

    def notify_build_failed(self, build_data: Dict[str, Any]) -> None:
        self._emit(
            [
                BuildFailed(
                    id=build_data.get("id"),
                    error_message=build_data.get("error_message", "Unknown error"),
                )
            ]
        )

    def notify_image_updated(self, update_data: Dict[str, Any]) -> None:
        self._emit(
            [
                ImageUpdated(
                    runner_type=update_data.get("runner_type", "base"),
                    from_version=update_data.get("from_version", ""),
                    to_version=update_data.get("to_version", ""),
                    image_name=update_data.get("image_name"),
                )
            ]
        )

    def notify_update_available(self, update_data: Dict[str, Any]) -> None:
        self._emit(
            [
                UpdateAvailable(
                    runner_type=update_data.get("runner_type", "base"),
                    current_version=update_data.get("current_version", ""),
                    available_version=update_data.get(
                        "available_version", update_data.get("latest_version", "")
                    ),
                )
            ]
        )

    def notify_update_applied(self, update_data: Dict[str, Any]) -> None:
        self._emit(
            [
                UpdateApplied(
                    runner_type=update_data.get("runner_type", "base"),
                    from_version=update_data.get("from_version", ""),
                    to_version=update_data.get("to_version", ""),
                    image_name=update_data.get("image_name"),
                )
            ]
        )

    def notify_update_error(self, update_data: Dict[str, Any]) -> None:
        self._emit(
            [
                UpdateError(
                    runner_type=update_data.get("runner_type", "base"),
                    error_message=update_data.get("error_message", "Unknown error"),
                )
            ]
        )

    # --- Nouvelle API pour résultats docker ------------------------------
    def notify_from_docker_result(self, operation: str, result: Dict[str, Any]) -> None:
        if not self.webhook_service or not self.webhook_service.enabled:
            return
        self._emit(events_from_operation(operation, result))


__all__ = ["NotificationService"]
