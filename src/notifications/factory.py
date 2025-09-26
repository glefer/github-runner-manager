"""Utility factory to convert operation results into typed events."""

from __future__ import annotations

from typing import Any, Dict

from .events import (
    BuildCompleted,
    BuildFailed,
    ImageUpdated,
    RunnerError,
    RunnerRemoved,
    RunnerSkipped,
    RunnerStarted,
    RunnerStopped,
    UpdateAvailable,
    UpdateError,
)



def events_from_operation(operation: str, result: Dict[str, Any]):
    yield from _iter_events(operation, result)


def _iter_events(operation: str, result: Dict[str, Any]):
    if operation == "build":
        for built in result.get("built", []):
            yield BuildCompleted(
                image_name=built.get("image", ""),
                duration=built.get("duration", 0.0),
                dockerfile=built.get("dockerfile", ""),
                id=built.get("id", ""),
                image_size=built.get("image_size", "unknown"),
            )
        for error in result.get("errors", []):
            yield BuildFailed(
                image_name=error.get("image", ""),
                id=error.get("id", ""),
                error_message=error.get("reason", "Unknown error"),
            )

    elif operation == "start":
        for started in result.get("started", []):
            yield RunnerStarted(
                runner_name=started.get("name", ""),
                labels=started.get("labels", []),
            )
        for restarted in result.get("restarted", []):
            yield RunnerStarted(
                runner_name=restarted.get("name", ""),
                labels=restarted.get("labels", []),
            )
        for error in result.get("errors", []):
            yield RunnerError(
                runner_id=error.get("id", ""),
                runner_name=error.get("name", error.get("id", "")),
                error_message=error.get("reason", "Unknown error"),
            )

    elif operation == "stop":
        for stopped in result.get("stopped", []):
            yield RunnerStopped(
                runner_name=stopped.get("name", ""),
                uptime=stopped.get("uptime", "unknown"),
            )
        for error in result.get("errors", []):
            yield RunnerError(
                runner_id=error.get("id", ""),
                runner_name=error.get("name", ""),
                error_message=error.get("reason", "Unknown error"),
            )
        for skipped in result.get("skipped", []):
            yield RunnerSkipped(
                runner_name=skipped.get("name", ""),
                operation="stop",
                reason="Runner not running",
            )

    elif operation == "remove":
        for deleted in result.get("deleted", []):
            yield RunnerRemoved(
                runner_id=deleted.get("id", ""),
                runner_name=deleted.get("name", ""),
            )
        for error in result.get("errors", []):
            yield RunnerError(
                runner_id=error.get("id", ""),
                runner_name=error.get("name", ""),
                error_message=error.get("reason", "Unknown error"),
            )
        for skipped in result.get("skipped", []):
            yield RunnerSkipped(
                runner_name=skipped.get("name", ""),
                operation="remove",
                reason=skipped.get("reason", result.get("reason", "Unknown reason")),
            )

    elif operation == "update":
        if result.get("update_available"):
            yield UpdateAvailable(
                runner_type="base",
                image_name=result.get("image_name", ""),
                current_version=result.get("current_version", ""),
                available_version=result.get("latest_version", ""),
            )
        if result.get("updated"):
            yield ImageUpdated(
                runner_type="base",
                from_version=result.get("old_version", ""),
                to_version=result.get("new_version", ""),
                image_name=result.get("new_image", ""),
            )
        if result.get("error"):
            yield UpdateError(
                runner_type="base",
                error_message=result.get("error", "Unknown error"),
            )


__all__ = ["events_from_operation"]
