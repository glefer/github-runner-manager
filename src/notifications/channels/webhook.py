"""Notification channel via existing Webhook service."""

from __future__ import annotations

from src.services.webhook_service import WebhookService

from ..events import NotificationEvent
from .base import NotificationChannel, register


class WebhookChannel:
    name = "webhook"

    def __init__(self, webhook_service: WebhookService):
        self._svc = webhook_service

    # Tous les événements sont supportés, filtrage déjà assuré côté WebhookService via config
    def supports(self, event: NotificationEvent) -> bool:  # pragma: no cover - trivial
        return True

    def send(self, event: NotificationEvent) -> None:
        payload = event.to_payload()
        event_type = payload.pop("event_type")
        payload.pop("timestamp", None)
        compact = {k: v for k, v in payload.items() if v is not None}
        if compact.get("restarted") is False:
            compact.pop("restarted")
        self._svc.notify(event_type, compact)


def build_and_register(webhook_service: WebhookService) -> NotificationChannel:
    channel = WebhookChannel(webhook_service)
    register(channel)
    return channel


__all__ = ["WebhookChannel", "build_and_register"]
