"""Service for managing scheduled tasks in GitHub Runner Manager."""

from __future__ import annotations

import datetime
import re
import time
from typing import Any, Dict, Optional

import schedule
from rich.console import Console

from src.services.config_service import ConfigService
from src.services.docker_service import DockerService


class SchedulerService:
    """Service for managing scheduled tasks in GitHub Runner Manager."""

    def __init__(
        self,
        config_service: ConfigService,
        docker_service: DockerService,
        console: Optional[Console] = None,
    ):
        self.config_service = config_service
        self.docker_service = docker_service
        self.console = console or Console()
        self.is_running = False
        self.retry_count = 0
        self._jobs = []
        self.check_interval = "15s"
        self.time_window = "00:00-23:59"
        self.allowed_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        self.actions = []
        self.max_retries = 3
        self.start_time = None
        self.end_time = None
        self.schedule_days = []

    def load_config(self) -> bool:
        """Load and validate the scheduler configuration.

        Returns:
            bool: True if the configuration is valid and the scheduler is enabled, False otherwise
        """
        try:
            config = self.config_service.load_config()
            scheduler_config = getattr(config, "scheduler", None)

            self.check_interval = getattr(scheduler_config, "check_interval", "15s")
            self.time_window = getattr(scheduler_config, "time_window", "00:00-23:59")
            self.allowed_days = getattr(
                scheduler_config,
                "days",
                ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            )
            self.actions = getattr(scheduler_config, "actions", [])
            self.max_retries = getattr(scheduler_config, "max_retries", 3)

            return self._validate_config()

        except Exception as e:
            self.console.print(f"[red]Error loading configuration: {str(e)}[/red]")
            return False

    def _validate_config(self) -> bool:
        """Validate configuration parameters.

        Returns:
            bool: True if the configuration is valid, False otherwise
        """
        interval_match = re.match(r"(\d+)([smh])", self.check_interval)
        if not interval_match:
            self.console.print(
                f"[red]Invalid interval format: {self.check_interval}[/red]"
            )
            return False

        self.interval_value = int(interval_match.group(1))
        self.interval_unit = interval_match.group(2)

        window_match = re.match(r"(\d{2}):(\d{2})-(\d{2}):(\d{2})", self.time_window)
        if not window_match:
            self.console.print(
                f"[red]Invalid time window format: {self.time_window}[/red]"
            )
            return False

        start_h, start_m, end_h, end_m = map(int, window_match.groups())
        self.start_time = datetime.time(start_h, start_m)
        self.end_time = datetime.time(end_h, end_m)
        self.start_time_str = f"{start_h:02d}:{start_m:02d}"

        day_map = {
            "mon": "monday",
            "tue": "tuesday",
            "wed": "wednesday",
            "thu": "thursday",
            "fri": "friday",
            "sat": "saturday",
            "sun": "sunday",
        }

        self.schedule_days = [
            day_map.get(day.lower())
            for day in self.allowed_days
            if day.lower() in day_map
        ]

        if not self.schedule_days:
            self.console.print("[red]No valid day configured.[/red]")
            return False

        return True

    def check_time_window(self) -> bool:
        """Check if the current time is within the allowed time window.

        Returns:
            bool: True if the current time is within the allowed time window, False otherwise
        """
        now = datetime.datetime.now().time()
        return self.start_time <= now <= self.end_time

    def run_scheduled_tasks(self) -> None:
        """Run scheduled tasks according to the configuration."""
        if not self.check_time_window():
            self.console.print(
                "[yellow]Outside allowed time window - Task postponed[/yellow]"
            )
            return

        now = datetime.datetime.now()
        self.console.print(
            f"\n[blue]Executing scheduled actions at {now.strftime('%H:%M:%S')}[/blue]"
        )

        try:
            self._execute_actions()

            if self.retry_count == 0:
                self.console.print("[green]Execution completed successfully[/green]")

            if self.retry_count >= self.max_retries:
                self.console.print(
                    f"[red]Maximum retry count reached ({self.max_retries}). "
                    f"Stopping scheduler.[/red]"
                )
                self.stop()

        except Exception as e:
            self.console.print(
                f"[red]Error occurred while executing tasks: {str(e)}[/red]"
            )
            self.retry_count += 1

            if self.retry_count >= self.max_retries:
                self.console.print(
                    f"[red]No maximum retry count reached ({self.max_retries}). "
                    f"Stopping scheduler.[/red]"
                )
                self.stop()

    def _execute_actions(self) -> None:
        """Run the configured actions."""
        if "check" in self.actions:
            self._execute_check_action()

    def _execute_check_action(self) -> None:
        """Run the action to check for image updates."""
        self.console.print("[cyan]Action: Check for image updates[/cyan]")
        check_result = self.docker_service.check_base_image_update(
            auto_update="build" in self.actions
        )

        if check_result.get("error"):
            self.console.print(f"[red]Error: {check_result['error']}[/red]")
            self.retry_count += 1
            return

        if not check_result.get("update_available"):
            self.console.print(
                f"[green]The runner image is up to date: v{check_result['current_version']}[/green]"
            )
            self.retry_count = 0
            return

        self.console.print(
            f"[yellow]New version available: {check_result['latest_version']} "
            f"(current: {check_result['current_version']})[/yellow]"
        )

        if "build" in self.actions and check_result.get("updated"):
            self._execute_build_action(check_result)

    def _execute_build_action(self, check_result: Dict[str, Any]) -> None:
        """Run the action to build images.

        Args:
            check_result: Result of the update check
        """
        self.console.print(
            f"[green]base_image updated to {check_result['new_image']} "
            f"in runners_config.yaml[/green]"
        )

        self.console.print("[cyan]Action: Rebuilding runner images[/cyan]")
        build_result = self.docker_service.build_runner_images(
            quiet=True, use_progress=False
        )

        for built in build_result.get("built", []):
            self.console.print(
                f"[green][SUCCESS] Image {built['image']} built from {built['dockerfile']}[/green]"
            )

        for skipped in build_result.get("skipped", []):
            self.console.print(
                f"[yellow][INFO] No image to build for {skipped['id']} "
                f"({skipped['reason']})[/yellow]"
            )

        for error in build_result.get("errors", []):
            self.console.print(f"[red][ERROR] {error['id']}: {error['reason']}[/red]")
            self.retry_count += 1

        if "deploy" in self.actions and build_result.get("built"):
            self.console.print("[cyan]Action: Automatic deployment of runners[/cyan]")
            try:
                start_result = self.docker_service.start_runners()
                for started in start_result.get("started", []):
                    self.console.print(
                        f"[green][INFO] Runner {started['name']} started (deploy).[/green]"
                    )
                for restarted in start_result.get("restarted", []):
                    self.console.print(
                        f"[yellow][INFO] Runner {restarted['name']} restarted (deploy).[/yellow]"
                    )
                for running in start_result.get("running", []):
                    self.console.print(
                        f"[blue][INFO] Runner {running['name']} already running (deploy).[/blue]"
                    )
                for removed in start_result.get("removed", []):
                    self.console.print(
                        f"[magenta][INFO] Container {removed['name']} removed (deploy).[/magenta]"
                    )
                for error in start_result.get("errors", []):
                    self.console.print(
                        f"[red][ERROR] {error['id']}: {error['reason']} (deploy)[/red]"
                    )
            except Exception as e:
                self.console.print(
                    f"[red]Error during automatic deployment: {str(e)}[/red]"
                )
                self.retry_count += 1

    def _setup_schedule(self) -> None:
        """Configure scheduled tasks with the schedule library."""
        schedule.clear()
        unit_map = {
            "s": lambda: schedule.every(self.interval_value).seconds,
            "m": lambda: schedule.every(self.interval_value).minutes,
            "h": lambda: schedule.every(self.interval_value).hours,
        }
        job = None
        if self.interval_unit in unit_map:
            job = unit_map[self.interval_unit]().do(self.run_scheduled_tasks)
            self._jobs.append(job)

        day_map = {
            "monday": lambda: schedule.every().monday,
            "tuesday": lambda: schedule.every().tuesday,
            "wednesday": lambda: schedule.every().wednesday,
            "thursday": lambda: schedule.every().thursday,
            "friday": lambda: schedule.every().friday,
            "saturday": lambda: schedule.every().saturday,
            "sunday": lambda: schedule.every().sunday,
        }
        for day in self.schedule_days:
            if day in day_map:
                job = (
                    day_map[day]().at(self.start_time_str).do(self.run_scheduled_tasks)
                )
                self._jobs.append(job)

    def start(self) -> None:
        """Starts the scheduler."""
        if not self.load_config():
            return

        self._setup_schedule()

        self.console.print("[blue]Scheduler started:[/blue]")
        self.console.print(f"  [cyan]Interval:[/cyan] {self.check_interval}")
        self.console.print(f"  [cyan]Time window:[/cyan] {self.time_window}")
        self.console.print(f"  [cyan]Days:[/cyan] {', '.join(self.allowed_days)}")
        self.console.print(f"  [cyan]Actions:[/cyan] {', '.join(self.actions)}")

        self.is_running = True

        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            self.console.print("[yellow]Scheduler stopped manually.[/yellow]")
            self.stop()
        except Exception as e:
            self.console.print(f"[red]Error in scheduler: {str(e)}[/red]")
            self.stop()

    def stop(self) -> None:
        """Stops the scheduler."""
        self.is_running = False
        schedule.clear()
        self._jobs = []
