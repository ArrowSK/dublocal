from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from .contextual_translation import _parse_chunk_output
from .media import DubLocalError
from .timeline import Segment
from .translation_quality import clean_generated_text

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_ID_LINE_RE = re.compile(r"^\s*\[?(\d+)\]?\s*(?::|[-–—])\s*(.+?)\s*$")
_CONTAINER_KEYS = ("translations", "items", "results", "data", "output")
_TRANSLATION_PREFIX_RE = re.compile(
    r"^\s*(?:final\s+translation|translation|translated\s+text|answer|result|перевод|переведенный\s+текст)\s*:\s*",
    re.IGNORECASE,
)
_TRANSLATION_HEADER_RE = re.compile(
    r"^\s*(?:final\s+translation|translation|translated\s+text|answer|result|перевод|переведенный\s+текст)\s*:??\s*$",
    re.IGNORECASE,
)
_RUNTIME_NOISE_MARKERS = (
    "loading model",
    "available commands",
    "using custom system prompt",
    "build      :",
    "model      :",
    "ftype      :",
    "modalities :",
    "/no_think",
    "target lines",
    "final single-subtitle recovery task",
    "exiting...",
    ".gguf",
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


def _compact_recovery_context(original_context_prompt: str, max_chars: int = 3_600) -> str:
    """Keep the useful tail of the contextual prompt without re-feeding the whole prompt.

    Single-subtitle recovery used to prepend the complete programme prompt for every
    missing subtitle. On long/high-context jobs that made each fallback call almost as
    expensive as a normal translation call. The tail contains recent approved
    translations and the current TARGET LINES, which are the highest-value context for
    a last-resort repair.
    """

    text = clean_generated_text(original_context_prompt)
    if len(text) <= max_chars:
        return text
    return "[earlier programme context omitted for fast recovery]\n" + text[-max_chars:]


def build_missing_recovery_prompt(
    original_context_prompt: str,
    target_segments: Sequence[Segment],
    missing_segments: Sequence[Segment],
    recovered: Mapping[int, str],
    target_language_label: str,
    prior_output: str,
) -> str:
    """Recover every missing subtitle in one compact model call.

    The previous implementation made one expensive model call per missing subtitle.
    This prompt keeps chunk-local context and already recovered translations while
    asking for all missing IDs at once.
    """

    missing_ids = ", ".join(str(segment.index) for segment in missing_segments)
    source_lines = "\n".join(f"[{segment.index}] {segment.text}" for segment in target_segments)
    recovered_lines = "\n".join(
        f"[{segment.index}] {recovered[segment.index]}"
        for segment in target_segments
        if segment.index in recovered
    )
    prior = clean_generated_text(prior_output)
    if len(prior) > 3_000:
        prior = prior[-3_000:]
    return (
        "/no_think\n"
        "MISSING SUBTITLE RECOVERY — repair all missing IDs in ONE response.\n"
        + f"Missing IDs: {missing_ids}.\n"
        + f"Translate only those missing IDs into natural {target_language_label}.\n"
        + "Return EXACTLY one line per missing ID in this form: [ID] - translated text\n"
        + "Return no other subtitle IDs, JSON, Markdown, headings, explanations or alternatives.\n"
        + "Keep meaning, names, tone and profanity faithful; preserve speaker/reference consistency from the supplied chunk context.\n\n"
        + "COMPACT ORIGINAL CONTEXT — reference only:\n"
        + _compact_recovery_context(original_context_prompt, max_chars=2_800)
        + "\n\nSOURCE CHUNK — reference only:\n"
        + source_lines
        + "\n\nALREADY RECOVERED TRANSLATIONS — preserve continuity, do not output:\n"
        + (recovered_lines if recovered_lines else "(none)")
        + "\n\nPREVIOUS MODEL OUTPUT — reference only:\n"
        + prior
        + "\n"
    )


def build_single_line_recovery_prompt(
    original_context_prompt: str,
    segment: Segment,
    target_language_label: str,
    prior_chunk_output: str,
) -> str:
    """Build a compact final single-ID recovery prompt.

    The normal chunk translation already had the full programme context. Recovery is a
    formatting/omission fallback, so resend only the most useful nearby tail instead of
    the complete context for every missing subtitle.
    """

    context = _compact_recovery_context(original_context_prompt)
    prior = clean_generated_text(prior_chunk_output)
    if len(prior) > 3_000:
        prior = prior[-3_000:]
    return (
        "/no_think\n"
        "FINAL SINGLE-SUBTITLE RECOVERY TASK.\n"
        + f"Translate ONLY subtitle [{segment.index}] into natural {target_language_label}.\n"
        + f"Source text: {segment.text}\n"
        + f"Return EXACTLY one line: [{segment.index}] - translated text\n"
        + "Do not output JSON, Markdown, explanation, labels, alternatives or any other subtitle ID.\n"
        + "Keep names, tone, profanity and meaning faithful to the source; do not invent missing dialogue.\n\n"
        + "COMPACT CHUNK CONTEXT — reference only:\n"
        + context
        + "\n\nPREVIOUS CHUNK RECOVERY OUTPUT — reference only:\n"
        + prior
        + "\n"
    )


def _runtime_noise_line(line: str) -> bool:
    folded = line.casefold().strip()
    return any(marker in folded for marker in _RUNTIME_NOISE_MARKERS)


def clean_single_line_output(raw: str, segment_id: int) -> str:
    """Extract one subtitle translation without concatenating runtime/log output."""

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

    # Some llama.cpp modes may wrap an otherwise valid answer in one labelled line
    # plus harmless runtime text. Accept exactly one labelled translation candidate;
    # never concatenate arbitrary lines.
    labelled: list[str] = []
    for line in lines:
        candidate = _TRANSLATION_PREFIX_RE.sub("", line).strip().strip('"“”')
        if candidate != line.strip().strip('"“”') and candidate:
            labelled.append(candidate)
    labelled = list(dict.fromkeys(labelled))
    if len(labelled) == 1 and len(labelled[0]) <= 1_000:
        return labelled[0]

    # Also tolerate a standalone header followed by exactly one useful line, even if
    # llama.cpp prints known status text around it.
    useful = [line for line in lines if not _runtime_noise_line(line)]
    for position, line in enumerate(useful[:-1]):
        if _TRANSLATION_HEADER_RE.fullmatch(line):
            following = useful[position + 1].strip().strip('"“”')
            if following and len(following) <= 1_000:
                return following

    # A single bare line is tolerated for compatibility. If known runtime noise is
    # present, the one remaining useful line is equally unambiguous.
    candidates = [line for line in useful if not _TRANSLATION_HEADER_RE.fullmatch(line)]
    if len(candidates) == 1:
        candidate = _TRANSLATION_PREFIX_RE.sub("", candidates[0]).strip().strip('"“”')
        if candidate and len(candidate) <= 1_000:
            return candidate

    preview = " | ".join(lines[:4])[:220]
    raise DubLocalError(
        f"Contextual translator returned ambiguous or contaminated text for subtitle id {segment_id}. "
        f"Output preview: {preview or '(empty after cleanup)'}"
    )
