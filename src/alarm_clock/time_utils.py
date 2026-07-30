from __future__ import annotations

import math
from datetime import datetime

WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

_ALIASES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def parse_weekdays(value: str) -> list[int]:
    normalized = value.strip().lower()
    presets = {
        "daily": list(range(7)),
        "everyday": list(range(7)),
        "weekdays": list(range(5)),
        "weekends": [5, 6],
    }
    if normalized in presets:
        return presets[normalized]

    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if not parts:
        raise ValueError("Enter weekdays such as mon,wed,fri or a preset.")
    try:
        return sorted({_ALIASES[part] for part in parts})
    except KeyError as exc:
        raise ValueError(f"Unknown weekday: {exc.args[0]}") from exc


def format_weekdays(days: list[int]) -> str:
    if days == list(range(7)):
        return "Daily"
    if days == list(range(5)):
        return "Weekdays"
    if days == [5, 6]:
        return "Weekends"
    return ", ".join(WEEKDAY_NAMES[day][:3] for day in days)


def format_countdown(target: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    total_seconds = max(0, math.ceil((target - now).total_seconds()))
    if total_seconds < 60:
        return _unit(total_seconds, "second")

    total_minutes = math.ceil(total_seconds / 60)
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(_unit(days, "day"))
    if hours:
        parts.append(_unit(hours, "hour"))
    if minutes:
        parts.append(_unit(minutes, "minute"))
    return " ".join(parts)


def _unit(value: int, name: str) -> str:
    return f"{value} {name}{'' if value == 1 else 's'}"
