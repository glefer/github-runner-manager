"""Dispatcher qui route les événements vers les canaux enregistrés."""

from __future__ import annotations

from typing import Iterable

from .channels.base import channels
from .events import NotificationEvent


class NotificationDispatcher:
    def dispatch(self, event: NotificationEvent) -> None:
        for ch in channels():
            if ch.supports(event):
                ch.send(event)

    def dispatch_many(self, events: Iterable[NotificationEvent]) -> None:
        for e in events:
            self.dispatch(e)


__all__ = ["NotificationDispatcher"]
