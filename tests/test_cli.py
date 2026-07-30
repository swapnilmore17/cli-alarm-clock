from pathlib import Path

import alarm_clock.cli as cli
from alarm_clock.cli import main
from alarm_clock.storage import AlarmStore


def configure_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALARM_CLOCK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ALARM_CLOCK_CACHE_DIR", str(tmp_path / "cache"))


def test_create_and_view_one_time_alarm(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    configure_paths(monkeypatch, tmp_path)
    result = main(
        [
            "create",
            "--name",
            "Meeting",
            "--date",
            "2099-01-01",
            "--time",
            "08:30",
            "--snooze",
            "10",
        ]
    )
    assert result == 0
    assert "Alarm set for" in capsys.readouterr().out

    assert main(["view"]) == 0
    output = capsys.readouterr().out
    assert "Meeting" in output
    assert "2099-01-01 at 08:30" in output


def test_pause_edit_and_resume(monkeypatch, tmp_path: Path, capsys) -> None:
    configure_paths(monkeypatch, tmp_path)
    main(
        [
            "create",
            "--name",
            "Routine",
            "--weekdays",
            "weekdays",
            "--time",
            "07:00",
            "--snooze",
            "5",
        ]
    )
    capsys.readouterr()

    assert main(["pause", "Routine"]) == 0
    assert AlarmStore().load()[0].status == "paused"
    assert main(["edit", "Routine", "--name", "Morning routine"]) == 0
    assert main(["resume", "Morning routine"]) == 0
    alarm = AlarmStore().load()[0]
    assert alarm.status == "active"
    assert alarm.name == "Morning routine"


def test_delete_has_no_confirmation(monkeypatch, tmp_path: Path) -> None:
    configure_paths(monkeypatch, tmp_path)
    main(
        [
            "create",
            "--name",
            "Temporary",
            "--weekdays",
            "daily",
            "--time",
            "12:00",
            "--snooze",
            "10",
        ]
    )
    assert main(["delete", "Temporary"]) == 0
    assert AlarmStore().load() == []


def test_edit_silences_without_stopping_lifecycle(
    monkeypatch, tmp_path: Path
) -> None:
    configure_paths(monkeypatch, tmp_path)
    main(
        [
            "create",
            "--name",
            "One time",
            "--date",
            "2099-01-01",
            "--time",
            "08:30",
            "--snooze",
            "10",
        ]
    )
    commands: list[str] = []

    def record(command: str, *_args, **_kwargs) -> dict[str, object]:
        commands.append(command)
        return {"ok": True}

    monkeypatch.setattr(cli, "send_command", record)
    assert main(["edit", "One time", "--name", "Renamed"]) == 0
    assert commands == ["silence", "refresh"]
    assert AlarmStore().load()[0].status == "active"


def test_invalid_past_alarm_returns_error(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    configure_paths(monkeypatch, tmp_path)
    result = main(
        [
            "create",
            "--name",
            "Past",
            "--date",
            "2000-01-01",
            "--time",
            "08:00",
            "--snooze",
            "10",
        ]
    )
    assert result == 1
    assert "future" in capsys.readouterr().err
