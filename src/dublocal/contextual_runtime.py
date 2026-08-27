from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib import error, request

from .contextual_translation import (
    ContextualTranslationMissingError,
    QWEN_CONTEXT_MODEL,
    _registered_model_valid,
    contextual_model_path,
)
from .media import DubLocalError


_SYSTEM_PROMPT = (
    "You are a professional audiovisual subtitle translator. "
    "Follow the user's translation instructions exactly. "
    "Return only the requested DubLocal subtitle protocol."
)


def _llama_server_command() -> list[str] | None:
    candidates = [
        shutil.which("llama-server"),
        "/opt/homebrew/bin/llama-server",
        "/usr/local/bin/llama-server",
    ]
    for raw in candidates:
        if raw and Path(raw).is_file() and os.access(raw, os.X_OK):
            return [str(raw)]

    llama = shutil.which("llama")
    if llama and Path(llama).is_file() and os.access(llama, os.X_OK):
        return [str(llama), "server"]
    return None


def llama_server_status() -> str:
    command = _llama_server_command()
    return " · ".join(command) if command else "not installed"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ContextualLlamaSession:
    """One local llama.cpp server reused for every chunk in one translation job."""

    def __init__(self) -> None:
        command = _llama_server_command()
        if not command or not _registered_model_valid():
            raise ContextualTranslationMissingError(
                "Contextual translation is not prepared. Open Settings → Model Manager → Contextual translation and click Prepare / verify."
            )
        self.command = command
        self.model = contextual_model_path()
        self.port = _free_port()
        self.process: subprocess.Popen[str] | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "ContextualLlamaSession":
        args = self.command + [
            "-m",
            str(self.model),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "-c",
            str(QWEN_CONTEXT_MODEL["native_context"]),
            "--jinja",
            "--no-warmup",
        ]
        if platform.machine().lower() in {"arm64", "aarch64"}:
            args.extend(["-ngl", "99"])

        env = os.environ.copy()
        env.setdefault("GGML_METAL", "1")
        try:
            self.process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                env=env,
            )
        except OSError as exc:
            raise DubLocalError(f"Could not start the local contextual translation server: {exc}") from exc

        deadline = time.monotonic() + 120.0
        last_error = "server did not become ready"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise DubLocalError(
                    "The local contextual translation server exited while loading the model. "
                    "Open Settings → Model Manager and verify the contextual model."
                )
            try:
                with request.urlopen(f"{self.base_url}/health", timeout=2.0) as response:
                    if 200 <= response.status < 300:
                        return self
            except Exception as exc:  # server is expected to refuse connections while loading
                last_error = str(exc)
            time.sleep(0.25)

        self.close()
        raise DubLocalError(f"The local contextual translation server did not become ready: {last_error}")

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5.0)

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def complete(self, prompt: str, *, max_output_tokens: int) -> str:
        body: dict[str, Any] = {
            "model": self.model.name,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "temperature": 0.05,
            "top_p": 0.9,
            "max_tokens": max(128, min(4096, int(max_output_tokens))),
            "reasoning_effort": "none",
            "chat_template_kwargs": {"enable_thinking": False},
        }
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=60 * 60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise DubLocalError(
                f"Contextual translation server rejected the request ({exc.code}): {detail[:500]}"
            ) from exc
        except (error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise DubLocalError(f"Contextual translation server request failed: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DubLocalError("Contextual translation server returned an unexpected response.") from exc
        if not isinstance(content, str) or not content.strip():
            raise DubLocalError("Contextual translation server returned no translated text.")
        return content.strip()
