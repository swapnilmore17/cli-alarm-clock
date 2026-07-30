from __future__ import annotations

import argparse
import sys
from datetime import datetime

from alarm_clock import service
from alarm_clock.models import Alarm
from alarm_clock.runtime import DaemonUnavailable, send_command
from alarm_clock.storage import AlarmStore, resolve_alarm
from alarm_clock.time_utils import (
    WEEKDAY_NAMES,
    format_countdown,
    format_weekdays,
    parse_weekdays,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alarm", description="Create and manage local macOS alarms."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create an alarm.")
    create.add_argument("--name")
    create.add_argument("--time", metavar="HH:MM")
    schedule = create.add_mutually_exclusive_group()
    schedule.add_argument("--date", metavar="YYYY-MM-DD")
    schedule.add_argument(
        "--weekdays", help="Comma-separated days, daily, weekdays, or weekends."
    )
    create.add_argument("--snooze", type=int, metavar="MINUTES")

    view = commands.add_parser("view", help="List alarms or show one alarm.")
    view.add_argument("identifier", nargs="?")

    edit = commands.add_parser("edit", help="Edit an alarm.")
    edit.add_argument("identifier")
    edit.add_argument("--name")
    edit.add_argument("--time", metavar="HH:MM")
    edit_schedule = edit.add_mutually_exclusive_group()
    edit_schedule.add_argument("--date", metavar="YYYY-MM-DD")
    edit_schedule.add_argument("--weekdays")
    edit.add_argument("--snooze", type=int, metavar="MINUTES")

    for command, help_text in (
        ("delete", "Delete an alarm immediately."),
        ("pause", "Pause an alarm indefinitely."),
        ("resume", "Resume a paused alarm."),
    ):
        action = commands.add_parser(command, help=help_text)
        action.add_argument("identifier")

    stop = commands.add_parser("stop", help="Stop ringing alarms.")
    stop.add_argument("identifier", nargs="?")
    snooze = commands.add_parser("snooze", help="Snooze ringing alarms.")
    snooze.add_argument("identifier", nargs="?")

    service_parser = commands.add_parser(
        "service", help="Manage the background scheduler."
    )
    service_parser.add_argument(
        "action",
        choices=("install", "uninstall", "start", "stop", "restart", "status"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        arguments = parser.parse_args(argv)
        return dispatch(arguments)
    except (ValueError, RuntimeError, DaemonUnavailable) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        return 130


def dispatch(arguments: argparse.Namespace) -> int:
    handlers = {
        "create": create_alarm,
        "view": view_alarms,
        "edit": edit_alarm,
        "delete": delete_alarm,
        "pause": pause_alarm,
        "resume": resume_alarm,
        "stop": stop_alarm,
        "snooze": snooze_alarm,
        "service": manage_service,
    }
    return handlers[arguments.command](arguments)


def create_alarm(arguments: argparse.Namespace) -> int:
    name = arguments.name or _prompt("Name")
    clock_time = arguments.time or _prompt("Time (HH:MM)")
    schedule_date = arguments.date
    weekdays_value = arguments.weekdays
    if not schedule_date and not weekdays_value:
        kind = _prompt("Schedule type (once/weekly)", "once").lower()
        if kind == "once":
            schedule_date = _prompt("Date (YYYY-MM-DD)")
        elif kind == "weekly":
            weekdays_value = _prompt(
                "Weekdays (for example mon,wed,fri or daily)"
            )
        else:
            raise ValueError("Schedule type must be 'once' or 'weekly'.")
    snooze_minutes = arguments.snooze
    if snooze_minutes is None:
        snooze_minutes = _prompt_int("Snooze minutes", 10)

    alarm = Alarm(
        name=name,
        kind="once" if schedule_date else "weekly",
        time=clock_time,
        date=schedule_date,
        weekdays=parse_weekdays(weekdays_value) if weekdays_value else [],
        snooze_minutes=snooze_minutes,
    )
    now = datetime.now()
    next_fire = alarm.next_occurrence(now)
    if alarm.kind == "once" and (not next_fire or next_fire <= now):
        raise ValueError("A one-time alarm must be scheduled in the future.")

    AlarmStore().update(lambda alarms: alarms.append(alarm))
    send_command("refresh", required=False)
    assert next_fire is not None
    print(
        f"Created '{alarm.name}' [{alarm.id[:8]}]. "
        f"Alarm set for {format_countdown(next_fire, now)} from now."
    )
    return 0


def view_alarms(arguments: argparse.Namespace) -> int:
    alarms = AlarmStore().load()
    if arguments.identifier:
        _print_alarm(resolve_alarm(alarms, arguments.identifier))
        return 0
    if not alarms:
        print("No alarms.")
        return 0

    now = datetime.now()
    print(f"{'ID':8}  {'NAME':20}  {'SCHEDULE':24}  {'STATUS':9}  NEXT")
    for alarm in alarms:
        next_fire = alarm.next_occurrence(now)
        next_text = (
            f"{next_fire:%Y-%m-%d %H:%M} ({format_countdown(next_fire, now)})"
            if next_fire
            else "-"
        )
        print(
            f"{alarm.id[:8]:8}  {alarm.name[:20]:20}  "
            f"{_schedule_text(alarm)[:24]:24}  {alarm.status:9}  {next_text}"
        )
    return 0


def edit_alarm(arguments: argparse.Namespace) -> int:
    store = AlarmStore()
    current = resolve_alarm(store.load(), arguments.identifier)
    send_command("silence", [current.id], required=False)
    interactive = all(
        value is None
        for value in (
            arguments.name,
            arguments.time,
            arguments.date,
            arguments.weekdays,
            arguments.snooze,
        )
    )

    def apply(alarms: list[Alarm]) -> Alarm:
        alarm = resolve_alarm(alarms, current.id)
        old_schedule = (alarm.kind, alarm.date, tuple(alarm.weekdays), alarm.time)
        if interactive:
            alarm.name = _prompt("Name", alarm.name)
            alarm.time = _prompt("Time (HH:MM)", alarm.time)
            alarm.snooze_minutes = _prompt_int(
                "Snooze minutes", alarm.snooze_minutes
            )
            kind = _prompt("Schedule type (once/weekly)", alarm.kind).lower()
            if kind == "once":
                default_date = alarm.date or datetime.now().date().isoformat()
                alarm.kind = "once"
                alarm.date = _prompt("Date (YYYY-MM-DD)", default_date)
                alarm.weekdays = []
            elif kind == "weekly":
                default_days = (
                    ",".join(WEEKDAY_NAMES[day][:3].lower() for day in alarm.weekdays)
                    or "weekdays"
                )
                alarm.kind = "weekly"
                alarm.date = None
                alarm.weekdays = parse_weekdays(
                    _prompt("Weekdays", default_days)
                )
            else:
                raise ValueError("Schedule type must be 'once' or 'weekly'.")
        else:
            if arguments.name is not None:
                alarm.name = arguments.name
            if arguments.time is not None:
                alarm.time = arguments.time
            if arguments.snooze is not None:
                alarm.snooze_minutes = arguments.snooze
            if arguments.date is not None:
                alarm.kind = "once"
                alarm.date = arguments.date
                alarm.weekdays = []
            elif arguments.weekdays is not None:
                alarm.kind = "weekly"
                alarm.date = None
                alarm.weekdays = parse_weekdays(arguments.weekdays)
        alarm.validate()
        new_schedule = (alarm.kind, alarm.date, tuple(alarm.weekdays), alarm.time)
        if old_schedule != new_schedule:
            alarm.snoozed_until = None
        if alarm.status == "completed" and old_schedule != new_schedule:
            alarm.status = "active"
        if (
            alarm.kind == "once"
            and alarm.status == "active"
            and alarm.scheduled_once() <= datetime.now()
        ):
            raise ValueError("An active one-time alarm must be in the future.")
        return alarm

    updated = store.update(apply)
    send_command("refresh", required=False)
    print(f"Updated '{updated.name}' [{updated.id[:8]}].")
    return 0


def delete_alarm(arguments: argparse.Namespace) -> int:
    store = AlarmStore()
    target = resolve_alarm(store.load(), arguments.identifier)
    send_command("silence", [target.id], required=False)

    def remove(alarms: list[Alarm]) -> None:
        alarm = resolve_alarm(alarms, target.id)
        alarms.remove(alarm)

    store.update(remove)
    print(f"Deleted '{target.name}' [{target.id[:8]}].")
    return 0


def pause_alarm(arguments: argparse.Namespace) -> int:
    store = AlarmStore()
    target = resolve_alarm(store.load(), arguments.identifier)
    send_command("silence", [target.id], required=False)

    def pause(alarms: list[Alarm]) -> Alarm:
        alarm = resolve_alarm(alarms, target.id)
        alarm.status = "paused"
        alarm.snoozed_until = None
        return alarm

    paused = store.update(pause)
    print(f"Paused '{paused.name}' [{paused.id[:8]}].")
    return 0


def resume_alarm(arguments: argparse.Namespace) -> int:
    store = AlarmStore()

    def resume(alarms: list[Alarm]) -> Alarm:
        alarm = resolve_alarm(alarms, arguments.identifier)
        if alarm.status != "paused":
            raise ValueError("Only a paused alarm can be resumed.")
        if alarm.kind == "once" and alarm.scheduled_once() <= datetime.now():
            raise ValueError(
                "Edit this one-time alarm to a future date/time before resuming."
            )
        alarm.status = "active"
        return alarm

    resumed = store.update(resume)
    send_command("refresh", required=False)
    print(f"Resumed '{resumed.name}' [{resumed.id[:8]}].")
    return 0


def stop_alarm(arguments: argparse.Namespace) -> int:
    identifiers = _runtime_ids(arguments.identifier)
    response = send_command("stop", identifiers)
    affected = response.get("affected", [])
    print(
        f"Stopped {len(affected)} alarm(s)."
        if affected
        else "No matching alarms are ringing."
    )
    return 0


def snooze_alarm(arguments: argparse.Namespace) -> int:
    identifiers = _runtime_ids(arguments.identifier)
    response = send_command("snooze", identifiers)
    affected = response.get("affected", [])
    print(
        f"Snoozed {len(affected)} alarm(s)."
        if affected
        else "No matching alarms are ringing."
    )
    return 0


def manage_service(arguments: argparse.Namespace) -> int:
    action = arguments.action
    if action == "install":
        service.install()
        print("Background service installed and started.")
    elif action == "uninstall":
        service.uninstall()
        print("Background service uninstalled.")
    elif action == "start":
        service.start()
        print("Background service started.")
    elif action == "stop":
        service.stop()
        print("Background service stopped.")
    elif action == "restart":
        service.restart()
        print("Background service restarted.")
    else:
        print(f"Background service: {service.status()}.")
    return 0


def _runtime_ids(identifier: str | None) -> list[str]:
    if identifier is None:
        return []
    return [resolve_alarm(AlarmStore().load(), identifier).id]


def _print_alarm(alarm: Alarm) -> None:
    next_fire = alarm.next_occurrence()
    print(f"ID:       {alarm.id}")
    print(f"Name:     {alarm.name}")
    print(f"Schedule: {_schedule_text(alarm)}")
    print(f"Status:   {alarm.status}")
    print(f"Snooze:   {alarm.snooze_minutes} minutes")
    if next_fire:
        print(f"Next:     {next_fire:%Y-%m-%d %H:%M}")
        print(f"From now: {format_countdown(next_fire)}")
    else:
        print("Next:     -")


def _schedule_text(alarm: Alarm) -> str:
    if alarm.kind == "once":
        return f"{alarm.date} at {alarm.time}"
    return f"{format_weekdays(alarm.weekdays)} at {alarm.time}"


def _prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    raise ValueError(f"{label} is required.")


def _prompt_int(label: str, default: int) -> int:
    value = _prompt(label, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer.") from exc
