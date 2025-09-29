"""Consolidated tests for list-runners command covering all output branches."""

from unittest.mock import patch

import pytest

from src.presentation.cli.commands import app


@pytest.mark.parametrize(
    "payload,expects",
    [
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 1,
                        "running": 1,
                        "runners": [
                            {
                                "id": 1,
                                "name": "g1-1",
                                "status": "running",
                                "labels": ["l1"],
                            }
                        ],
                        "extra_runners": [],
                    }
                ],
                "total": {"count": 1, "running": 1},
            },
            ["✅ running", "g1-1", "Runners configurés"],
        ),
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 1,
                        "running": 0,
                        "runners": [
                            {
                                "id": 1,
                                "name": "g1-1",
                                "status": "stopped",
                                "labels": ["l1"],
                            }
                        ],
                        "extra_runners": [],
                    }
                ],
                "total": {"count": 1, "running": 0},
            },
            ["stopped"],
        ),
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 1,
                        "running": 0,
                        "runners": [
                            {
                                "id": 1,
                                "name": "g1-1",
                                "status": "absent",
                                "labels": ["l1"],
                            }
                        ],
                        "extra_runners": [],
                    }
                ],
                "total": {"count": 1, "running": 0},
            },
            ["absent", "❌"],
        ),
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 0,
                        "running": 0,
                        "runners": [],
                        "extra_runners": [],
                    }
                ],
                "total": {"count": 0, "running": 0},
            },
            ["Runners configurés"],
        ),
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 1,
                        "running": 1,
                        "runners": [
                            {
                                "id": 1,
                                "name": "g1-1",
                                "status": "running",
                                "labels": "label-as-string",
                            }
                        ],
                        "extra_runners": [],
                    }
                ],
                "total": {"count": 1, "running": 1},
            },
            ["label-as-string"],
        ),
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 1,
                        "running": 1,
                        "runners": [
                            {
                                "id": 1,
                                "name": "g1-1",
                                "status": "running",
                                "labels": ["l1"],
                            }
                        ],
                        "extra_runners": [
                            {"id": 2, "name": "g1-2", "status": "will_be_removed"}
                        ],
                    }
                ],
                "total": {"count": 1, "running": 1},
            },
            ["will be removed", "g1-2"],
        ),
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 1,
                        "running": 1,
                        "runners": [
                            {
                                "id": 1,
                                "name": "g1-1",
                                "status": "running",
                                "labels": ["l1"],
                            }
                        ],
                        "extra_runners": [
                            {"id": 3, "name": "g1-3", "status": "will_be_removed"},
                            {"id": 5, "name": "g1-5", "status": "will_be_removed"},
                        ],
                    }
                ],
                "total": {"count": 1, "running": 1},
            },
            ["will be removed", "g1-3", "g1-5"],
        ),
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 1,
                        "running": 1,
                        "runners": [
                            {
                                "id": 1,
                                "name": "g1-1",
                                "status": "running",
                                "labels": ["l1"],
                            }
                        ],
                        "extra_runners": [],
                    },
                    {
                        "id": "g2",
                        "prefix": "g2",
                        "total": 1,
                        "running": 0,
                        "runners": [
                            {
                                "id": 1,
                                "name": "g2-1",
                                "status": "absent",
                                "labels": ["l2"],
                            }
                        ],
                        "extra_runners": [],
                    },
                ],
                "total": {"count": 2, "running": 1},
            },
            ["g1-1", "g2-1"],
        ),
        (
            {
                "groups": [
                    {
                        "id": "g1",
                        "prefix": "g1",
                        "total": 0,
                        "running": 0,
                        "runners": [],
                        "extra_runners": [
                            {"id": 1, "name": "g1-1", "status": "will_be_removed"},
                            {"id": 2, "name": "g1-2", "status": "will_be_removed"},
                        ],
                    }
                ],
                "total": {"count": 0, "running": 0},
            },
            ["will be removed", "g1-1", "g1-2"],
        ),
    ],
)
@patch("src.services.docker_service.DockerService.list_runners")
def test_list_runners(mock_list, cli, payload, expects):
    mock_list.return_value = payload
    res = cli.invoke(app, ["list-runners"])
    assert res.exit_code == 0
    for e in expects:
        assert e in res.stdout
