from __future__ import annotations

import subprocess
import sys
import threading
from importlib.resources import files


def alarm_sound_path() -> str:
    return str(files("alarm_clock").joinpath("assets", "alarm.wav"))


class AlertPlayer:
    def __init__(self) -> None:
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    @property
    def playing(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            stop_event = threading.Event()
            self._stop_event = stop_event
            self._thread = threading.Thread(
                target=self._play_loop,
                args=(stop_event,),
                name="alarm-audio",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            stop_event = self._stop_event
            process = self._process
            thread = self._thread
        if stop_event:
            stop_event.set()
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
        if thread:
            thread.join(timeout=2)
        with self._lock:
            if self._thread is thread and (not thread or not thread.is_alive()):
                self._thread = None
                self._stop_event = None

    def _play_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                process = subprocess.Popen(
                    ["afplay", alarm_sound_path()],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError as exc:
                print(f"alarm audio error: {exc}", file=sys.stderr)
                return
            with self._lock:
                self._process = process
            process.wait()
            with self._lock:
                if self._process is process:
                    self._process = None


def show_notification(title: str, message: str) -> None:
    script = (
        f'display notification "{_escape(message)}" '
        f'with title "{_escape(title)}"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
