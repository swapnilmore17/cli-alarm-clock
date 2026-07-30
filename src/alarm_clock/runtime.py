from __future__ import annotations

import json
import socket
from typing import Any

from alarm_clock.storage import socket_path


class DaemonUnavailable(RuntimeError):
    pass


def send_command(
    command: str,
    alarm_ids: list[str] | None = None,
    *,
    required: bool = True,
) -> dict[str, Any]:
    request = {"command": command, "alarm_ids": alarm_ids or []}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(2)
    try:
        client.connect(str(socket_path()))
        client.sendall((json.dumps(request) + "\n").encode())
        response = _receive_line(client)
    except (FileNotFoundError, ConnectionError, TimeoutError, OSError) as exc:
        if not required:
            return {"ok": False, "error": "Background service is not running."}
        raise DaemonUnavailable(
            "Background service is not running. Run 'alarm service install'."
        ) from exc
    finally:
        client.close()

    payload = json.loads(response)
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", "Daemon command failed."))
    return payload


def _receive_line(connection: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        raise ConnectionError("Daemon closed the connection.")
    return b"".join(chunks).split(b"\n", 1)[0].decode()
