"""A small client for a running `mufuse serve`: what `mufuse chat` uses (stdlib HTTP only)."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
from typing import Any

from mufuse.companion.serve import serve_file

TIMEOUT_S = 90.0  # a local model may take a while to word a reply


class EngineNotRunningError(Exception):
    pass


class ChatClient:
    def __init__(self, port: int, token: str) -> None:
        self.port, self.token = port, token

    @classmethod
    def from_serve_file(cls, path: Path | None = None) -> ChatClient:
        path = path or serve_file()
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
            return cls(int(info["port"]), str(info["token"]))
        except (OSError, ValueError, KeyError) as exc:
            raise EngineNotRunningError(
                "The engine is not running. Start it first: uv run mufuse serve"
            ) from exc

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=TIMEOUT_S)
        try:
            conn.request(
                "POST",
                "/command",
                body=json.dumps(body).encode("utf-8"),
                headers={
                    "Host": f"127.0.0.1:{self.port}",
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
            )
            reply: dict[str, Any] = json.loads(conn.getresponse().read() or b"{}")
        except (OSError, json.JSONDecodeError) as exc:
            raise EngineNotRunningError(f"The engine stopped answering: {exc}") from exc
        finally:
            conn.close()
        return reply

    def ask(self, text: str) -> dict[str, Any]:
        return self._post({"type": "ask", "text": text})

    def cloud(self, on: bool) -> dict[str, Any]:
        return self._post({"type": "cloud", "on": on})
