from __future__ import annotations

import json
import re
from typing import Any, Sequence

from .contextual_translation import _parse_chunk_output
from .media import DubLocalError
from .timeline import Segment
from .translation_quality import clean_generated_text

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_ID_LINE_RE = re.compile(r"^\s*\[?(\d+)\]?\s*(?::|[-–—])\s*(.+?)\s*$")
_CONTAINER_KEYS = ("translations", "items", "results", "data", "output")
_TRANSLATION_PREFIX_RE = re.compile(
    r"^\s*(?:translation|translated text|перевод|переведенный текст)\s*:\s*",
    re.IGNORECASE,
)


def _candidate_payloads(raw: str) -> list[Any]:
    """Recover likely JSON payloads from common local-LLM output wrappers."""

    text = clean_generated_text(raw)
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
    for line in clean_generated_text(raw).splitlines():
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


def _all_candidate_items(raw: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for payload in _candidate_payloads(raw):
        candidate = _items_from_payload(payload)
        if candidate:
            items.extend(candidate)
    items.extend(_line_items(raw))
    return items


def recover_partial_output(raw: str, target_segments: Sequence[Segment]) -> dict[int, str]:
    """Return unambiguous translations for expected IDs present in model output."""

    expected = {segment.index for segment in target_segments}
    values: dict[int, list[str]] = {}
    for item in _all_candidate_items(raw):
        try:
            index = int(item["id"])
            text = clean_generated_text(str(item["text"]))
        except (KeyError, TypeError, ValueError):
            continue
        if index not in expected or not text:
            continue
        values.setdefault(index, []).append(text)

    recovered: dict[int, str] = {}
    for index, candidates in values.items():
        unique = list(dict.fromkeys(candidates))
        if len(unique) == 1:
            recovered[index] = unique[0]
    return recovered


def recover_chunk_output(raw: str, target_segments: Sequence[Segment]) -> list[str]:
    """Parse model output while keeping subtitle alignment strict.

    The current preferred protocol is one line per subtitle: ``[ID] - text``.
    JSON remains accepted for compatibility with earlier DubLocal builds.
    """

    first_error: DubLocalError | None = None
    try:
        return _parse_chunk_output(clean_generated_text(raw), target_segments)
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
    previous = clean_generated_text(raw)
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
        "Keep meaning, tone, profanity and names faithful to the source. Do not invent a smoother but different sentence.\n"
        "If the previous response omitted a usable translation for an id, translate that source line conservatively now.\n\n"
        "SOURCE TARGET LINES:\n"
        f"{source_lines}\n\n"
        "PREVIOUS RESPONSE TO RECOVER:\n"
        f"{previous}\n"
    )


def build_single_line_recovery_prompt(
    original_context_prompt: str,
    segment: Segment,
    target_language_label: str,
    prior_chunk_output: str,
) -> str:
    """Build a final single-ID recovery prompt while retaining the original context."""

    prior = clean_generated_text(prior_chunk_output)
    if len(prior) > 8_000:
        prior = prior[-8_000:]
    return (
        original_context_prompt.rstrip()
        + "\n\nFINAL SINGLE-SUBTITLE RECOVERY TASK:\n"
        + f"Use all programme, nearby and prior-translation context above. Translate ONLY subtitle [{segment.index}] "
        + f"into natural {target_language_label}.\n"
        + f"Source text: {segment.text}\n"
        + f"Return EXACTLY one line: [{segment.index}] - translated text\n"
        + "Do not output JSON, Markdown, explanation, labels, alternatives or any other subtitle ID.\n"
        + "Keep names, tone, profanity and meaning faithful to the source; do not invent missing lyrics/dialogue.\n"
        + "For reference, the previous chunk recovery output was:\n"
        + prior
        + "\n"
    )


def clean_single_line_output(raw: str, segment_id: int) -> str:
    """Extract one subtitle translation without ever concatenating runtime/log output."""

    text = clean_generated_text(raw)
    if not text:
        raise DubLocalError(f"Contextual translator returned no text for subtitle id {segment_id}.")

    fenced = _CODE_FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    for payload in _candidate_payloads(text):
        if isinstance(payload, dict) and "text" in payload:
            candidate = clean_generated_text(str(payload["text"]))
            if candidate:
                return candidate
        if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
            candidate = clean_generated_text(str(payload[0].get("text") or ""))
            if candidate:
                return candidate

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        match = _ID_LINE_RE.match(line)
        if match and int(match.group(1)) == segment_id:
            candidate = match.group(2).strip().strip('"“”')
            if candidate:
                return candidate

    # A single bare line is tolerated for compatibility. Multiple unstructured lines
    # are rejected rather than joined, because recent llama-cli builds may print UI/log text.
    if len(lines) == 1:
        candidate = _TRANSLATION_PREFIX_RE.sub("", lines[0]).strip().strip('"“”')
        if candidate and len(candidate) <= 1_000:
            return candidate

    raise DubLocalError(
        f"Contextual translator returned ambiguous or contaminated text for subtitle id {segment_id}."
    )
