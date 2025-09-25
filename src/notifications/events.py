"""Définition des événements de notification typés.

Chaque événement est une dataclass immuable afin de faciliter tests, sérialisation
et extension. La méthode ``event_type`` fournit la clé utilisée par les canaux.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List



@dataclass(frozen=True)
class NotificationEvent:
    timestamp: datetime = field(default_factory=lambda: datetime.now(), kw_only=True)

    def event_type(self) -> str:  # snake_case pour cohérence existante
        name = self.__class__.__name__
        out = []
        for i, c in enumerate(name):
            if c.isupper() and i and (not name[i - 1].isupper()):
                out.append("_")
            out.append(c.lower())
        return "".join(out)

    def to_payload(self) -> Dict[str, Any]:  # utilisé par canaux génériques
        data = asdict(self)
        data["event_type"] = self.event_type()
        return data




@dataclass(frozen=True)
class RunnerStarted(NotificationEvent):
    runner_name: str
    labels: List[str] | str | None = None


@dataclass(frozen=True)
class RunnerStopped(NotificationEvent):
    runner_name: str
    uptime: str | None = None


@dataclass(frozen=True)
class RunnerRemoved(NotificationEvent):
    runner_id: str
    runner_name: str


@dataclass(frozen=True)
class RunnerError(NotificationEvent):
    runner_id: str
    runner_name: str
    error_message: str


@dataclass(frozen=True)
class RunnerSkipped(NotificationEvent):
    runner_name: str
    operation: str
    reason: str




@dataclass(frozen=True)
class BuildStarted(NotificationEvent):
    image_name: str
    dockerfile: str | None = None
    id: str | None = None


@dataclass(frozen=True)
class BuildCompleted(NotificationEvent):
    image_name: str
    duration: float
    image_size: str
    dockerfile: str | None = None
    id: str | None = None


@dataclass(frozen=True)
class BuildFailed(NotificationEvent):
    id: str | None
    image_name: str
    error_message: str


@dataclass(frozen=True)
class ImageUpdated(NotificationEvent):
    runner_type: str
    from_version: str
    to_version: str
    image_name: str | None = None


@dataclass(frozen=True)
class UpdateAvailable(NotificationEvent):
    runner_type: str
    image_name: str
    current_version: str
    available_version: str


@dataclass(frozen=True)
class UpdateApplied(NotificationEvent):
    runner_type: str
    from_version: str
    to_version: str
    image_name: str | None = None


@dataclass(frozen=True)
class UpdateError(NotificationEvent):
    runner_type: str
    error_message: str


EVENT_NAME_TO_CLASS = {
    "runner_started": RunnerStarted,
    "runner_stopped": RunnerStopped,
    "runner_removed": RunnerRemoved,
    "runner_error": RunnerError,
    "runner_skipped": RunnerSkipped,
    "build_started": BuildStarted,
    "build_completed": BuildCompleted,
    "build_failed": BuildFailed,
    "image_updated": ImageUpdated,
    "update_available": UpdateAvailable,
    "update_applied": UpdateApplied,
    "update_error": UpdateError,
}

__all__ = [
    "NotificationEvent",
    # Runner events
    "RunnerStarted",
    "RunnerStopped",
    "RunnerRemoved",
    "RunnerError",
    "RunnerSkipped",
    # Build / image events
    "BuildStarted",
    "BuildCompleted",
    "BuildFailed",
    "ImageUpdated",
    "UpdateAvailable",
    "UpdateApplied",
    "UpdateError",
    # Mapping
    "EVENT_NAME_TO_CLASS",
]
