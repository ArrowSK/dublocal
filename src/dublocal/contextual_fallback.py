from __future__ import annotations

import os
import platform
import subprocess

from .contextual_translation import (
    ContextualTranslationMissingError,
    QWEN_CONTEXT_MODEL,
    _llama_command,
    _registered_model_valid,
    contextual_model_path,
)
from .media import DubLocalError


def run_llama_unconstrained(prompt: str, *, max_output_tokens: int) -> str:
    """Run the same local Qwen backend without llama.cpp JSON-schema sampling.

    This is used only as a structured-output recovery path. Some recent llama.cpp
    builds have regressions around constrained JSON generation; the recovery pass
    therefore uses a deliberately simple line protocol and validates subtitle IDs
    itself instead of trusting the runtime's schema layer.
    """

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
        "--no-display-prompt",
        "--no-show-timings",
        "-sys",
        "You are a professional audiovisual subtitle translator. Follow the user's instructions exactly and output only the requested subtitle lines.",
        "-p",
        prompt,
        "-c",
        str(QWEN_CONTEXT_MODEL["native_context"]),
        "-n",
        str(max(256, min(4096, max_output_tokens))),
        "--temp",
        "0.10",
        "--top-p",
        "0.8",
        "--repeat-penalty",
        "1.05",
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
        raise DubLocalError(f"Contextual translation recovery engine failed to run: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "llama.cpp failed").strip()
        raise DubLocalError(
            "Contextual translation recovery failed in llama.cpp: "
            + (detail.splitlines()[-1] if detail else "unknown error")
        )
    return result.stdout
