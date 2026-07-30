from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from alarm_clock.macos import AlertPlayer, show_notification
from alarm_clock.models import Alarm
from alarm_clock.storage import AlarmStore

MAX_POLL_GAP_SECONDS = 5


class Scheduler:
    def __init__(
        self,
        store: AlarmStore | None = None,
        player: AlertPlayer | None = None,
        notifier: Callable[[str, str], None] = show_notification,
    ) -> None:
        self.store = store or AlarmStore()
        self.player = player or AlertPlayer()
        self.notifier = notifier
        self.ringing_ids: set[str] = set()
        self.last_tick: datetime | None = None

    def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        if self.last_tick is None:
            self._expire_missed(now)
            self.last_tick = now - timedelta(microseconds=1)
            return

        elapsed = (now - self.last_tick).total_seconds()
        if elapsed < 0 or elapsed > MAX_POLL_GAP_SECONDS:
            self._expire_missed(now)
            self.last_tick = now
            return

        alarms = self.store.load()
        potentially_due = [
            alarm
            for alarm in alarms
            if alarm.id not in self.ringing_ids
            and alarm.due_between(self.last_tick, now)
        ]
        if potentially_due:
            def confirm_due(items: list[Alarm]) -> list[Alarm]:
                confirmed = [
                    alarm
                    for alarm in items
                    if alarm.id not in self.ringing_ids
                    and alarm.due_between(self.last_tick, now)
                ]
                for alarm in confirmed:
                    if alarm.snoozed_until:
                        alarm.snoozed_until = None
                return confirmed

            due = self.store.update(confirm_due)
            if due:
                self._start_ringing(due)
        self.last_tick = now

    def stop(self, alarm_ids: list[str] | None = None) -> list[str]:
        selected = self._selected_ringing(alarm_ids)
        if not selected:
            return []

        def mark_stopped(alarms: list[Alarm]) -> None:
            for alarm in alarms:
                if alarm.id not in selected:
                    continue
                alarm.snoozed_until = None
                if alarm.kind == "once":
                    alarm.status = "completed"

        self.store.update(mark_stopped)
        self.ringing_ids.difference_update(selected)
        if not self.ringing_ids:
            self.player.stop()
        return sorted(selected)

    def snooze(
        self, alarm_ids: list[str] | None = None, now: datetime | None = None
    ) -> list[str]:
        selected = self._selected_ringing(alarm_ids)
        if not selected:
            return []
        now = now or datetime.now()

        def apply_snooze(alarms: list[Alarm]) -> None:
            for alarm in alarms:
                if alarm.id in selected:
                    alarm.snoozed_until = (
                        now + timedelta(minutes=alarm.snooze_minutes)
                    ).isoformat(timespec="seconds")

        self.store.update(apply_snooze)
        self.ringing_ids.difference_update(selected)
        if not self.ringing_ids:
            self.player.stop()
        return sorted(selected)

    def silence(self, alarm_ids: list[str] | None = None) -> list[str]:
        """Silence alarms without applying normal stop lifecycle changes."""
        selected = self._selected_ringing(alarm_ids)
        self.ringing_ids.difference_update(selected)
        if selected and not self.ringing_ids:
            self.player.stop()
        return sorted(selected)

    def shutdown(self) -> None:
        self.player.stop()

    def status(self) -> dict[str, object]:
        return {
            "ringing": bool(self.ringing_ids),
            "ringing_ids": sorted(self.ringing_ids),
        }

    def _selected_ringing(self, alarm_ids: list[str] | None) -> set[str]:
        requested = set(alarm_ids or [])
        return self.ringing_ids & requested if requested else set(self.ringing_ids)

    def _start_ringing(self, alarms: list[Alarm]) -> None:
        was_ringing = bool(self.ringing_ids)
        self.ringing_ids.update(alarm.id for alarm in alarms)
        if not was_ringing:
            names = ", ".join(alarm.name for alarm in alarms)
            self.notifier("Alarm", names)
            self.player.start()

    def _expire_missed(self, now: datetime) -> None:
        def expire(alarms: list[Alarm]) -> None:
            for alarm in alarms:
                if alarm.status != "active":
                    continue
                snoozed = alarm.snooze_datetime()
                if snoozed and snoozed < now:
                    alarm.snoozed_until = None
                    if alarm.kind == "once":
                        alarm.status = "completed"
                    continue
                if (
                    alarm.kind == "once"
                    and not alarm.snoozed_until
                    and alarm.scheduled_once() < now
                ):
                    alarm.status = "completed"

        self.store.update(expire)
