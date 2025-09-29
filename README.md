# GitHub Runner Manager

![Banner](./docs/assets/logo.webp)

[![Workflow State](https://github.com/glefer/github-runner-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/glefer/github-runner-manager/actions/workflows/main.yml)  
[![codecov](https://codecov.io/gh/glefer/github-runner-manager/branch/main/graph/badge.svg?token=JRjmc0emjT)](https://codecov.io/gh/glefer/github-runner-manager)  
![Python](https://img.shields.io/badge/python-3.13-blue)  
[![Docker](https://img.shields.io/docker/pulls/glefer/github-runner-manager)](https://hub.docker.com/r/glefer/github-runner-manager)

A Python application to easily manage your GitHub runners from any server or locally.  
![Output](./docs/assets/output.webp)

---

## 🚀 Getting Started

### Requirements
* Python 3.13+
* Poetry

### Installation

1. Clone:
```bash
git clone https://github.com/glefer/github-runner-manager
cd github-runner-manager
cp runners_config.yaml.dist runners_config.yaml
cp .env.example .env 
# fill the GITHUB_TOKEN with your API token (see: Configuration (.env and runners_config.yaml) section below)
```

2. Install:
```bash
poetry install
```

3. Help:
```bash
poetry run python main.py --help
```

---

## 📋 Commands

```bash
python main.py build-runners-images    # Build Docker runner images
python main.py start-runners           # Start Docker runners
python main.py stop-runners            # Stop Docker runners
python main.py remove-runners          # Remove Docker runners
python main.py check-base-image-update # Check for base image updates
python main.py list-runners            # List Docker runners
```

---

## ⏰ Scheduler

The scheduler automates runner actions (checks, builds, etc.) based on flexible planning defined in `runners_config.yaml`.

It is automatically started in the container via Supervisor. No manual activation/deactivation is required.

For more details, see: [docs/scheduler.md](./docs/scheduler.md)

---

## Configuration (.env and runners_config.yaml)

As of September 2025, GitHub runner management uses a **GitHub personal token** (`admin:org`, `repo` scopes) to dynamically generate a registration token.


Minimal `.env` example:
```dotenv
GITHUB_TOKEN=ghp_................................
```


**Security:**
- Never share your personal token
- Prefer tokens restricted to org/repo scope

---

### Webhooks (notifications)

GitHub Runner Manager supports sending notifications via webhooks to keep you informed of important events like runner start/stop, image builds, or available updates.

![webhook](./docs/assets/webhook.webp)

Example configuration (`runners_config.yaml`):
```yaml
webhooks:
  enabled: true
  timeout: 10
  retry_count: 3
  retry_delay: 5

  # Slack configuration
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
    username: "GitHub Runner Bot"
    events:
      - runner_started
      - runner_error
      - build_completed
      - update_available
```

**Supported events include:**
- `runner_started`
- `runner_stopped`
- `runner_removed`
- `runner_error`
- `runner_skipped`
- `build_started`
- `build_completed`
- `build_failed`
- `image_updated`
- `update_available`
- `update_applied`
- `update_error`

**Supported providers:**
- Slack
- Discord
- Microsoft Teams
- Generic webhooks

**Testing webhooks:**
```bash
# Test a specific event
python main.py webhook test --event runner_started --provider slack

# Test all configured events
python main.py webhook test-all --provider slack
```

---

## Example Runner Configuration

A sample `runners_config.yaml.dist` file is provided. Copy it to start your own configuration:

```bash
cp runners_config.yaml.dist runners_config.yaml
```

Example runner definition:
```yaml
runners:
  - id: sample
    name_prefix: my-runner-sample
    labels: [my-runner-set-sample, sample]
    nb: 2
    build_image: ./config/Dockerfile.sample
    techno: php
    techno_version: 8.3
```

Simplified example:
```yaml
runners:
  - name: runner-1
    image: ghcr.io/actions/runner:latest
    labels: [linux, docker]
```

The project includes a config schema (`src/services/config_schema.py`) validated with Pydantic.

---

## CLI Commands

The CLI (powered by Typer) is documented via `--help`:

```bash
poetry run python main.py --help
```

Common commands:
- `list-runners` – list runners
- `start-runners` – start runners
- `stop-runners` – stop runners
- `remove-runners` – remove runners
- `check-base-image-update` – check if base images have updates

---

## Usage in Docker Container

A `Dockerfile` is provided for building a custom image.

### Entrypoint
- `server` → runs the scheduler via Supervisor
- `<CLI command>` → runs a Python CLI command
- No argument → prints help/usage

### Example build and run
```bash
# Build
docker build -t github-runner-manager .

# Run scheduler
docker run --rm -it   -v /var/run/docker.sock:/var/run/docker.sock   -v $(pwd)/runners_config.yaml:/app/runners_config.yaml   -v $(pwd)/config:/app/config:ro   github-runner-manager server

# Run CLI (example: list runners)
docker run --rm -it   -v /var/run/docker.sock:/var/run/docker.sock   -v $(pwd)/runners_config.yaml:/app/runners_config.yaml   -v $(pwd)/config:/app/config:ro   github-runner-manager list-runners
```

⚠️ Mounting the Docker socket gives full access to Docker on the host. Use only in trusted environments.

---
