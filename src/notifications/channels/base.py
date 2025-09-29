"""Notification channels (interface + registry)."""

from __future__ import annotations

from typing import List, Protocol

from ..events import NotificationEvent


class NotificationChannel(Protocol):
    name: str

    def supports(
        self, event: NotificationEvent
    ) -> bool:  # pragma: no cover (interface)
        ...

    def send(self, event: NotificationEvent) -> None:  # pragma: no cover (interface)
        ...


_registry: List[NotificationChannel] = []


def register(channel: NotificationChannel) -> None:
    _registry.append(channel)


def channels() -> List[NotificationChannel]:
    return list(_registry)


__all__ = ["NotificationChannel", "register", "channels"]
