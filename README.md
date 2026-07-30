# CLI Alarm Clock

A minimal Python 3.11+ alarm clock for macOS. It has no web UI or database,
uses a local JSON file, and runs its scheduler as a per-user launchd service.
The application has no third-party runtime dependencies.

## Setup

Keep the project in a stable location because the launchd service records the
virtual environment's absolute Python path.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
alarm service install
```

`alarm service install` starts the scheduler immediately and configures it to
start at login. Run `alarm service uninstall` before moving the project or
deleting `.venv`.

## Commands

Create a one-time alarm:

```sh
alarm create --name "Dentist" --date 2026-08-03 --time 09:30 --snooze 10
```

Create a recurring alarm:

```sh
alarm create --name "Wake up" --weekdays weekdays --time 07:00 --snooze 10
alarm create --name "Gym" --weekdays mon,wed,fri --time 18:30 --snooze 5
```

Omit create options to be prompted interactively. Times use 24-hour `HH:MM`
format and dates use `YYYY-MM-DD`.

```sh
alarm view
alarm view "Wake up"
alarm edit "Wake up"
alarm edit "Wake up" --time 07:30
alarm pause "Wake up"
alarm resume "Wake up"
alarm delete "Wake up"
```

Each alarm has a stable ID. A unique name or unambiguous ID prefix can be used
with commands. If names are duplicated, use the ID shown by `alarm view`.

When alarms ring, open another terminal and run:

```sh
alarm stop
alarm snooze
```

If several alarms ring together, these commands affect the whole ringing
session. Pass an ID or unique name to target one alarm. Snooze always uses each
alarm's configured duration.

Manage the background process with:

```sh
alarm service status
alarm service start
alarm service stop
alarm service restart
alarm service uninstall
```

## Behavior

- Weekly schedules support any weekday combination plus `daily`, `weekdays`,
  and `weekends`.
- Pausing disables an alarm until it is resumed.
- One-time alarms remain visible as `completed` after being stopped.
- A paused one-time alarm whose date has passed must be edited before resume.
- Alarms missed while the Mac is asleep or the service is stopped are skipped.
- The bundled `assets/alarm.wav` loops until stop or snooze. It is generated
  by `tools/generate_alarm_sound.py` and does not depend on a system sound.
- One desktop notification is shown when a ringing session begins. macOS may
  ask for notification permission for the terminal or Python process.

The scheduler uses `afplay` and `osascript`, so this release supports macOS
only.

## Local files

- Alarms: `~/Library/Application Support/Alarm Clock/alarms.json`
- Runtime socket/lock: `~/Library/Application Support/Alarm Clock/`
- Logs: `~/Library/Caches/Alarm Clock/`
- Launch agent: `~/Library/LaunchAgents/com.local.cli-alarm-clock.plist`

Alarm writes are process-locked and atomically replaced. Avoid editing the JSON
file while the service is running.

## Development

```sh
source .venv/bin/activate
pytest
python -m compileall -q src tests
python -m alarm_clock --help
```

Regenerate the bundled sound with:

```sh
python tools/generate_alarm_sound.py
```
