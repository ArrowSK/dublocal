from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from platformdirs import user_cache_dir

from .contextual_translation import (
    ContextualTranslationMissingError,
    QWEN_CONTEXT_MODEL,
    _llama_command,
    _registered_model_valid,
    contextual_model_path,
)
from .media import DubLocalError


_SYSTEM_PROMPT = (
    "You are a professional audiovisual subtitle translator. Translate faithfully, naturally and "
    "conservatively. Never invent dialogue. Follow the requested subtitle IDs and output format exactly."
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
        return [str(llama), "serve"]
    return None


def contextual_runtime_available() -> bool:
    return bool(_llama_server_command() or _llama_command())


def llama_server_status() -> str:
    command = _llama_server_command()
    return " · ".join(command) if command else "not installed"


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _clean_cli_text(raw: str) -> str:
    """Remove terminal control characters and known llama-cli UI noise.

    This is only for the compatibility fallback. The preferred llama-server path returns
    generated content through JSON and therefore never mixes runtime logs with subtitles.
    """

    text = (raw or "").replace("\b", "")
    text = "".join(char for char in text if char in "\n\t" or ord(char) >= 32)
    noise_prefixes = (
        "Loading model",
        "build      :",
        "model      :",
        "ftype      :",
        "modalities :",
        "using custom system prompt",
        "available commands:",
        "Exiting...",
    )
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(noise_prefixes):
            continue
        if stripped.startswith(("/exit", "/regen", "/clear", "/read", "/glob")):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _run_cli_compat(prompt: str, *, max_output_tokens: int) -> str:
    command = _llama_command()
    model = contextual_model_path()
    if not command or not _registered_model_valid():
        raise ContextualTranslationMissingError(
            "Contextual translation is not prepared. Open Settings → Model Manager → Contextual translation and click Prepare / verify."
        )

    args = command + [
        "-m",
        str(model),
        "--jinja",
        "--single-turn",
        "--reasoning",
        "off",
        "--simple-io",
        "--color",
        "off",
        "--log-colors",
        "off",
        "--log-verbosity",
        "1",
        "--no-warmup",
        "--no-display-prompt",
        "--no-show-timings",
        "-sys",
        _SYSTEM_PROMPT,
        "-p",
        prompt,
        "-c",
        str(QWEN_CONTEXT_MODEL["native_context"]),
        "-n",
        str(max(128, min(4096, max_output_tokens))),
        "--temp",
        "0.05",
        "--top-p",
        "0.75",
        "--repeat-penalty",
        "1.03",
    ]
    if platform.machine().lower() in {"arm64", "aarch64"}:
        args.extend(["-ngl", "99"])

    env = os.environ.copy()
    env.setdefault("GGML_METAL", "1")
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=6 * 60 * 60,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DubLocalError(f"Contextual translation engine failed to run: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "llama.cpp failed").strip()
        raise DubLocalError(
            "Contextual translation failed in llama.cpp: "
            + (detail.splitlines()[-1] if detail else "unknown error")
        )
    cleaned = _clean_cli_text(result.stdout)
    if not cleaned:
        raise DubLocalError("llama.cpp returned no translation text.")
    return cleaned


class ContextualRuntime:
    """One local llama.cpp model session reused across every chunk/recovery in one job."""

    def __init__(self) -> None:
        self._server_command = _llama_server_command()
        self._process: subprocess.Popen[str] | None = None
        self._log_handle = None
        self._log_path: Path | None = None
        self._base_url: str | None = None
        self.mode = "llama-server" if self._server_command else "llama-cli compatibility"

    def __enter__(self) -> "ContextualRuntime":
        if not _registered_model_valid():
            raise ContextualTranslationMissingError(
                "Contextual translation is not prepared. Open Settings → Model Manager → Contextual translation and click Prepare / verify."
            )
        if not self._server_command:
            if not _llama_command():
                raise ContextualTranslationMissingError(
                    "llama.cpp is not installed. Prepare contextual translation in Settings → Model Manager."
                )
            return self

        port = _free_local_port()
        self._base_url = f"http://127.0.0.1:{port}"
        log_root = Path(user_cache_dir("DubLocal")) / "jobs"
        log_root.mkdir(parents=True, exist_ok=True)
        log_dir = Path(tempfile.mkdtemp(prefix="llama-server-", dir=log_root))
        self._log_path = log_dir / "server.log"
        self._log_handle = self._log_path.open("w", encoding="utf-8")

        args = self._server_command + [
            "-m",
            str(contextual_model_path()),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "-c",
            str(QWEN_CONTEXT_MODEL["native_context"]),
            "--jinja",
            "--log-colors",
            "off",
            "--log-verbosity",
            "1",
        ]
        if platform.machine().lower() in {"arm64", "aarch64"}:
            args.extend(["-ngl", "99"])

        env = os.environ.copy()
        env.setdefault("GGML_METAL", "1")
        try:
            self._process = subprocess.Popen(
                args,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
        except OSError as exc:
            self._close_log()
            raise DubLocalError(f"Could not start the local llama.cpp translation server: {exc}") from exc

        try:
            deadline = time.monotonic() + 180.0
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    raise DubLocalError(
                        "The local llama.cpp translation server exited while loading the model. "
                        f"See temporary log: {self._log_path}"
                    )
                try:
                    with urlopen(f"{self._base_url}/health", timeout=2) as response:
                        if response.status == 200:
                            return self
                except (HTTPError, URLError, TimeoutError, OSError):
                    pass
                time.sleep(0.25)

            raise DubLocalError(
                "The local llama.cpp translation server did not become ready within 3 minutes. "
                f"See temporary log: {self._log_path}"
            )
        except Exception:
            self.__exit__(None, None, None)
            raise

    def _close_log(self) -> None:
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except OSError:
                pass
            self._log_handle = None

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            self._process = None
        self._close_log()

    def generate(self, prompt: str, *, max_output_tokens: int) -> str:
        if not self._server_command:
            return _run_cli_compat(prompt, max_output_tokens=max_output_tokens)
        if not self._base_url or not self._process or self._process.poll() is not None:
            raise DubLocalError("The local contextual translation runtime is not running.")

        payload = {
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "temperature": 0.05,
            "top_p": 0.75,
            "repeat_penalty": 1.03,
            "max_tokens": max(128, min(4096, int(max_output_tokens))),
        }
        request = Request(
            f"{self._base_url}/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=6 * 60 * 60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            raise DubLocalError(f"Local contextual translation request failed: {detail}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise DubLocalError(f"Local contextual translation request failed: {exc}") from exc

        try:
            content = str(body["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise DubLocalError("llama.cpp returned an unexpected translation response shape.") from exc
        if not content:
            raise DubLocalError("llama.cpp returned an empty translation response.")
        return content
