from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from platformdirs import user_cache_dir, user_data_dir

from .dependencies import shared_huggingface_cache
from .media import DubLocalError
from .timeline import Segment, parse_srt, segments_to_srt
from .translation import (
    TRANSLATION_LANGUAGES,
    TranslatedSegment,
    TranslationResult,
    normalise_language_code,
)


QWEN_CONTEXT_MODEL = {
    "id": "qwen3-4b-q4-k-m",
    "label": "Qwen3 4B · contextual quality",
    "repo_id": "Qwen/Qwen3-4B-GGUF",
    "revision": "a9a60d009fa7ff9606305047c2bf77ac25dbec49",
    "filename": "Qwen3-4B-Q4_K_M.gguf",
    "sha256": "7485fe6f11af29433bc51b69ff7fcdd187af17f0d694c5b05000b54664292e8534fdf5",
    "size": "2.5 GB",
    "license": "Apache-2.0",
    "native_context": 32768,
}

_MIN_CONTEXT_TOKENS = 4096
_MAX_CONTEXT_INPUT_TOKENS = 24576
_TARGET_CHUNK_SEGMENTS = 12
_MODEL_REGISTRATION = ".dublocal-contextual-translation.json"
_JSON_SCHEMA = json.dumps(
    {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "text": {"type": "string"},
            },
            "required": ["id", "text"],
            "additionalProperties": False,
        },
    },
    separators=(",", ":"),
)


@dataclass(frozen=True, slots=True)
class ContextPlan:
    duration_ms: int
    input_budget_tokens: int
    chunk_segments: int


class ContextualTranslationMissingError(DubLocalError):
    """Raised when the contextual translation runtime/model is not ready."""


def _new_job_dir(prefix: str) -> Path:
    root = Path(user_cache_dir("DubLocal")) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=root))


def contextual_models_dir() -> Path:
    root = Path(user_data_dir("DubLocal")) / "models" / "contextual-translation"
    root.mkdir(parents=True, exist_ok=True)
    return root


def contextual_model_path() -> Path:
    return contextual_models_dir() / str(QWEN_CONTEXT_MODEL["filename"])


def _registration_path() -> Path:
    return contextual_models_dir() / _MODEL_REGISTRATION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _llama_command() -> list[str] | None:
    candidates = [
        shutil.which("llama-cli"),
        "/opt/homebrew/bin/llama-cli",
        "/usr/local/bin/llama-cli",
    ]
    for raw in candidates:
        if raw and Path(raw).is_file() and os.access(raw, os.X_OK):
            return [str(raw)]

    llama = shutil.which("llama")
    if llama and Path(llama).is_file() and os.access(llama, os.X_OK):
        return [str(llama), "cli"]
    return None


def llama_cpp_status() -> str:
    command = _llama_command()
    return " · ".join(command) if command else "not installed"


def install_llama_cpp() -> list[str]:
    existing = _llama_command()
    if existing:
        return existing

    brew = shutil.which("brew")
    if not brew:
        for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                brew = candidate
                break
    if not brew:
        raise ContextualTranslationMissingError(
            "Contextual translation needs llama.cpp. Homebrew is not available, so DubLocal cannot install it automatically."
        )

    try:
        result = subprocess.run(
            [str(brew), "install", "llama.cpp"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30 * 60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DubLocalError(f"Could not install llama.cpp with Homebrew: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Homebrew failed").strip()
        raise DubLocalError(f"Could not install llama.cpp: {detail}")

    command = _llama_command()
    if not command:
        raise DubLocalError(
            "Homebrew installed llama.cpp, but DubLocal still cannot find llama-cli. Restart DubLocal and rescan Local Resources."
        )
    return command


def _registered_model_valid() -> bool:
    path = contextual_model_path()
    marker = _registration_path()
    if not (path.exists() or path.is_symlink()) or not marker.is_file():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("repo_id") == QWEN_CONTEXT_MODEL["repo_id"]
        and payload.get("revision") == QWEN_CONTEXT_MODEL["revision"]
        and payload.get("sha256") == QWEN_CONTEXT_MODEL["sha256"]
        and path.is_file()
    )


def install_contextual_model() -> Path:
    destination = contextual_model_path()
    if _registered_model_valid():
        return destination

    destination.unlink(missing_ok=True)
    _registration_path().unlink(missing_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise DubLocalError(
            "The Hugging Face download helper is missing from DubLocal. Run Repair installation once, then retry."
        ) from exc

    try:
        shared = Path(
            hf_hub_download(
                repo_id=str(QWEN_CONTEXT_MODEL["repo_id"]),
                revision=str(QWEN_CONTEXT_MODEL["revision"]),
                filename=str(QWEN_CONTEXT_MODEL["filename"]),
                cache_dir=str(shared_huggingface_cache()),
            )
        ).resolve()
    except Exception as exc:
        raise DubLocalError(f"Contextual translation model download failed: {exc}") from exc

    if _sha256(shared) != QWEN_CONTEXT_MODEL["sha256"]:
        raise DubLocalError(
            "Downloaded Qwen3 contextual translation model failed SHA-256 verification. DubLocal refused to register it."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.symlink_to(shared)
    except OSError as exc:
        raise DubLocalError(f"Could not link the shared Qwen3 model into DubLocal: {exc}") from exc

    _registration_path().write_text(
        json.dumps(
            {
                "repo_id": QWEN_CONTEXT_MODEL["repo_id"],
                "revision": QWEN_CONTEXT_MODEL["revision"],
                "filename": QWEN_CONTEXT_MODEL["filename"],
                "sha256": QWEN_CONTEXT_MODEL["sha256"],
                "shared_path": str(shared),
                "storage": "huggingface-shared-cache",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def remove_contextual_model() -> bool:
    destination = contextual_model_path()
    marker = _registration_path()
    existed = destination.exists() or destination.is_symlink() or marker.exists()
    destination.unlink(missing_ok=True)
    marker.unlink(missing_ok=True)
    return existed


def prepare_contextual_translation() -> str:
    command = install_llama_cpp()
    model = install_contextual_model()
    return f"{' '.join(command)} · {model.name}"


def estimate_tokens(text: str) -> int:
    """Cheap conservative token estimate suitable for context planning."""

    return max(1, int(math.ceil(len(text) / 3.5)))


def context_budget_for_duration(duration_ms: int) -> int:
    """Scale usable source context with programme length."""

    minutes = max(0.0, float(duration_ms) / 60000.0)
    budget = _MIN_CONTEXT_TOKENS + int(minutes * 128)
    return max(_MIN_CONTEXT_TOKENS, min(_MAX_CONTEXT_INPUT_TOKENS, budget))


def context_plan(segments: Sequence[Segment]) -> ContextPlan:
    duration_ms = max((segment.end_ms for segment in segments), default=0)
    minutes = duration_ms / 60000.0
    chunk_segments = min(20, _TARGET_CHUNK_SEGMENTS + int(minutes // 60) * 2)
    return ContextPlan(
        duration_ms=duration_ms,
        input_budget_tokens=context_budget_for_duration(duration_ms),
        chunk_segments=chunk_segments,
    )


def _segment_line(segment: Segment) -> str:
    text = segment.text.replace("\n", " ").strip()
    return f"[{segment.index}] {text}"


def _fit_lines(lines: Iterable[str], token_budget: int, *, reverse: bool = False) -> list[str]:
    material = list(lines)
    if reverse:
        material.reverse()
    chosen: list[str] = []
    used = 0
    for line in material:
        cost = estimate_tokens(line) + 2
        if chosen and used + cost > token_budget:
            break
        if cost > token_budget and not chosen:
            chosen.append(line[: max(32, token_budget * 3)])
            break
        chosen.append(line)
        used += cost
    if reverse:
        chosen.reverse()
    return chosen


def _evenly_sample_context(
    segments: Sequence[Segment],
    excluded: set[int],
    token_budget: int,
) -> list[str]:
    candidates = [segment for segment in segments if segment.index not in excluded and segment.text.strip()]
    if not candidates or token_budget <= 0:
        return []
    sample_count = min(len(candidates), max(8, token_budget // 36))
    if sample_count >= len(candidates):
        sampled = candidates
    else:
        positions = {
            round(i * (len(candidates) - 1) / max(1, sample_count - 1))
            for i in range(sample_count)
        }
        sampled = [candidates[pos] for pos in sorted(positions)]
    return _fit_lines((_segment_line(segment) for segment in sampled), token_budget)


def _build_context_sections(
    all_segments: Sequence[Segment],
    start: int,
    end: int,
    previous_translations: Sequence[TranslatedSegment],
    plan: ContextPlan,
) -> tuple[list[str], list[str], list[str]]:
    target_ids = {segment.index for segment in all_segments[start:end]}
    global_budget = int(plan.input_budget_tokens * 0.22)
    previous_translation_budget = int(plan.input_budget_tokens * 0.16)
    nearby_budget = plan.input_budget_tokens - global_budget - previous_translation_budget

    global_lines = _evenly_sample_context(all_segments, target_ids, global_budget)

    before_budget = int(nearby_budget * 0.62)
    after_budget = nearby_budget - before_budget
    before = _fit_lines(
        (_segment_line(segment) for segment in all_segments[:start] if segment.text.strip()),
        before_budget,
        reverse=True,
    )
    after = _fit_lines(
        (_segment_line(segment) for segment in all_segments[end:] if segment.text.strip()),
        after_budget,
    )
    nearby_lines = before + after

    previous_lines = _fit_lines(
        (
            f"[{item.index}] {item.translated_text.replace(chr(10), ' ').strip()}"
            for item in previous_translations
            if item.translated_text.strip()
        ),
        previous_translation_budget,
        reverse=True,
    )
    return global_lines, nearby_lines, previous_lines


def build_translation_prompt(
    all_segments: Sequence[Segment],
    start: int,
    end: int,
    source_language: str,
    target_language: str,
    previous_translations: Sequence[TranslatedSegment],
    plan: ContextPlan,
) -> str:
    source = TRANSLATION_LANGUAGES[source_language]["label"]
    target = TRANSLATION_LANGUAGES[target_language]["label"]
    target_segments = all_segments[start:end]
    global_lines, nearby_lines, previous_lines = _build_context_sections(
        all_segments, start, end, previous_translations, plan
    )
    target_lines = [_segment_line(segment) for segment in target_segments]

    return (
        "/no_think\n"
        f"Translate the TARGET LINES from {source} to natural, idiomatic {target}.\n"
        "Use all supplied context to resolve pronouns, speaker intent, recurring names, slang, jokes and tone.\n"
        "Do not translate sentence-by-sentence in isolation. Preserve meaning across adjacent lines.\n"
        "Keep profanity and register when they are present; do not sanitize dialogue.\n"
        "Translate bracketed non-dialogue cues naturally for the target language.\n"
        "Do not invent information. Keep each target subtitle concise enough for screen reading.\n"
        "Return exactly one JSON item for every TARGET LINE id, in the same order, and no items for context lines.\n\n"
        f"PROGRAMME DURATION: {plan.duration_ms / 60000.0:.1f} minutes\n"
        f"CONTEXT INPUT BUDGET: {plan.input_budget_tokens} tokens (scales with programme duration)\n\n"
        "GLOBAL PROGRAMME CONTEXT — reference only, do not output:\n"
        + ("\n".join(global_lines) if global_lines else "(none)")
        + "\n\nNEARBY SOURCE CONTEXT — reference only, do not output:\n"
        + ("\n".join(nearby_lines) if nearby_lines else "(none)")
        + "\n\nRECENT APPROVED TRANSLATIONS — preserve terminology/style, do not output:\n"
        + ("\n".join(previous_lines) if previous_lines else "(none)")
        + "\n\nTARGET LINES — translate these and only these:\n"
        + "\n".join(target_lines)
        + "\n"
    )


def _extract_json_array(raw: str) -> list[dict[str, object]]:
    text = raw.strip()
    starts = [index for index, char in enumerate(text) if char == "["]
    for start in reversed(starts):
        end = text.rfind("]")
        if end <= start:
            continue
        candidate = text[start : end + 1]
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
            return payload
    raise DubLocalError("Contextual translator returned output that was not a valid JSON subtitle array.")


def _parse_chunk_output(raw: str, target_segments: Sequence[Segment]) -> list[str]:
    payload = _extract_json_array(raw)
    expected = [segment.index for segment in target_segments]
    found: dict[int, str] = {}
    for item in payload:
        try:
            index = int(item["id"])
            text = str(item["text"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise DubLocalError("Contextual translator returned malformed subtitle JSON.") from exc
        if index in found:
            raise DubLocalError(f"Contextual translator returned subtitle id {index} more than once.")
        found[index] = text

    missing = [index for index in expected if index not in found]
    extra = [index for index in found if index not in expected]
    if missing or extra:
        raise DubLocalError(
            "Contextual translator did not preserve subtitle alignment "
            f"(missing={missing[:5]}, unexpected={extra[:5]})."
        )
    return [found[index] for index in expected]


def _run_llama(prompt: str, *, max_output_tokens: int) -> str:
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
        "You are a professional audiovisual subtitle translator. Follow the user's translation instructions exactly and return only the requested JSON.",
        "-p",
        prompt,
        "-c",
        str(QWEN_CONTEXT_MODEL["native_context"]),
        "-n",
        str(max(256, min(4096, max_output_tokens))),
        "--temp",
        "0.15",
        "--top-p",
        "0.8",
        "--repeat-penalty",
        "1.05",
        "--json-schema",
        _JSON_SCHEMA,
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
    return result.stdout


def contextual_translation_status(
    source_language: str = "auto",
    target_language: str = "en",
    duration_ms: int | None = None,
) -> str:
    source = normalise_language_code(source_language)
    target = normalise_language_code(target_language)
    engine = llama_cpp_status()
    model_state = "installed" if _registered_model_valid() else "not installed"
    duration = max(0, int(duration_ms or 0))
    budget = context_budget_for_duration(duration)
    route = "choose source and target languages"
    if source in TRANSLATION_LANGUAGES and target in TRANSLATION_LANGUAGES:
        route = f"{TRANSLATION_LANGUAGES[source]['label']} → {TRANSLATION_LANGUAGES[target]['label']}"
    lines = [
        f"[engine] llama.cpp · {engine}",
        f"[model] {QWEN_CONTEXT_MODEL['label']} · {model_state} · {QWEN_CONTEXT_MODEL['size']} · {QWEN_CONTEXT_MODEL['license']}",
        f"[route] {route}",
        f"[context] {budget} token input budget · grows with video duration · native model context {QWEN_CONTEXT_MODEL['native_context']}",
        f"[shared cache] {shared_huggingface_cache()}",
        "[policy] contextual quality is local-only; there is no cloud fallback",
    ]
    return "```text\n" + "\n".join(lines) + "\n```"


def translate_srt_contextual(
    subtitle_path: str | Path,
    source_language: str,
    target_language: str,
) -> TranslationResult:
    path = Path(subtitle_path).expanduser().resolve()
    if not path.is_file():
        raise DubLocalError("The subtitle file is no longer available. Extract or transcribe it again.")
    if path.suffix.lower() != ".srt":
        raise DubLocalError("Contextual translation expects DubLocal's normalized SRT timeline.")

    source = normalise_language_code(source_language)
    target = normalise_language_code(target_language)
    if source not in TRANSLATION_LANGUAGES:
        raise DubLocalError("Choose the subtitle source language before contextual translation.")
    if target not in TRANSLATION_LANGUAGES:
        raise DubLocalError("Choose a supported translation target language.")
    if source == target:
        raise DubLocalError("Source and target languages are the same; no translation is needed.")
    if not _llama_command() or not _registered_model_valid():
        raise ContextualTranslationMissingError(
            "Contextual translation is not prepared. Open Settings → Model Manager → Contextual translation and click Prepare / verify."
        )

    try:
        segments = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise DubLocalError(f"Could not read the subtitle timeline: {exc}") from exc
    if not segments:
        raise DubLocalError("The subtitle file contains no timed text to translate.")

    plan = context_plan(segments)
    translated: list[TranslatedSegment] = []
    for start in range(0, len(segments), plan.chunk_segments):
        end = min(len(segments), start + plan.chunk_segments)
        target_segments = segments[start:end]
        prompt = build_translation_prompt(
            segments,
            start,
            end,
            source,
            target,
            translated,
            plan,
        )
        target_text = "\n".join(segment.text for segment in target_segments)
        raw = _run_llama(
            prompt,
            max_output_tokens=max(512, estimate_tokens(target_text) * 2 + 256),
        )
        chunk = _parse_chunk_output(raw, target_segments)
        translated.extend(
            TranslatedSegment(
                index=segment.index,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                source_text=segment.text,
                translated_text=text,
            )
            for segment, text in zip(target_segments, chunk, strict=True)
        )

    output_dir = _new_job_dir("contextual-translation")
    output = output_dir / f"captions.{target}.srt"
    output.write_text(
        segments_to_srt(
            [
                Segment(
                    index=item.index,
                    start_ms=item.start_ms,
                    end_ms=item.end_ms,
                    text=item.translated_text,
                )
                for item in translated
            ]
        ),
        encoding="utf-8",
    )
    route = (
        f"Contextual Qwen3 · {TRANSLATION_LANGUAGES[source]['label']} → "
        f"{TRANSLATION_LANGUAGES[target]['label']} · {plan.input_budget_tokens}-token context budget"
    )
    return TranslationResult(
        srt_path=output,
        segments=translated,
        source_language=source,
        target_language=target,
        route=route,
    )
