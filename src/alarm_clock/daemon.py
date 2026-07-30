from __future__ import annotations

import fcntl
import json
import signal
import socket
import sys
from pathlib import Path
from typing import IO
from typing import Any

from alarm_clock.scheduler import Scheduler
from alarm_clock.storage import daemon_lock_path, socket_path


class AlarmDaemon:
    def __init__(self, scheduler: Scheduler | None = None) -> None:
        self.scheduler = scheduler or Scheduler()
        self.running = True
        self.server: socket.socket | None = None
        self.lock_file: IO[str] | None = None

    def run(self) -> None:
        path = socket_path()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._acquire_process_lock(daemon_lock_path())
        path.unlink(missing_ok=True)

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path))
        path.chmod(0o600)
        self.server.listen(8)
        self.server.settimeout(0.25)

        try:
            while self.running:
                try:
                    connection, _ = self.server.accept()
                except TimeoutError:
                    connection = None
                if connection:
                    with connection:
                        self._handle(connection)
                try:
                    self.scheduler.tick()
                except Exception as exc:  # Keep the launch agent alive.
                    print(f"alarm daemon scheduler error: {exc}", file=sys.stderr)
        finally:
            self.scheduler.shutdown()
            self.server.close()
            path.unlink(missing_ok=True)
            if self.lock_file:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
                self.lock_file.close()

    def stop(self, *_args: object) -> None:
        self.running = False

    def _handle(self, connection: socket.socket) -> None:
        try:
            raw = connection.recv(64 * 1024).split(b"\n", 1)[0]
            request = json.loads(raw)
            response = self._dispatch(request)
        except Exception as exc:
            response = {"ok": False, "error": str(exc)}
        connection.sendall((json.dumps(response) + "\n").encode())

    def _dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        command = request.get("command")
        alarm_ids = request.get("alarm_ids") or []
        if not isinstance(alarm_ids, list):
            raise ValueError("alarm_ids must be a list.")
        if command == "stop":
            affected = self.scheduler.stop(alarm_ids)
            return {"ok": True, "affected": affected}
        if command == "snooze":
            affected = self.scheduler.snooze(alarm_ids)
            return {"ok": True, "affected": affected}
        if command == "silence":
            affected = self.scheduler.silence(alarm_ids)
            return {"ok": True, "affected": affected}
        if command == "status":
            return {"ok": True, **self.scheduler.status()}
        if command == "refresh":
            return {"ok": True}
        raise ValueError(f"Unknown daemon command: {command}")

    def _acquire_process_lock(self, path: Path) -> None:
        self.lock_file = path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(
                self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB
            )
        except BlockingIOError as exc:
            self.lock_file.close()
            self.lock_file = None
            raise RuntimeError("Another alarm daemon is already running.") from exc


def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("The alarm background service requires macOS.")
    daemon = AlarmDaemon()
    signal.signal(signal.SIGTERM, daemon.stop)
    signal.signal(signal.SIGINT, daemon.stop)
    daemon.run()


if __name__ == "__main__":
    main()
