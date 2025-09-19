"""Service Docker pour gérer les runners GitHub Actions."""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import docker
import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from src.services.config_service import ConfigService
from src.services.docker_logger import DockerBuildLogger


class DockerService:
    def _get_registration_token(
        self, org_url: str, github_personal_token: Optional[str] = None
    ) -> str:
        """Obtient dynamiquement un registration token via l'API GitHub."""

        if github_personal_token is None:
            github_personal_token = os.getenv("GITHUB_TOKEN")
        if not github_personal_token:
            raise Exception(
                "Le token GitHub n'est pas défini. Ajoutez GITHUB_TOKEN dans votre environnement."
            )
        headers = {
            "Authorization": f"Bearer {github_personal_token}",
            "Accept": "application/vnd.github+json",
        }
        if org_url.endswith("/"):
            org_url = org_url[:-1]
        if org_url.count("/") == 3:
            org = org_url.split("/")[-1]
            url = (
                f"https://api.github.com/orgs/{org}/actions/runners/registration-token"
            )
        else:
            owner, repo = org_url.split("/")[-2:]
            url = f"https://api.github.com/repos/{owner}/{repo}/actions/runners/registration-token"
        for _ in range(3):
            resp = requests.post(url, headers=headers, timeout=10)
            if resp.status_code == 201:
                token = resp.json().get("token")
                if isinstance(token, str):
                    return token
                else:
                    raise Exception("Token returned by GitHub API is not a string.")
            time.sleep(1)
        raise Exception(
            f"Impossible d'obtenir un registration token GitHub: {resp.text}"
        )

    def __init__(self, config_service: ConfigService):
        self.config_service = config_service

    def container_exists(self, name: str) -> bool:
        """Vérifie si un conteneur existe (docker-py)."""

        client = docker.from_env()
        try:
            client.containers.get(name)
            return True
        except docker.errors.NotFound:
            return False
        except Exception:
            return False

    def container_running(self, name: str) -> bool:
        """Vérifie si un conteneur est en cours d'exécution (docker-py)."""

        client = docker.from_env()
        try:
            container = client.containers.get(name)
            return container.status == "running"
        except docker.errors.NotFound:
            return False
        except Exception:
            return False

    def run_command(self, cmd: List[str], info: str = "") -> None:
        subprocess.run(cmd, check=True)

    def image_exists(self, tag: str) -> bool:
        """Vérifie si une image Docker existe (docker-py)."""

        client = docker.from_env()
        try:
            images = client.images.list(name=tag)
            return len(images) > 0
        except Exception:
            return False

    def build_image(
        self,
        image_tag: str,
        dockerfile_path: str,
        build_dir: str,
        build_args: Dict[str, str] | None = None,
        logger: Optional[callable] = None,
        quiet: bool = False,
        use_progress: bool = False,
    ) -> None:
        """Construit une image Docker (docker-py)."""

        client = docker.from_env()
        buildargs = build_args or {}
        api_client = client.api
        dockerfile_rel = os.path.relpath(dockerfile_path, build_dir)
        stream = api_client.build(
            path=build_dir,
            dockerfile=dockerfile_rel,
            tag=image_tag,
            buildargs=buildargs,
            rm=True,
            decode=True,
        )

        # Use DockerBuildLogger if no custom logger provided
        if logger is None:
            logger = DockerBuildLogger.get_logger(quiet)

        # If progress requested, create a progress bar and use it for logging
        if use_progress:
            console = Console()
            progress = Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(bar_width=None),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            )

            task_id = None
            try:
                with progress:
                    for chunk in stream:
                        if not chunk:
                            continue
                        if isinstance(chunk, dict):
                            if "stream" in chunk:
                                line = chunk["stream"].rstrip("\n")
                                # detect Step X/Y : lines
                                m = re.search(r"Step\s+(\d+)\/(\d+)", line)
                                if m:
                                    cur = int(m.group(1))
                                    total = int(m.group(2))
                                    if task_id is None:
                                        task_id = progress.add_task(
                                            "Building image", total=total
                                        )
                                    # progress expects completed value; ensure monotonic update
                                    progress.update(
                                        task_id, completed=cur, description=line
                                    )
                                else:
                                    progress.console.log(line)
                            elif "status" in chunk:
                                msg = chunk.get("status", "")
                                prog = chunk.get("progress", "")
                                if prog:
                                    progress.console.log(f"{msg} {prog}")
                                else:
                                    progress.console.log(msg)
                            elif "error" in chunk:
                                raise Exception(chunk.get("error"))
                            else:
                                progress.console.log(str(chunk))
                        else:
                            progress.console.log(str(chunk))
                    # ensure task marked complete
                    if task_id is not None:
                        progress.update(task_id, completed=progress.tasks[0].total)
            finally:
                try:
                    if hasattr(stream, "close"):
                        stream.close()
                except Exception:
                    pass
            return

        # Iterate over the stream and log progress lines
        try:
            for chunk in stream:
                # chunk is expected to be a dict when decode=True
                if not chunk:
                    continue
                # Some messages contain 'stream' (plain text), others 'status' and 'progress'
                if isinstance(chunk, dict):
                    if "stream" in chunk:
                        logger(chunk["stream"].rstrip("\n"))
                    elif "status" in chunk:
                        msg = chunk.get("status", "")
                        prog = chunk.get("progress", "")
                        if prog:
                            logger(f"{msg} {prog}")
                        else:
                            logger(msg)
                    elif "error" in chunk:
                        # raise with docker error message
                        raise Exception(chunk.get("error"))
                    else:
                        # Fallback to string representation
                        logger(str(chunk))
                else:
                    logger(str(chunk))
        finally:
            # ensure generator is exhausted/closed
            try:
                if hasattr(stream, "close"):
                    stream.close()
            except Exception:
                pass

    def exec_command(self, container: str, command: str) -> None:
        """Exécute une commande dans un conteneur en cours d'exécution (docker-py)."""

        client = docker.from_env()
        cont = client.containers.get(container)
        cont.exec_run(command, privileged=True, detach=False)

    def start_container(self, name: str) -> None:
        """Démarre un conteneur (docker-py)."""

        client = docker.from_env()
        container = client.containers.get(name)
        container.start()

    def stop_container(self, name: str) -> None:
        """Arrête un conteneur (docker-py)."""

        client = docker.from_env()
        container = client.containers.get(name)
        container.stop()

    def remove_container(self, name: str, force: bool = False) -> None:
        """Supprime un conteneur (docker-py)."""

        client = docker.from_env()
        container = client.containers.get(name)
        container.remove(force=force)

    def run_container(
        self,
        name: str,
        image: str,
        command: str,
        env_vars: Dict[str, str],
        detach: bool = True,
    ) -> None:
        """Exécute un nouveau conteneur."""
        cmd = ["docker", "run"]

        if detach:
            cmd.append("-d")

        cmd.extend(["--name", name])

        cmd.extend(["--restart", "always"])

        for k, v in env_vars.items():
            cmd.extend(["-e", f"{k}={v}"])

        cmd.append(image)

        if command:
            cmd.extend(["/bin/bash", "-c", command])

        self.run_command(cmd)

    def list_containers(self, name_pattern: Optional[str] = None) -> List[str]:
        """Liste les noms des conteneurs, éventuellement filtrés par modèle (docker-py)."""

        client = docker.from_env()
        containers = client.containers.list(all=True)
        names = [c.name for c in containers]
        if name_pattern:
            return [name for name in names if name_pattern in name]
        return names

    def build_runner_images(
        self, quiet: bool = False, use_progress: bool = False
    ) -> dict:
        """Construit les images Docker personnalisées pour les runners."""
        config = self.config_service.load_config()
        runners = config.runners
        defaults = config.runners_defaults
        base_image_default = defaults.base_image

        m = re.search(r":([\d.]+)$", base_image_default)
        runner_version = m.group(1) if m else "latest"

        result: dict[str, list[dict[str, str]]] = {
            "built": [],
            "skipped": [],
            "errors": [],
        }

        for runner in runners:
            build_image = getattr(runner, "build_image", None)
            techno = getattr(runner, "techno", None)
            techno_version = getattr(runner, "techno_version", None)
            base_image = getattr(runner, "base_image", base_image_default)

            if not build_image:
                runner_id = getattr(runner, "name_prefix", "unknown")
                result["skipped"].append(
                    {"id": runner_id, "reason": "No build_image specified"}
                )
                continue

            if not (techno and techno_version):
                runner_id = getattr(runner, "name_prefix", "unknown")
                result["errors"].append(
                    {"id": runner_id, "reason": "Missing techno or techno_version"}
                )
                continue

            try:
                image_tag = f"itroom/{techno}:{techno_version}-{runner_version}"
                build_dir = os.path.dirname(build_image) or "."
                dockerfile_path = build_image

                self.build_image(
                    image_tag=image_tag,
                    dockerfile_path=dockerfile_path,
                    build_dir=build_dir,
                    build_args={"BASE_IMAGE": base_image},
                    quiet=quiet,
                    use_progress=use_progress,
                )

                result["built"].append(
                    {
                        "id": getattr(runner, "name_prefix", "unknown"),
                        "image": image_tag,
                        "dockerfile": dockerfile_path,
                    }
                )

            except Exception as e:
                result["errors"].append(
                    {"id": getattr(runner, "name_prefix", "unknown"), "reason": str(e)}
                )

        return result

    def start_runners(self) -> dict:
        """Démarre les runners Docker selon la configuration."""
        config = self.config_service.load_config()

        defaults = config.runners_defaults
        base_image_default = defaults.base_image
        org_url_default = defaults.org_url
        runners = config.runners

        m = re.search(r":([\d.]+)$", base_image_default)
        runner_version = m.group(1) if m else "latest"

        result: dict[str, list[dict[str, str]]] = {
            "started": [],
            "restarted": [],
            "running": [],
            "removed": [],
            "errors": [],
        }

        for runner in runners:
            prefix = runner.name_prefix
            labels = runner.labels
            nb = runner.nb
            build_image = getattr(runner, "build_image", None)
            techno = getattr(runner, "techno", None)
            techno_version = getattr(runner, "techno_version", None)
            base_image = getattr(runner, "base_image", base_image_default)
            org_url = getattr(runner, "org_url", org_url_default)
            if build_image and techno and techno_version:
                image = f"itroom/{techno}:{techno_version}-{runner_version}"
            else:
                image = f"{prefix}:latest"

            if build_image and not self.image_exists(image):
                try:
                    if techno and techno_version:
                        build_dir = os.path.dirname(build_image) or "."
                        self.build_image(
                            image_tag=image,
                            dockerfile_path=build_image,
                            build_dir=build_dir,
                            build_args={"BASE_IMAGE": base_image},
                        )
                    else:
                        build_dir = os.path.dirname(build_image) or "."
                        self.build_image(
                            image_tag=image,
                            dockerfile_path=build_image,
                            build_dir=build_dir,
                        )
                except Exception as e:
                    result["errors"].append(
                        {"id": prefix, "reason": f"Build failed: {str(e)}"}
                    )
                    continue

            all_containers = self.list_containers(prefix + "-")
            for name in all_containers:
                try:
                    parts = name.split("-")
                    if len(parts) < 2:
                        continue
                    idx = int(parts[-1])
                    if idx > nb:
                        try:
                            if self.container_running(name):
                                self.start_container(name)
                            self.exec_command(
                                name,
                                'bash -c "./config.sh remove --token $RUNNER_TOKEN || true"',
                            )
                            self.remove_container(name, force=True)
                            runner_dir = Path(f"runner-{idx}").absolute()
                            if runner_dir.exists():
                                shutil.rmtree(runner_dir)
                            result["removed"].append({"name": name})
                        except Exception as e:
                            result["errors"].append(
                                {"id": name, "operation": "removal", "reason": str(e)}
                            )
                except (ValueError, IndexError):
                    continue

            for i in range(1, nb + 1):
                runner_name = f"{prefix}-{i}"
                try:
                    if self.container_exists(runner_name):
                        if self.container_running(runner_name):
                            result["running"].append({"name": runner_name})
                        else:
                            self.start_container(runner_name)
                            result["restarted"].append({"name": runner_name})
                    else:
                        registration_token = self._get_registration_token(org_url, None)
                        env_vars = {
                            "RUNNER_NAME": runner_name,
                            "RUNNER_REPO": org_url,
                            "RUNNER_TOKEN": registration_token,
                            "RUNNER_LABELS": (
                                ",".join(labels) if isinstance(labels, list) else labels
                            ),
                        }
                        command = (
                            f"./config.sh --url {org_url} --token {registration_token} "
                            f"--name {runner_name} --labels "
                            f"{','.join(labels) if isinstance(labels, list) else labels} "
                            f"--unattended && ./run.sh"
                        )
                        self.run_container(
                            name=runner_name,
                            image=image,
                            command=command,
                            env_vars=env_vars,
                        )
                        result["started"].append({"name": runner_name})
                except Exception as e:
                    result["errors"].append(
                        {"id": runner_name, "operation": "start", "reason": str(e)}
                    )

        return result

    def stop_runners(self) -> dict:
        """Arrête les runners Docker selon la configuration."""
        config = self.config_service.load_config()
        runners = getattr(config, "runners", [])

        result: dict[str, list[dict[str, str]]] = {
            "stopped": [],
            "skipped": [],
            "errors": [],
        }

        for runner in runners:
            prefix = runner.name_prefix
            nb = runner.nb

            for i in range(1, nb + 1):
                runner_name = f"{prefix}-{i}"
                try:
                    if self.container_running(runner_name):
                        self.stop_container(runner_name)
                        result["stopped"].append({"name": runner_name})
                    else:
                        result["skipped"].append(
                            {"name": runner_name, "reason": "Not running"}
                        )
                except Exception as e:
                    result["errors"].append({"name": runner_name, "reason": str(e)})

        return result

    def remove_runners(self) -> dict:
        """Supprime les runners Docker selon la configuration."""
        config = self.config_service.load_config()
        runners = getattr(config, "runners", [])

        result: dict[str, list[dict[str, str]]] = {
            "removed": [],
            "skipped": [],
            "errors": [],
        }

        for runner in runners:
            prefix = runner.name_prefix
            nb = runner.nb

            for i in range(1, nb + 1):
                runner_name = f"{prefix}-{i}"
                try:
                    if self.container_exists(runner_name):
                        if not self.container_running(runner_name):
                            self.start_container(runner_name)
                        self.exec_command(
                            runner_name,
                            'bash -c "./config.sh remove --token $RUNNER_TOKEN || true"',
                        )
                        self.remove_container(runner_name, force=True)
                        result["removed"].append({"container": runner_name})
                    else:
                        result["skipped"].append(
                            {"name": runner_name, "reason": "Container not found"}
                        )
                except Exception as e:
                    result["errors"].append({"name": runner_name, "reason": str(e)})

        return result

    def list_runners(self) -> dict:
        """Liste les runners Docker avec leur état."""
        config = self.config_service.load_config()
        runners = getattr(config, "runners", [])

        result: dict = {"groups": [], "total": {"count": 0, "running": 0}}

        for runner in runners:
            prefix = runner.name_prefix
            nb = runner.nb
            labels = runner.labels
            group_id = getattr(runner, "id", prefix)

            group_info = {
                "id": group_id,
                "prefix": prefix,
                "total": nb,
                "running": 0,
                "runners": [],
                "extra_runners": [],
            }

            all_containers = self.list_containers(prefix + "-")

            for i in range(1, nb + 1):
                runner_name = f"{prefix}-{i}"

                status = "absent"
                if self.container_exists(runner_name):
                    if self.container_running(runner_name):
                        status = "running"
                        group_info["running"] += 1
                        result["total"]["running"] += 1
                    else:
                        status = "stopped"

                group_info["runners"].append(
                    {"id": i, "name": runner_name, "status": status, "labels": labels}
                )

            for name in all_containers:
                try:
                    parts = name.split("-")
                    if len(parts) < 2:
                        continue
                    idx = int(parts[-1])
                    if idx > nb:
                        status = "will_be_removed"
                        if self.container_running(name):
                            status = "running_will_be_removed"

                        group_info["extra_runners"].append(
                            {"id": idx, "name": name, "status": status}
                        )
                except (ValueError, IndexError):
                    continue

            result["groups"].append(group_info)
            result["total"]["count"] += nb

        return result

    def get_latest_runner_version(self) -> Optional[str]:
        """Récupère la dernière version du runner GitHub via l'API GitHub."""

        try:
            url = "https://api.github.com/repos/actions/runner/releases/latest"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            tag = data.get("tag_name")
            if isinstance(tag, str):
                if tag.startswith("v"):
                    return tag[1:]
                return tag
            return None
        except Exception:
            return None

    def check_base_image_update(
        self, config_path: str = "runners_config.yaml", auto_update: bool = False
    ) -> dict:
        """Vérifie si une mise à jour de l'image de base du runner GitHub est disponible."""
        config = self.config_service.load_config()
        defaults = getattr(config, "runners_defaults", None)
        base_image = getattr(defaults, "base_image", None) if defaults else None

        result: dict = {
            "current_version": None,
            "latest_version": None,
            "update_available": False,
            "updated": False,
            "error": None,
        }

        if not base_image:
            result["error"] = "No base_image found in runners_defaults"
            return result

        m = re.search(r":([\d.]+)$", base_image)
        result["current_version"] = m.group(1) if m else None

        latest_version = self.get_latest_runner_version()
        result["latest_version"] = latest_version

        if not latest_version:
            result["error"] = "Could not get latest version from GitHub API"
            return result

        if result["current_version"] == latest_version:
            return result

        result["update_available"] = True

        if auto_update:
            try:
                new_image = re.sub(r":([\d.]+)$", f":{latest_version}", base_image)

                with open(config_path, "r") as f:
                    lines = f.readlines()

                with open(config_path, "w") as f:
                    for line in lines:
                        if line.strip().startswith("base_image:"):
                            f.write(f"  base_image: {new_image}\n")
                        else:
                            f.write(line)

                result["updated"] = True
                result["new_image"] = new_image
            except Exception as e:
                result["error"] = str(e)

        return result
