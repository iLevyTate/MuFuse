"""Who words the answer (007 decision 5): Ollama on this computer by default, the Claude API only
when the person switches cloud on, and templates when neither answers.

A model gets the system rules, the summary and the conversation, never raw signal. Any failure
is `ModelUnavailableError`, and the caller falls back to the next choice.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any, Protocol

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "llama3.2"
CLAUDE_MODEL = "claude-opus-5-5"
TIMEOUT_S = 30.0

Turn = dict[str, str]  # {"role": "user" | "assistant", "content": ...}


class ModelUnavailableError(Exception):
    pass


class Model(Protocol):
    name: str
    cloud: bool

    def reply(self, system: str, turns: Sequence[Turn]) -> str: ...


class Ollama:
    """A model served by Ollama on this computer."""

    cloud = False

    def __init__(self, model: str | None = None, url: str = OLLAMA_URL) -> None:
        self.model = model or os.environ.get("MUFUSE_OLLAMA_MODEL", OLLAMA_MODEL)
        self.url = url
        self.name = f"ollama:{self.model}"

    def reply(self, system: str, turns: Sequence[Turn]) -> str:
        body = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, *turns],
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                answer: dict[str, Any] = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ModelUnavailableError(f"Ollama: {exc}") from exc
        text = str(answer.get("message", {}).get("content", "")).strip()
        if not text:
            raise ModelUnavailableError("Ollama gave an empty answer")
        return text


class Claude:
    """The Claude API, opt-in (`mufuse[cloud]`). It receives the summary and the conversation."""

    cloud = True

    def __init__(self, model: str | None = None, client: Any = None) -> None:
        self.model = model or os.environ.get("MUFUSE_CLAUDE_MODEL", CLAUDE_MODEL)
        self.name = f"claude:{self.model}"
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise ModelUnavailableError(
                    "install the cloud extra: uv sync --extra cloud"
                ) from exc
            self._client = anthropic.Anthropic(max_retries=2, timeout=TIMEOUT_S)
        return self._client

    def reply(self, system: str, turns: Sequence[Turn]) -> str:
        client = self._get_client()
        try:
            response = client.beta.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system,
                messages=list(turns),
                output_config={"effort": "low"},  # a short chat reply
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except Exception as exc:  # anthropic.APIError, no credentials, network: the chat falls back
            raise ModelUnavailableError(f"Claude API: {exc}") from exc
        if response.stop_reason == "refusal":
            raise ModelUnavailableError("Claude API declined")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise ModelUnavailableError("Claude API gave an empty answer")
        return text
