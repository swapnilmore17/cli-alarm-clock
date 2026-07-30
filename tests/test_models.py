from datetime import datetime

import pytest

from alarm_clock.models import Alarm
from alarm_clock.time_utils import (
    format_countdown,
    format_weekdays,
    parse_weekdays,
)


def test_one_time_next_occurrence() -> None:
    alarm = Alarm(
        name="Appointment",
        kind="once",
        date="2026-07-30",
        time="09:15",
        snooze_minutes=10,
    )
    assert alarm.next_occurrence(datetime(2026, 7, 29, 12)) == datetime(
        2026, 7, 30, 9, 15
    )
    assert alarm.next_occurrence(datetime(2026, 7, 30, 9, 16)) is None


def test_weekly_next_occurrence_wraps_week() -> None:
    alarm = Alarm(
        name="Standup",
        kind="weekly",
        weekdays=[0, 2],
        time="09:00",
        snooze_minutes=5,
    )
    assert alarm.next_occurrence(datetime(2026, 7, 29, 9, 1)) == datetime(
        2026, 8, 3, 9
    )


def test_due_between_handles_poll_interval() -> None:
    alarm = Alarm(
        name="Standup",
        kind="weekly",
        weekdays=[2],
        time="09:00",
        snooze_minutes=5,
    )
    assert alarm.due_between(
        datetime(2026, 7, 29, 8, 59, 59),
        datetime(2026, 7, 29, 9, 0, 1),
    )


def test_snoozed_weekly_alarm_suppresses_regular_occurrence() -> None:
    alarm = Alarm(
        name="Standup",
        kind="weekly",
        weekdays=[2],
        time="09:00",
        snooze_minutes=10,
        snoozed_until="2026-07-29T09:10:00",
    )
    assert not alarm.due_between(
        datetime(2026, 7, 29, 8, 59, 59),
        datetime(2026, 7, 29, 9, 0, 1),
    )
    assert alarm.due_between(
        datetime(2026, 7, 29, 9, 9, 59),
        datetime(2026, 7, 29, 9, 10, 1),
    )


def test_paused_alarm_has_no_next_occurrence() -> None:
    alarm = Alarm(
        name="Paused",
        kind="weekly",
        weekdays=[0],
        time="09:00",
        snooze_minutes=5,
        status="paused",
    )
    assert alarm.next_occurrence(datetime(2026, 7, 27, 8)) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("weekdays", [0, 1, 2, 3, 4]),
        ("weekends", [5, 6]),
        ("daily", list(range(7))),
        ("mon,wed,fri", [0, 2, 4]),
    ],
)
def test_parse_weekdays(value: str, expected: list[int]) -> None:
    assert parse_weekdays(value) == expected


def test_weekday_format_presets() -> None:
    assert format_weekdays(list(range(5))) == "Weekdays"
    assert format_weekdays([5, 6]) == "Weekends"


def test_countdown_format() -> None:
    assert (
        format_countdown(
            datetime(2026, 7, 30, 14, 15),
            datetime(2026, 7, 29, 12),
        )
        == "1 day 2 hours 15 minutes"
    )


def test_rejects_invalid_alarm() -> None:
    with pytest.raises(ValueError, match="24-hour"):
        Alarm(
            name="Bad",
            kind="once",
            date="2026-07-30",
            time="25:00",
            snooze_minutes=10,
        )
