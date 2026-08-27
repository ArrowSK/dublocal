from __future__ import annotations

import json
import re
from typing import Any, Sequence

from .contextual_translation import _parse_chunk_output
from .media import DubLocalError
from .timeline import Segment

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_ID_LINE_RE = re.compile(r"^\s*\[?(\d+)\]?\s*(?::|[-–—])\s*(.+?)\s*$")
_CONTAINER_KEYS = ("translations", "items", "results", "data", "output")


def _candidate_payloads(raw: str) -> list[Any]:
    """Recover likely JSON payloads from common local-LLM output wrappers."""

    text = (raw or "").strip()
    candidates: list[str] = []
    if text:
        candidates.append(text)
    candidates.extend(match.group(1).strip() for match in _CODE_FENCE_RE.finditer(text))

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            payload, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        candidates.append(json.dumps(payload, ensure_ascii=False))

    payloads: list[Any] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            payloads.append(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    return payloads


def _items_from_payload(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return list(payload)
    if isinstance(payload, dict):
        for key in _CONTAINER_KEYS:
            value = payload.get(key)
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return list(value)
    return None


def _line_items(raw: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in (raw or "").splitlines():
        stripped = line.strip().rstrip(",")
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and "id" in payload and "text" in payload:
            items.append(payload)
            continue

        match = _ID_LINE_RE.match(stripped)
        if match:
            items.append({"id": int(match.group(1)), "text": match.group(2).strip()})
    return items


def recover_chunk_output(raw: str, target_segments: Sequence[Segment]) -> list[str]:
    """Parse model output while keeping subtitle alignment strict.

    The normal path accepts valid JSON. Recovery also tolerates harmless wrappers
    and a simple one-line-per-subtitle protocol used when llama.cpp constrained
    JSON generation is unreliable on a particular local build.
    """

    first_error: DubLocalError | None = None
    try:
        return _parse_chunk_output(raw, target_segments)
    except DubLocalError as exc:
        first_error = exc

    for payload in _candidate_payloads(raw):
        items = _items_from_payload(payload)
        if not items:
            continue
        try:
            return _parse_chunk_output(
                json.dumps(items, ensure_ascii=False),
                target_segments,
            )
        except DubLocalError:
            continue

    items = _line_items(raw)
    if items:
        try:
            return _parse_chunk_output(
                json.dumps(items, ensure_ascii=False),
                target_segments,
            )
        except DubLocalError:
            pass

    raise first_error or DubLocalError(
        "Contextual translator returned output that could not be recovered into aligned subtitle data."
    )


def build_format_repair_prompt(
    raw: str,
    target_segments: Sequence[Segment],
    target_language_label: str,
) -> str:
    ids = ", ".join(str(segment.index) for segment in target_segments)
    source_lines = "\n".join(f"[{segment.index}] {segment.text}" for segment in target_segments)
    previous = (raw or "").strip()
    if len(previous) > 12_000:
        previous = previous[:12_000] + "\n[truncated]"
    return (
        "/no_think\n"
        "Repair the previous subtitle-translation response using a simple plain-text protocol.\n"
        f"Required subtitle ids, exactly once and in this order: {ids}.\n"
        "Return EXACTLY one line per subtitle in this form: [ID] - translated text\n"
        "Example: [12] - Это естественный перевод строки.\n"
        "Do not output JSON, Markdown, headings, commentary or any other lines.\n"
        f"Every translated text must be natural {target_language_label}.\n"
        "Keep the meaning, tone, profanity and names from the previous translation when usable.\n"
        "If the previous response omitted a usable translation for an id, translate that source line naturally now.\n\n"
        "SOURCE TARGET LINES:\n"
        f"{source_lines}\n\n"
        "PREVIOUS RESPONSE TO RECOVER:\n"
        f"{previous}\n"
    )
