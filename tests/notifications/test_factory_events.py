"""
Tests for all event branches for start/stop/remove/update operations in events_from_operation.
Optimized for clarity and maintainability.
"""

import pytest

from src.notifications import events as ev


def collect(op, data):
    """Helper to collect events from operation for test cases."""
    from src.notifications.factory import events_from_operation

    return list(events_from_operation(op, data))


@pytest.mark.parametrize(
    "op,data,checks",
    [
        (
            "start",
            {
                "started": [
                    {
                        "id": "1",
                        "name": "r1",
                        "labels": ["x"],
                        "techno": "py",
                        "techno_version": "3.12",
                    }
                ],
                "restarted": [
                    {
                        "id": "2",
                        "name": "r2",
                        "labels": [],
                        "techno": "node",
                        "techno_version": "20",
                    }
                ],
                "errors": [{"id": "3", "name": "r3", "reason": "boom"}],
            },
            [
                lambda events: any(isinstance(e, ev.RunnerStarted) for e in events),
                lambda events: any(isinstance(e, ev.RunnerStarted) for e in events),
                lambda events: any(
                    isinstance(e, ev.RunnerError) and e.error_message == "boom"
                    for e in events
                ),
            ],
        ),
        (
            "stop",
            {
                "stopped": [{"id": "1", "name": "r1", "uptime": "10s"}],
                "errors": [{"id": "2", "name": "r2", "reason": "oops"}],
                "skipped": [{"name": "r3"}],
            },
            [
                lambda events: any(
                    isinstance(e, ev.RunnerStopped) and e.uptime == "10s"
                    for e in events
                ),
                lambda events: any(
                    isinstance(e, ev.RunnerError) and e.error_message == "oops"
                    for e in events
                ),
                lambda events: any(
                    isinstance(e, ev.RunnerSkipped)
                    and e.runner_name == "r3"
                    and e.operation == "stop"
                    for e in events
                ),
            ],
        ),
        (
            "remove",
            {
                "deleted": [{"id": "1", "name": "r1"}],
                "errors": [{"id": "2", "name": "r2", "reason": "fail"}],
                "skipped": [{"name": "r3", "reason": "not found"}],
            },
            [
                lambda events: any(isinstance(e, ev.RunnerRemoved) for e in events),
                lambda events: any(
                    isinstance(e, ev.RunnerError) and e.error_message == "fail"
                    for e in events
                ),
                lambda events: any(
                    isinstance(e, ev.RunnerSkipped)
                    and e.runner_name == "r3"
                    and e.reason == "not found"
                    for e in events
                ),
            ],
        ),
        (
            "update",
            {
                "image_name": "img:1.0",
                "update_available": True,
                "current_version": "1.0",
                "latest_version": "1.1",
                "updated": True,
                "old_version": "1.0",
                "new_version": "1.1",
                "new_image": "img:1.1",
                "error": "err",
            },
            [
                lambda events: any(
                    isinstance(e, ev.UpdateAvailable) and e.available_version == "1.1"
                    for e in events
                ),
                lambda events: any(
                    isinstance(e, ev.ImageUpdated) and e.to_version == "1.1"
                    for e in events
                ),
                lambda events: any(
                    isinstance(e, ev.UpdateError) and e.error_message == "err"
                    for e in events
                ),
            ],
        ),
    ],
)
def test_events_all_branches(op, data, checks):
    """Parametrized test for all event branches."""
    events = collect(op, data)
    for check in checks:
        assert check(events)


@pytest.mark.parametrize(
    "data,expected_type,expected_attr",
    [
        (
            {
                "update_available": True,
                "current_version": "1.0",
                "latest_version": "1.1",
            },
            ev.UpdateAvailable,
            None,
        ),
        (
            {
                "updated": True,
                "old_version": "1.0",
                "new_version": "1.1",
                "new_image": "img:1.1",
            },
            ev.ImageUpdated,
            None,
        ),
        ({"error": "fatal"}, ev.UpdateError, "fatal"),
    ],
)
def test_update_events_single(data, expected_type, expected_attr):
    """Test update events for only available, updated, or error cases."""
    events = collect("update", data)
    assert len(events) == 1
    assert isinstance(events[0], expected_type)
    if expected_attr:
        assert getattr(events[0], "error_message", None) == expected_attr


def test_update_events_none():
    """Test update event returns empty for empty data."""
    assert collect("update", {}) == []


def test_unknown_operation_returns_empty():
    """Test unknown operation returns empty list."""
    assert collect("unknown_operation", {"some": "data"}) == []
