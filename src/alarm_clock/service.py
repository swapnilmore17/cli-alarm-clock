from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from alarm_clock.storage import cache_directory

LABEL = "com.local.cli-alarm-clock"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def domain() -> str:
    return f"gui/{os.getuid()}"


def install() -> None:
    _require_macos()
    destination = plist_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    logs = cache_directory()
    logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    configuration = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, "-m", "alarm_clock.daemon"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        "ProcessType": "Interactive",
        "StandardOutPath": str(logs / "daemon.log"),
        "StandardErrorPath": str(logs / "daemon-error.log"),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }
    destination.write_bytes(plistlib.dumps(configuration))
    destination.chmod(0o600)
    _run(["bootout", f"{domain()}/{LABEL}"], check=False)
    _run(["bootstrap", domain(), str(destination)])


def uninstall() -> None:
    _require_macos()
    _run(["bootout", f"{domain()}/{LABEL}"], check=False)
    plist_path().unlink(missing_ok=True)


def start() -> None:
    _require_macos()
    if not plist_path().exists():
        raise RuntimeError("Service is not installed. Run 'alarm service install'.")
    if is_running():
        _run(["kickstart", "-k", f"{domain()}/{LABEL}"])
    else:
        _run(["bootstrap", domain(), str(plist_path())])


def stop() -> None:
    _require_macos()
    _run(["bootout", f"{domain()}/{LABEL}"], check=False)


def restart() -> None:
    stop()
    start()


def is_running() -> bool:
    result = _run(["print", f"{domain()}/{LABEL}"], check=False)
    return result.returncode == 0


def status() -> str:
    _require_macos()
    if not plist_path().exists():
        return "not installed"
    return "running" if is_running() else "installed, stopped"


def _run(
    arguments: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["launchctl", *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message or f"launchctl exited with {result.returncode}")
    return result


def _require_macos() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("The alarm background service requires macOS.")
