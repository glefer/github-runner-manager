"""Tests pour le service scheduler."""

import datetime
from unittest import mock

import pytest

from src.services.config_service import ConfigService
from src.services.docker_service import DockerService
from src.services.scheduler_service import SchedulerService


class MockConsole:
    """Mock pour la console Rich."""

    def __init__(self):
        self.messages = []

    def print(self, message, *args, **kwargs):
        """Enregistre les messages affichés."""
        self.messages.append(message)
        return True


class TestSchedulerService:
    """Tests pour le service SchedulerService."""

    @pytest.fixture
    def mock_config_service(self):
        """Fixture pour un ConfigService mockée."""
        return mock.MagicMock(spec=ConfigService)

    @pytest.fixture
    def mock_docker_service(self):
        """Fixture pour un DockerService mockée."""
        return mock.MagicMock(spec=DockerService)

    @pytest.fixture
    def mock_console(self):
        """Fixture pour une console mockée."""
        return MockConsole()

    @pytest.fixture
    def scheduler_service(self, mock_config_service, mock_docker_service, mock_console):
        """Fixture pour le service scheduler avec des dépendances mockées."""
        return SchedulerService(
            config_service=mock_config_service,
            docker_service=mock_docker_service,
            console=mock_console,
        )

    @pytest.fixture
    def mock_schedule(self, monkeypatch):
        """Fixture pour mocker le module schedule."""
        mock_schedule = mock.MagicMock()
        monkeypatch.setattr("src.services.scheduler_service.schedule", mock_schedule)
        return mock_schedule

    @pytest.fixture
    def valid_config(self):
        """Configuration valide pour les tests."""
        mock_config = mock.MagicMock()
        mock_config.scheduler = mock.MagicMock(
            enabled=True,
            check_interval="30s",
            time_window="10:00-18:00",
            days=["mon", "wed", "fri"],
            actions=["check", "build"],
            max_retries=5,
        )
        return mock_config

    @pytest.fixture
    def disabled_config(self):
        """Configuration avec scheduler désactivé."""
        mock_config = mock.MagicMock()
        mock_config.scheduler = mock.MagicMock(enabled=False)
        return mock_config

    @pytest.fixture
    def schedule_setup_service(self, scheduler_service):
        """Service avec configuration de base pour les tests de setup_schedule."""
        scheduler_service.interval_value = 1
        scheduler_service.interval_unit = "s"
        scheduler_service.schedule_days = []
        scheduler_service.start_time_str = "10:00"
        scheduler_service._jobs = []
        return scheduler_service

    @pytest.fixture
    def mock_datetime_patch(self):
        """Patch pour datetime avec mock personnalisable."""
        with mock.patch("src.services.scheduler_service.datetime") as mock_dt:
            yield mock_dt

    @pytest.fixture
    def configured_scheduler(self, scheduler_service):
        """Scheduler configuré pour les tests d'exécution."""
        scheduler_service.check_time_window = mock.MagicMock(return_value=True)
        scheduler_service.actions = ["check"]
        return scheduler_service

    def test_init(self, scheduler_service):
        """Test l'initialisation du service."""
        assert scheduler_service.config_service is not None
        assert scheduler_service.docker_service is not None
        assert scheduler_service.console is not None
        assert scheduler_service.is_running is False
        assert scheduler_service.retry_count == 0

    def test_load_config_enabled(
        self, scheduler_service, mock_config_service, valid_config
    ):
        """Test le chargement d'une configuration avec scheduler activé."""
        mock_config_service.load_config.return_value = valid_config
        result = scheduler_service.load_config()

        assert result is True
        assert scheduler_service.check_interval == "30s"
        assert scheduler_service.time_window == "10:00-18:00"
        assert scheduler_service.allowed_days == ["mon", "wed", "fri"]
        assert scheduler_service.actions == ["check", "build"]
        assert scheduler_service.max_retries == 5

    def test_load_config_exception(self, scheduler_service, mock_config_service):
        """Test le chargement d'une configuration avec une exception."""
        mock_config_service.load_config.side_effect = Exception("Test error")
        result = scheduler_service.load_config()
        assert result is False
        assert "Erreur" in scheduler_service.console.messages[0]

    @pytest.mark.parametrize(
        "interval,time_window,days,expected",
        [
            ("invalid", "10:00-18:00", ["mon"], "Format d'intervalle invalide"),
            ("30s", "invalid", ["mon"], "Format de plage horaire invalide"),
            ("30s", "10:00-18:00", ["invalid"], "Aucun jour valide"),
        ],
    )
    def test_validate_config_invalid(
        self, scheduler_service, interval, time_window, days, expected
    ):
        """Test la validation avec différents paramètres invalides."""
        scheduler_service.check_interval = interval
        scheduler_service.time_window = time_window
        scheduler_service.allowed_days = days

        result = scheduler_service._validate_config()
        assert result is False
        assert expected in scheduler_service.console.messages[0]

    def test_validate_config_valid(self, scheduler_service):
        """Test la validation d'une configuration valide."""
        scheduler_service.check_interval = "30s"
        scheduler_service.time_window = "10:00-18:00"
        scheduler_service.allowed_days = ["mon", "wed", "fri"]

        result = scheduler_service._validate_config()

        assert result is True
        assert scheduler_service.interval_value == 30
        assert scheduler_service.interval_unit == "s"
        assert scheduler_service.start_time == datetime.time(10, 0)
        assert scheduler_service.end_time == datetime.time(18, 0)
        assert "monday" in scheduler_service.schedule_days
        assert "wednesday" in scheduler_service.schedule_days
        assert "friday" in scheduler_service.schedule_days

    @pytest.mark.parametrize(
        "current_time,expected",
        [
            (datetime.time(12, 0), True),
            (datetime.time(9, 0), False),
        ],
    )
    def test_check_time_window(
        self, scheduler_service, mock_datetime_patch, current_time, expected
    ):
        """Test la vérification de la plage horaire."""
        mock_now = mock.MagicMock()
        mock_now.time.return_value = current_time
        mock_datetime_patch.datetime.now.return_value = mock_now

        scheduler_service.start_time = datetime.time(10, 0)
        scheduler_service.end_time = datetime.time(18, 0)

        result = scheduler_service.check_time_window()
        assert result is expected

    def test_run_scheduled_tasks_outside_time_window(self, configured_scheduler):
        """Test l'exécution des tâches en dehors de la plage horaire."""
        configured_scheduler.check_time_window = mock.MagicMock(return_value=False)
        configured_scheduler.run_scheduled_tasks()
        assert "Hors plage horaire" in configured_scheduler.console.messages[0]

    @pytest.mark.parametrize(
        "docker_result,expected_retry,expected_msg",
        [
            ({"current_version": "1.0.0", "update_available": False}, 0, "déjà à jour"),
            ({"error": "Test error"}, 1, "Erreur"),
        ],
    )
    def test_run_scheduled_tasks_check_scenarios(
        self,
        configured_scheduler,
        mock_docker_service,
        docker_result,
        expected_retry,
        expected_msg,
    ):
        """Test différents scénarios d'exécution de l'action check."""
        mock_docker_service.check_base_image_update.return_value = docker_result
        configured_scheduler.run_scheduled_tasks()

        assert configured_scheduler.retry_count == expected_retry
        messages = configured_scheduler.console.messages
        assert any(expected_msg in msg for msg in messages)

    def test_run_scheduled_tasks_check_update_available(
        self, configured_scheduler, mock_docker_service
    ):
        """Test l'exécution de l'action check avec mise à jour disponible."""
        mock_docker_service.check_base_image_update.return_value = {
            "current_version": "1.0.0",
            "latest_version": "2.0.0",
            "update_available": True,
        }
        configured_scheduler.run_scheduled_tasks()

        messages = configured_scheduler.console.messages
        assert any("Nouvelle version disponible" in msg for msg in messages)

    def test_run_scheduled_tasks_check_build(
        self, configured_scheduler, mock_docker_service
    ):
        """Test l'exécution des actions check et build avec mise à jour."""
        configured_scheduler.actions = ["check", "build"]

        mock_docker_service.check_base_image_update.return_value = {
            "current_version": "1.0.0",
            "latest_version": "2.0.0",
            "update_available": True,
            "updated": True,
            "new_image": "ghcr.io/actions/actions-runner:2.0.0",
        }
        mock_docker_service.build_runner_images.return_value = {
            "built": [{"image": "test:latest", "dockerfile": "./test"}],
            "skipped": [],
            "errors": [],
        }

        configured_scheduler.run_scheduled_tasks()

        messages = configured_scheduler.console.messages
        assert any("base_image mise à jour" in msg for msg in messages)
        assert any("Reconstruction des images" in msg for msg in messages)
        assert any("SUCCESS" in msg for msg in messages)

    def test_run_scheduled_tasks_check_build_with_error(
        self, configured_scheduler, mock_docker_service
    ):
        """Test l'exécution des actions check et build avec erreur de build."""
        configured_scheduler.actions = ["check", "build"]

        mock_docker_service.check_base_image_update.return_value = {
            "current_version": "1.0.0",
            "latest_version": "2.0.0",
            "update_available": True,
            "updated": True,
            "new_image": "ghcr.io/actions/actions-runner:2.0.0",
        }
        mock_docker_service.build_runner_images.return_value = {
            "built": [],
            "skipped": [],
            "errors": [{"id": "test", "reason": "Test error"}],
        }

        configured_scheduler.run_scheduled_tasks()

        assert configured_scheduler.retry_count == 1
        messages = configured_scheduler.console.messages
        assert any("ERREUR" in msg for msg in messages)

    def test_run_scheduled_tasks_check_build_deploy(
        self, configured_scheduler, mock_docker_service
    ):
        """Test build + deploy automatique quand 'deploy' est présent et images construites."""
        configured_scheduler.actions = ["check", "build", "deploy"]

        mock_docker_service.check_base_image_update.return_value = {
            "current_version": "1.0.0",
            "latest_version": "2.0.0",
            "update_available": True,
            "updated": True,
            "new_image": "ghcr.io/actions/actions-runner:2.0.0",
        }
        mock_docker_service.build_runner_images.return_value = {
            "built": [{"image": "test:latest", "dockerfile": "./test", "id": "grp"}],
            "skipped": [],
            "errors": [],
        }
        mock_docker_service.start_runners.return_value = {
            "started": [{"name": "runner-1"}],
            "restarted": [],
            "running": [],
            "removed": [],
            "errors": [],
        }

        configured_scheduler.run_scheduled_tasks()
        messages = configured_scheduler.console.messages
        assert any("Déploiement automatique" in m for m in messages)
        assert any("runner-1 démarré (deploy)" in m for m in messages)
        mock_docker_service.start_runners.assert_called_once()

    def test_run_scheduled_tasks_check_build_deploy_no_built(
        self, configured_scheduler, mock_docker_service
    ):
        """Test que deploy n'est pas appelé si rien n'a été built."""
        configured_scheduler.actions = ["check", "build", "deploy"]

        mock_docker_service.check_base_image_update.return_value = {
            "current_version": "1.0.0",
            "latest_version": "2.0.0",
            "update_available": True,
            "updated": True,
            "new_image": "ghcr.io/actions/actions-runner:2.0.0",
        }
        mock_docker_service.build_runner_images.return_value = {
            "built": [],
            "skipped": [{"id": "grp", "reason": "No build_image specified"}],
            "errors": [],
        }
        configured_scheduler.run_scheduled_tasks()
        messages = configured_scheduler.console.messages
        # Pas de message de déploiement
        assert not any("Déploiement automatique" in m for m in messages)
        mock_docker_service.start_runners.assert_not_called()

    def test_run_scheduled_tasks_check_build_deploy_all_states(
        self, configured_scheduler, mock_docker_service
    ):
        """Test deploy automatique couvrant restarted, running, removed, errors."""
        configured_scheduler.actions = ["check", "build", "deploy"]

        mock_docker_service.check_base_image_update.return_value = {
            "current_version": "1.0.0",
            "latest_version": "2.0.0",
            "update_available": True,
            "updated": True,
            "new_image": "ghcr.io/actions/actions-runner:2.0.0",
        }
        mock_docker_service.build_runner_images.return_value = {
            "built": [{"image": "test:latest", "dockerfile": "./test", "id": "grp"}],
            "skipped": [],
            "errors": [],
        }
        mock_docker_service.start_runners.return_value = {
            "started": [],
            "restarted": [{"name": "runner-r1"}],
            "running": [{"name": "runner-r2"}],
            "removed": [{"name": "old-container"}],
            "errors": [{"id": "bad", "reason": "failure"}],
        }

        configured_scheduler.run_scheduled_tasks()
        messages = configured_scheduler.console.messages
        # Vérifie chaque message spécifique
        assert any("runner-r1 redémarré (deploy)" in m for m in messages)
        assert any("runner-r2 déjà en cours (deploy)" in m for m in messages)
        assert any("old-container supprimé (deploy)" in m for m in messages)
        assert any("bad: failure (deploy)" in m for m in messages)
        mock_docker_service.start_runners.assert_called_once()

    def test_run_scheduled_tasks_check_build_deploy_exception(
        self, configured_scheduler, mock_docker_service
    ):
        """Test exception lors du déploiement automatique (start_runners)."""
        configured_scheduler.actions = ["check", "build", "deploy"]
        configured_scheduler.retry_count = 0

        mock_docker_service.check_base_image_update.return_value = {
            "current_version": "1.0.0",
            "latest_version": "2.0.0",
            "update_available": True,
            "updated": True,
            "new_image": "ghcr.io/actions/actions-runner:2.0.0",
        }
        mock_docker_service.build_runner_images.return_value = {
            "built": [{"image": "test:latest", "dockerfile": "./test", "id": "grp"}],
            "skipped": [],
            "errors": [],
        }
        mock_docker_service.start_runners.side_effect = Exception("boom")

        configured_scheduler.run_scheduled_tasks()
        messages = configured_scheduler.console.messages
        assert any("Erreur lors du déploiement automatique" in m for m in messages)
        assert configured_scheduler.retry_count == 1

    def test_run_scheduled_tasks_max_retries(
        self, configured_scheduler, mock_docker_service
    ):
        """Test l'atteinte du nombre maximal de tentatives."""
        configured_scheduler.max_retries = 1
        configured_scheduler.retry_count = 1
        configured_scheduler.stop = mock.MagicMock()

        mock_docker_service.check_base_image_update.return_value = {
            "error": "Test error"
        }
        configured_scheduler.run_scheduled_tasks()

        messages = configured_scheduler.console.messages
        assert any("Nombre maximal de tentatives atteint" in msg for msg in messages)
        configured_scheduler.stop.assert_called_once()

    def test_run_scheduled_tasks_exception(
        self, configured_scheduler, mock_docker_service
    ):
        """Test une exception pendant l'exécution des tâches."""
        configured_scheduler.max_retries = 2
        configured_scheduler.retry_count = 0
        configured_scheduler.stop = mock.MagicMock()

        mock_docker_service.check_base_image_update.side_effect = Exception(
            "Test exception"
        )
        configured_scheduler.run_scheduled_tasks()

        assert configured_scheduler.retry_count == 1
        messages = configured_scheduler.console.messages
        assert any("Erreur pendant l'exécution des tâches" in msg for msg in messages)

        # Simuler une nouvelle exécution pour atteindre max_retries
        configured_scheduler.retry_count = 2
        configured_scheduler.run_scheduled_tasks()
        configured_scheduler.stop.assert_called_once()

    @pytest.mark.parametrize(
        "interval_unit,mock_attr",
        [
            ("s", "seconds"),
            ("m", "minutes"),
            ("h", "hours"),
        ],
    )
    def test_setup_schedule_intervals(
        self, schedule_setup_service, mock_schedule, interval_unit, mock_attr
    ):
        """Test la configuration du scheduler avec différents intervalles."""
        schedule_setup_service.interval_value = (
            30 if interval_unit == "s" else 5 if interval_unit == "m" else 1
        )
        schedule_setup_service.interval_unit = interval_unit

        # Configure le mock
        mock_job = mock.MagicMock()
        mock_time_unit = mock.MagicMock()
        mock_time_unit.do.return_value = mock_job
        mock_every_result = mock.MagicMock()
        setattr(mock_every_result, mock_attr, mock_time_unit)
        mock_schedule.every.return_value = mock_every_result

        schedule_setup_service._setup_schedule()

        # Vérifications
        mock_schedule.clear.assert_called_once()
        expected_value = schedule_setup_service.interval_value
        mock_schedule.every.assert_any_call(expected_value)
        mock_time_unit.do.assert_called_with(schedule_setup_service.run_scheduled_tasks)

    def test_setup_schedule_invalid_day(self, schedule_setup_service, mock_schedule):
        """Test la configuration avec un jour invalide."""
        schedule_setup_service.schedule_days = ["invalid_day"]
        mock_seconds_job = mock.MagicMock()
        mock_seconds = mock.MagicMock()
        mock_seconds.do.return_value = mock_seconds_job
        mock_every_result = mock.MagicMock()
        mock_every_result.seconds = mock_seconds
        mock_schedule.every.return_value = mock_every_result

        schedule_setup_service._setup_schedule()

        assert len(schedule_setup_service._jobs) == 1
        assert schedule_setup_service._jobs[0] is mock_seconds_job

    def test_setup_schedule_invalid_interval_unit(
        self, schedule_setup_service, mock_schedule
    ):
        """Test la configuration avec une unité d'intervalle invalide."""
        schedule_setup_service.interval_unit = "x"
        schedule_setup_service._setup_schedule()
        assert len(schedule_setup_service._jobs) == 0

    @pytest.mark.parametrize(
        "day_attr",
        ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    )
    def test_setup_schedule_days(self, schedule_setup_service, mock_schedule, day_attr):
        """Test la configuration du scheduler pour tous les jours de la semaine."""
        schedule_setup_service.schedule_days = [day_attr]

        # Configure les mocks pour l'intervalle de secondes
        mock_seconds = mock.MagicMock()
        mock_seconds_job = mock.MagicMock()
        mock_seconds.do.return_value = mock_seconds_job
        mock_every_result = mock.MagicMock()
        mock_every_result.seconds = mock_seconds

        # Configure les mocks pour le jour spécifique
        mock_day_job = mock.MagicMock()
        mock_day_at_do = mock.MagicMock()
        mock_day_at_do.do.return_value = mock_day_job
        mock_day_at = mock.MagicMock()
        mock_day_at.return_value = mock_day_at_do
        mock_day = mock.MagicMock()
        mock_day.at = mock_day_at

        # Configure les retours de schedule.every()
        mock_every_day = mock.MagicMock()
        setattr(mock_every_day, day_attr, mock_day)
        mock_schedule.every.side_effect = [mock_every_result, mock_every_day]

        schedule_setup_service._setup_schedule()

        # Vérifications
        mock_day.at.assert_called_with("10:00")
        mock_day_at_do.do.assert_called_with(schedule_setup_service.run_scheduled_tasks)
        assert len(schedule_setup_service._jobs) == 2
        assert mock_day_job in schedule_setup_service._jobs

    def test_start_config_failed(self, scheduler_service):
        """Test le démarrage du scheduler quand la configuration échoue."""
        scheduler_service.load_config = mock.MagicMock(return_value=False)
        scheduler_service._setup_schedule = mock.MagicMock()
        scheduler_service.start()

        scheduler_service.load_config.assert_called_once()
        scheduler_service._setup_schedule.assert_not_called()

    @mock.patch("src.services.scheduler_service.time")
    def test_start_and_stop(self, mock_time, scheduler_service):
        """Test le démarrage et l'arrêt du scheduler."""
        scheduler_service.load_config = mock.MagicMock(return_value=True)
        scheduler_service._setup_schedule = mock.MagicMock()
        scheduler_service.check_interval = "30s"
        scheduler_service.time_window = "10:00-18:00"
        scheduler_service.allowed_days = ["mon", "wed", "fri"]
        scheduler_service.actions = ["check", "build"]

        def side_effect(*args, **kwargs):
            scheduler_service.is_running = False

        mock_time.sleep.side_effect = side_effect
        scheduler_service.start()

        scheduler_service.load_config.assert_called_once()
        scheduler_service._setup_schedule.assert_called_once()
        assert "Scheduler démarré" in scheduler_service.console.messages[0]
        assert not scheduler_service.is_running

    @pytest.mark.parametrize(
        "exception_type,expected_msg",
        [
            (KeyboardInterrupt(), "Scheduler arrêté manuellement."),
            (Exception("fail"), "Erreur dans le scheduler: fail"),
        ],
    )
    def test_start_exceptions(
        self, scheduler_service, mock_schedule, exception_type, expected_msg
    ):
        """Test start avec différentes exceptions dans la boucle principale."""
        scheduler_service.load_config = mock.MagicMock(return_value=True)
        scheduler_service._setup_schedule = mock.MagicMock()
        scheduler_service.is_running = True

        mock_schedule.run_pending.side_effect = exception_type
        scheduler_service.console = mock.MagicMock()

        with mock.patch("src.services.scheduler_service.time.sleep"):
            scheduler_service.start()

        scheduler_service.console.print.assert_any_call(
            f"[yellow]{expected_msg}[/yellow]"
            if isinstance(exception_type, KeyboardInterrupt)
            else f"[red]{expected_msg}[/red]"
        )
        assert not scheduler_service.is_running

    def test_stop(self, scheduler_service, mock_schedule):
        """Test l'arrêt du scheduler."""
        scheduler_service.is_running = True
        scheduler_service._jobs = ["job1", "job2"]

        scheduler_service.stop()

        assert not scheduler_service.is_running
        assert not scheduler_service._jobs
        mock_schedule.clear.assert_called_once()

    def test_execute_actions_no_check(self, scheduler_service):
        """Test _execute_actions quand 'check' n'est pas dans actions."""
        scheduler_service.actions = ["build"]
        scheduler_service._execute_actions()  # Ne doit pas lever d'exception

    @pytest.mark.parametrize(
        "docker_result,expected_behavior",
        [
            ({"current_version": "1.2.3"}, "no_special_action"),
            (
                {
                    "current_version": "1.0.0",
                    "latest_version": "2.0.0",
                    "update_available": True,
                    "updated": False,
                },
                "no_build_action",
            ),
        ],
    )
    def test_execute_check_action_edge_cases(
        self, scheduler_service, mock_docker_service, docker_result, expected_behavior
    ):
        """Test _execute_check_action pour les cas limites."""
        scheduler_service.actions = ["check"]
        mock_docker_service.check_base_image_update.return_value = docker_result
        scheduler_service.docker_service = mock_docker_service

        scheduler_service._execute_check_action()  # Ne doit pas lever d'exception

    @pytest.mark.parametrize(
        "build_result,expected_retry",
        [
            ({"built": [], "skipped": [], "errors": []}, 0),
            (
                {
                    "built": [],
                    "skipped": [{"id": "foo", "reason": "no build"}],
                    "errors": [],
                },
                0,
            ),
            (
                {
                    "built": [],
                    "skipped": [],
                    "errors": [{"id": "foo", "reason": "fail"}],
                },
                1,
            ),
        ],
    )
    def test_execute_build_action_scenarios(
        self, scheduler_service, mock_docker_service, build_result, expected_retry
    ):
        """Test _execute_build_action avec différents résultats de build."""
        scheduler_service.docker_service = mock_docker_service
        mock_docker_service.build_runner_images.return_value = build_result
        initial_retry = scheduler_service.retry_count

        scheduler_service._execute_build_action({"new_image": "img"})

        assert scheduler_service.retry_count == initial_retry + expected_retry
