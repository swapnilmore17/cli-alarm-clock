from datetime import datetime
from pathlib import Path

from alarm_clock.models import Alarm
from alarm_clock.scheduler import Scheduler
from alarm_clock.storage import AlarmStore


class FakePlayer:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1


def recurring_alarm() -> Alarm:
    return Alarm(
        name="Wake up",
        kind="weekly",
        weekdays=[2],
        time="07:00",
        snooze_minutes=10,
    )


def test_scheduler_rings_and_stops(tmp_path: Path) -> None:
    store = AlarmStore(tmp_path)
    alarm = recurring_alarm()
    store.save([alarm])
    player = FakePlayer()
    notifications: list[tuple[str, str]] = []
    scheduler = Scheduler(
        store, player, lambda title, body: notifications.append((title, body))
    )

    scheduler.tick(datetime(2026, 7, 29, 6, 59, 59))
    scheduler.tick(datetime(2026, 7, 29, 7, 0, 1))
    assert scheduler.ringing_ids == {alarm.id}
    assert player.started == 1
    assert notifications == [("Alarm", "Wake up")]

    assert scheduler.stop() == [alarm.id]
    assert not scheduler.ringing_ids
    assert player.stopped == 1
    assert store.load()[0].status == "active"


def test_scheduler_fires_at_exact_startup_boundary(tmp_path: Path) -> None:
    store = AlarmStore(tmp_path)
    alarm = recurring_alarm()
    store.save([alarm])
    player = FakePlayer()
    scheduler = Scheduler(store, player, lambda *_: None)

    scheduler.tick(datetime(2026, 7, 29, 7, 0, 0))
    scheduler.tick(datetime(2026, 7, 29, 7, 0, 1))
    assert scheduler.ringing_ids == {alarm.id}
    assert player.started == 1


def test_snooze_uses_per_alarm_duration(tmp_path: Path) -> None:
    store = AlarmStore(tmp_path)
    alarm = recurring_alarm()
    store.save([alarm])
    scheduler = Scheduler(store, FakePlayer(), lambda *_: None)
    scheduler.ringing_ids.add(alarm.id)

    scheduler.snooze(now=datetime(2026, 7, 29, 7))
    saved = store.load()[0]
    assert saved.snoozed_until == "2026-07-29T07:10:00"
    assert scheduler.ringing_ids == set()


def test_stopping_one_time_alarm_completes_it(tmp_path: Path) -> None:
    store = AlarmStore(tmp_path)
    alarm = Alarm(
        name="Once",
        kind="once",
        date="2026-07-30",
        time="07:00",
        snooze_minutes=5,
    )
    store.save([alarm])
    scheduler = Scheduler(store, FakePlayer(), lambda *_: None)
    scheduler.ringing_ids.add(alarm.id)
    scheduler.stop()
    assert store.load()[0].status == "completed"


def test_silencing_one_time_alarm_does_not_complete_it(
    tmp_path: Path,
) -> None:
    store = AlarmStore(tmp_path)
    alarm = Alarm(
        name="Once",
        kind="once",
        date="2026-07-30",
        time="07:00",
        snooze_minutes=5,
    )
    store.save([alarm])
    scheduler = Scheduler(store, FakePlayer(), lambda *_: None)
    scheduler.ringing_ids.add(alarm.id)
    scheduler.silence()
    assert store.load()[0].status == "active"


def test_startup_skips_missed_one_time_alarm(tmp_path: Path) -> None:
    store = AlarmStore(tmp_path)
    alarm = Alarm(
        name="Missed",
        kind="once",
        date="2026-07-29",
        time="07:00",
        snooze_minutes=5,
    )
    store.save([alarm])
    scheduler = Scheduler(store, FakePlayer(), lambda *_: None)
    scheduler.tick(datetime(2026, 7, 29, 8))
    assert store.load()[0].status == "completed"
    assert not scheduler.ringing_ids


def test_large_poll_gap_skips_occurrence(tmp_path: Path) -> None:
    store = AlarmStore(tmp_path)
    alarm = recurring_alarm()
    store.save([alarm])
    player = FakePlayer()
    scheduler = Scheduler(store, player, lambda *_: None)
    scheduler.tick(datetime(2026, 7, 29, 6, 59))
    scheduler.tick(datetime(2026, 7, 29, 7, 10))
    assert not scheduler.ringing_ids
    assert player.started == 0
