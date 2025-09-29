# GitHub Runner Manager Application Workflow Documentation

## General Overview

The application allows dynamic management of self-hosted GitHub runners via a command-line interface (CLI). It facilitates deployment, management, configuration, and monitoring of runners in Docker environments, with support for different languages and versions (Node, PHP, etc.).

## Main Features

- **Runner Deployment**: Create and start new runners according to the YAML configuration.
- **Stop and Remove**: Stop, remove, or clean up existing runners.
- **Image Update**: Check and update the base Docker images used by runners.
- **List and Status**: Display the list of runners, their state, and detailed information.
- **Multi-language Support**: Manage runners for different environments (Node, PHP, etc.) via dedicated Dockerfiles.
- **Centralized Configuration**: Use a `runners_config.yaml` file to describe the runners to manage.

## Possible Runner States

A runner can be in one of the following states:

- **created**: The runner is configured but not yet started.
- **started**: The runner is active and ready to execute GitHub Actions jobs.
- **running**: The runner is currently executing a job.
- **stopped**: The runner is stopped (Docker container stopped).
- **removed**: The runner and its container have been deleted.
- **error**: An error occurred during an operation (start, stop, remove, etc.).

## Typical Workflows

### 1. Deploying a New Runner

```ascii
  +---------------------+
  | runners_config.yaml |
  +----------+----------+
          |
          v
  +---------------------+
  |  CLI Command        |
  |  (deploy/start)     |
  +----------+----------+
          |
          v
  +---------------------+
  |  Runner "created"   |
  +----------+----------+
          |
          v
  +---------------------+
  |  Runner "started"   |
  +---------------------+
```

### 2. Stopping a Runner

```ascii
  +---------------------+
  | Runner "started"    |
  +----------+----------+
          |
          v
  +---------------------+
  | CLI Command stop    |
  +----------+----------+
          |
          v
  +---------------------+
  | Runner "stopped"    |
  +---------------------+
```

### 3. Removing a Runner

```ascii
  +---------------------+
  | Runner "stopped"    |
  +----------+----------+
          |
          v
  +---------------------+
  | CLI Command remove  |
  +----------+----------+
          |
          v
  +---------------------+
  | Runner "removed"    |
  +---------------------+
```

### 4. Updating a Base Image

```ascii
        +-----------------------------+
        | CLI Command check/update    |
        +-------------+---------------+
                                                |
                                                v
        +-----------------------------+
        | New image available?        |
        +-------------+---------------+
                                         Yes / No
                                         /       \
                                        v         v
        [Update]      [No action]
                        |
                        v
        +-----------------------------+
        | Redeploy related runners     |
        +-----------------------------+
```

## CLI Command Examples

- `python main.py list`: Lists all runners and their state.
- `python main.py start <runner>`: Starts a specific runner.
- `python main.py stop <runner>`: Stops a specific runner.
- `python main.py remove <runner>`: Removes a specific runner.
- `python main.py check-base-image-update`: Checks for updates to base Docker images.

## Technical Architecture

- **Configuration File**: `runners_config.yaml` describes the runners to manage.
- **Services**:
        - `config_service.py`: Configuration management.
        - `docker_service.py`: Docker container management.
- **CLI**: User interface to control the application.

---

For more details, see the rest of the documentation or the source code.
