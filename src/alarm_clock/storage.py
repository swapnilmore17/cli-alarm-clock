from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from alarm_clock.models import Alarm

SCHEMA_VERSION = 1
T = TypeVar("T")


def data_directory() -> Path:
    override = os.environ.get("ALARM_CLOCK_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Application Support" / "Alarm Clock"


def cache_directory() -> Path:
    override = os.environ.get("ALARM_CLOCK_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Caches" / "Alarm Clock"


def socket_path() -> Path:
    return data_directory() / "daemon.sock"


def daemon_lock_path() -> Path:
    return data_directory() / "daemon.lock"


class AlarmStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or data_directory()
        self.path = self.directory / "alarms.json"
        self.lock_path = self.directory / "alarms.lock"

    def load(self) -> list[Alarm]:
        self._ensure_directory()
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            return self._read_unlocked()

    def save(self, alarms: list[Alarm]) -> None:
        self._ensure_directory()
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._write_unlocked(alarms)

    def update(self, operation: Callable[[list[Alarm]], T]) -> T:
        self._ensure_directory()
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            alarms = self._read_unlocked()
            result = operation(alarms)
            self._write_unlocked(alarms)
            return result

    def _ensure_directory(self) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _read_unlocked(self) -> list[Alarm]:
        if not self.path.exists():
            return []
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot read alarm data: {exc}") from exc
        if document.get("version") != SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported alarm data version: {document.get('version')}"
            )
        try:
            return [Alarm.from_dict(item) for item in document.get("alarms", [])]
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid alarm data: {exc}") from exc

    def _write_unlocked(self, alarms: list[Alarm]) -> None:
        document = {
            "version": SCHEMA_VERSION,
            "alarms": [alarm.to_dict() for alarm in alarms],
        }
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.directory, prefix=".alarms-", suffix=".json"
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(document, output, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


def resolve_alarm(alarms: list[Alarm], identifier: str) -> Alarm:
    exact_id = [alarm for alarm in alarms if alarm.id == identifier]
    if exact_id:
        return exact_id[0]

    id_prefix = [alarm for alarm in alarms if alarm.id.startswith(identifier)]
    if len(id_prefix) == 1:
        return id_prefix[0]
    if len(id_prefix) > 1:
        raise ValueError(f"Alarm ID prefix '{identifier}' is ambiguous.")

    by_name = [
        alarm for alarm in alarms if alarm.name.casefold() == identifier.casefold()
    ]
    if len(by_name) == 1:
        return by_name[0]
    if len(by_name) > 1:
        raise ValueError(
            f"Alarm name '{identifier}' is ambiguous; use the displayed ID."
        )
    raise ValueError(f"No alarm found for '{identifier}'.")
