
# Scheduler – GitHub Runner Manager

This document explains the configuration and operation of the scheduler integrated into GitHub Runner Manager.

## General Operation

The scheduler automates actions (check, build, etc.) on runners according to a flexible schedule defined in the configuration file (`runners_config.yaml`).

- **Interval**: Periodic trigger (seconds, minutes, hours)
- **Time window**: Allowed time range for execution
- **Days**: Days of the week when the scheduler is active
- **Actions**: List of actions to execute (e.g., `check`, `build`, `deploy`)
- **Maximum retries**: Automatic stop after X consecutive failures

## Example configuration (`runners_config.yaml`)

## Starting and configuring the scheduler

Since the Supervisor version, the scheduler is automatically started in the container via supervisord. It is no longer necessary to configure `scheduler.enabled` in the configuration file.

The scheduler starts automatically if the container is launched without arguments, thanks to the entrypoint and supervisord configuration.

Example of starting the scheduler via Docker:

```bash
docker run --rm -d \
   -v /var/run/docker.sock:/var/run/docker.sock \
   -v $(pwd)/runners_config.yaml:/app/runners_config.yaml \
   -v $(pwd)/config:/app/config:ro \
   a/github-runner-manager
```

## Example configuration (`runners_config.yaml`)

```yaml
scheduler:
  check_interval: "30m"         # Interval between two executions (e.g.: 30s, 10m, 1h)
  time_window: "08:00-20:00"    # Allowed time window (HH:MM-HH:MM)
  days: [mon, tue, wed, thu, fri] # Allowed days (mon, tue, ...)
  actions: [check, build, deploy] # Actions to execute (deploy = auto start runners after build)
  max_retries: 3                 # Maximum number of retries in case of failure
```

## Parameter details

- **check_interval**: Format `<number><unit>` (e.g.: `30s`, `10m`, `1h`). Units:
   - `s`: seconds
   - `m`: minutes
   - `h`: hours
- **time_window**: Allowed execution time window (e.g.: `08:00-20:00`)
- **days**: List of allowed days (`mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`)
- **actions**:
   - `check`: Checks if a new version of the base image is available
   - `build`: Rebuilds runner images if an update is detected (and updates config if needed)
   - `deploy`: If present with `build`, and at least one image has been rebuilt, automatically starts/restarts runners without interaction.
- **max_retries**: Maximum number of consecutive retries before automatic stop

## Detailed operation

1. **Loading configuration**:
   - Parameters are validated (syntax, allowed values).
2. **Scheduling**:
   - The scheduler uses the Python library [`schedule`](https://schedule.readthedocs.io/) to schedule tasks.
   - The interval (`check_interval`) and days (`days`) are combined to define the execution frequency.
   - The time window (`time_window`) limits execution to allowed hours.
3. **Execution**:
   - At each trigger, the scheduler checks the time window and executes the configured actions.
   - In case of failure, the retry counter is incremented. If the maximum is reached, the scheduler stops.

## Best practices

- Use reasonable intervals to avoid excessive load.
- Prefer time windows adapted to your needs (e.g.: business hours).
- Monitor logs to detect repeated failures.

## Dependencies

- [schedule](https://pypi.org/project/schedule/): Python scheduling library

---

For any questions or suggestions, open an issue on the project's GitHub repository.
