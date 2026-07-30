from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Literal
from uuid import uuid4

ScheduleKind = Literal["once", "weekly"]
AlarmStatus = Literal["active", "paused", "completed"]


@dataclass(slots=True)
class Alarm:
    name: str
    kind: ScheduleKind
    time: str
    snooze_minutes: int
    id: str = field(default_factory=lambda: uuid4().hex)
    date: str | None = None
    weekdays: list[int] = field(default_factory=list)
    status: AlarmStatus = "active"
    snoozed_until: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Alarm name cannot be empty.")
        if self.kind not in {"once", "weekly"}:
            raise ValueError("Schedule kind must be 'once' or 'weekly'.")
        parse_clock_time(self.time)
        if self.snooze_minutes < 1:
            raise ValueError("Snooze duration must be at least 1 minute.")
        if self.status not in {"active", "paused", "completed"}:
            raise ValueError(f"Invalid alarm status: {self.status}")
        if self.kind == "once":
            if not self.date:
                raise ValueError("A one-time alarm requires a date.")
            parse_date(self.date)
            if self.weekdays:
                raise ValueError("A one-time alarm cannot have weekdays.")
        else:
            if self.date:
                raise ValueError("A weekly alarm cannot have a date.")
            if not self.weekdays:
                raise ValueError("A weekly alarm requires at least one weekday.")
            if any(day not in range(7) for day in self.weekdays):
                raise ValueError("Weekdays must be integers from 0 to 6.")
            self.weekdays = sorted(set(self.weekdays))
        if self.snoozed_until:
            datetime.fromisoformat(self.snoozed_until)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alarm:
        return cls(**data)

    def scheduled_once(self) -> datetime:
        if self.kind != "once" or self.date is None:
            raise ValueError("Alarm is not a one-time alarm.")
        return datetime.combine(parse_date(self.date), parse_clock_time(self.time))

    def snooze_datetime(self) -> datetime | None:
        return (
            datetime.fromisoformat(self.snoozed_until)
            if self.snoozed_until
            else None
        )

    def next_occurrence(self, now: datetime | None = None) -> datetime | None:
        now = now or datetime.now()
        if self.status != "active":
            return None

        snoozed = self.snooze_datetime()
        candidates: list[datetime] = []
        if snoozed and snoozed >= now:
            candidates.append(snoozed)

        if self.kind == "once":
            scheduled = self.scheduled_once()
            if scheduled >= now and not self.snoozed_until:
                candidates.append(scheduled)
        else:
            clock = parse_clock_time(self.time)
            for offset in range(8):
                candidate_date = now.date() + timedelta(days=offset)
                if candidate_date.weekday() not in self.weekdays:
                    continue
                candidate = datetime.combine(candidate_date, clock)
                if candidate >= now:
                    candidates.append(candidate)
                    break

        return min(candidates) if candidates else None

    def due_between(self, start: datetime, end: datetime) -> bool:
        """Return whether an occurrence is in the half-open interval (start, end]."""
        if self.status != "active":
            return False

        snoozed = self.snooze_datetime()
        if snoozed:
            return start < snoozed <= end

        if self.kind == "once":
            return (
                start < self.scheduled_once() <= end
            )

        clock = parse_clock_time(self.time)
        current = start.date()
        while current <= end.date():
            candidate = datetime.combine(current, clock)
            if current.weekday() in self.weekdays and start < candidate <= end:
                return True
            current += timedelta(days=1)
        return False


def parse_clock_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Time must use 24-hour HH:MM format.") from exc


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD format.") from exc
