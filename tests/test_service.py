import plistlib
import subprocess
from pathlib import Path

from alarm_clock import service


def successful_run(
    _arguments: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, "", "")


def test_install_writes_launch_agent(
    monkeypatch, tmp_path: Path
) -> None:
    destination = tmp_path / "LaunchAgents" / "alarm.plist"
    logs = tmp_path / "cache"
    monkeypatch.setattr(service, "plist_path", lambda: destination)
    monkeypatch.setattr(service, "cache_directory", lambda: logs)
    monkeypatch.setattr(service, "_run", successful_run)

    service.install()

    configuration = plistlib.loads(destination.read_bytes())
    assert configuration["Label"] == service.LABEL
    assert configuration["RunAtLoad"] is True
    assert configuration["KeepAlive"] is True
    assert configuration["ProgramArguments"][1:] == [
        "-m",
        "alarm_clock.daemon",
    ]


def test_status_when_not_installed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        service, "plist_path", lambda: tmp_path / "missing.plist"
    )
    assert service.status() == "not installed"
