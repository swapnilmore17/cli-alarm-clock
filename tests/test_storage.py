import json
from pathlib import Path

import pytest

from alarm_clock.models import Alarm
from alarm_clock.storage import AlarmStore, resolve_alarm


def make_alarm(name: str = "Wake up") -> Alarm:
    return Alarm(
        name=name,
        kind="weekly",
        weekdays=[0, 1, 2, 3, 4],
        time="07:00",
        snooze_minutes=10,
    )


def test_store_round_trip(tmp_path: Path) -> None:
    store = AlarmStore(tmp_path)
    alarm = make_alarm()
    store.save([alarm])
    loaded = store.load()
    assert loaded == [alarm]
    document = json.loads((tmp_path / "alarms.json").read_text())
    assert document["version"] == 1


def test_atomic_update(tmp_path: Path) -> None:
    store = AlarmStore(tmp_path)
    store.update(lambda alarms: alarms.append(make_alarm()))
    store.update(lambda alarms: setattr(alarms[0], "status", "paused"))
    assert store.load()[0].status == "paused"


def test_resolve_by_id_prefix_or_unique_name(tmp_path: Path) -> None:
    first = make_alarm("Morning")
    second = make_alarm("Evening")
    alarms = [first, second]
    assert resolve_alarm(alarms, first.id[:8]) is first
    assert resolve_alarm(alarms, "evening") is second


def test_duplicate_name_is_ambiguous() -> None:
    alarms = [make_alarm("Wake"), make_alarm("Wake")]
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_alarm(alarms, "wake")


def test_corrupt_json_is_reported(tmp_path: Path) -> None:
    (tmp_path / "alarms.json").write_text("not-json")
    with pytest.raises(RuntimeError, match="Cannot read"):
        AlarmStore(tmp_path).load()
