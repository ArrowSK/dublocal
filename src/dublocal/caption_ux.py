from __future__ import annotations

from typing import Any


_LANGUAGE_NAMES = {
    "en": "English",
    "eng": "English",
    "hu": "Hungarian",
    "hun": "Hungarian",
    "ru": "Russian",
    "rus": "Russian",
    "de": "German",
    "deu": "German",
    "ger": "German",
    "fr": "French",
    "fra": "French",
    "fre": "French",
    "es": "Spanish",
    "spa": "Spanish",
    "it": "Italian",
    "ita": "Italian",
    "pt": "Portuguese",
    "por": "Portuguese",
    "pl": "Polish",
    "pol": "Polish",
    "uk": "Ukrainian",
    "ukr": "Ukrainian",
    "sr": "Serbian",
    "srp": "Serbian",
    "hr": "Croatian",
    "hrv": "Croatian",
    "ja": "Japanese",
    "jpn": "Japanese",
    "zh": "Chinese",
    "zho": "Chinese",
    "hi": "Hindi",
    "hin": "Hindi",
}

# If YouTube does not expose an explicit *-orig automatic-caption entry, keep the
# normal selector bounded to languages DubLocal can use directly. This is only a
# fallback; genuine original captions always take priority.
_PREFERRED_BASE_CODES = {
    "en",
    "hu",
    "ru",
    "de",
    "fr",
    "es",
    "it",
    "pt",
    "pl",
    "uk",
    "sr",
    "hr",
}


def _base_language(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("_", "-")
    if raw.endswith("-orig"):
        raw = raw[:-5]
    return raw.split("-", 1)[0] if raw else "und"


def _format_name(track: dict[str, Any]) -> str:
    for item in track.get("formats", []) or []:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        cleaned = name
        for suffix in (
            " (Original)",
            " (original)",
            " (Auto-generated)",
            " (auto-generated)",
            " - auto-generated",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        if cleaned and len(cleaned) <= 80:
            return cleaned
    return ""


def human_language_name(track: dict[str, Any]) -> str:
    format_name = _format_name(track)
    if format_name:
        return format_name
    raw = str(track.get("language") or "und")
    base = _base_language(raw)
    return _LANGUAGE_NAMES.get(raw.lower(), _LANGUAGE_NAMES.get(base, base.upper()))


def friendly_track_label(track: dict[str, Any], *, kind: str) -> str:
    name = human_language_name(track)
    if kind == "youtube":
        if track.get("source") == "manual":
            return f"{name} · Creator captions"
        if str(track.get("language") or "").lower().endswith("-orig"):
            return f"{name} · Automatic captions · original"
        return f"{name} · Automatic captions"

    codec = str(track.get("codec") or "").lower()
    text_capable = bool(track.get("text_capable", True))
    title = str(track.get("title") or "").strip()
    details = [name]
    if text_capable:
        details.append("Text subtitles")
    else:
        details.append("Image subtitles · use local transcription")
    if title and title.casefold() != name.casefold():
        details.append(title)
    elif codec and codec not in {"subrip", "srt", "webvtt", "mov_text", "text"}:
        details.append(codec.upper())
    return " · ".join(details)


def _looks_original_auto(track: dict[str, Any]) -> bool:
    language = str(track.get("language") or "").lower()
    if language.endswith("-orig"):
        return True
    for item in track.get("formats", []) or []:
        name = str(item.get("name") or "").casefold()
        if "original" in name:
            return True
    return False


def curate_caption_info(info: dict[str, Any] | None) -> dict[str, Any]:
    """Return a user-facing caption inventory without dumping YouTube translations.

    yt-dlp can expose 100+ machine-translated automatic caption variants. Those are
    not equivalent source subtitle tracks and make the ordinary selector unusable.
    DubLocal keeps the complete inventory in `subtitle_tracks_all`, but the normal
    selector shows creator captions and genuine/original automatic captions first.
    """

    payload = dict(info or {})
    kind = str(payload.get("kind") or "")
    raw_tracks = [dict(item) for item in payload.get("subtitle_tracks", []) or []]
    for track in raw_tracks:
        track["label"] = friendly_track_label(track, kind=kind)

    payload["subtitle_tracks_all"] = raw_tracks
    payload["caption_hidden_count"] = 0

    if kind != "youtube":
        payload["subtitle_tracks"] = raw_tracks
        payload["caption_inventory_text"] = _inventory_text(payload)
        return payload

    manual = [item for item in raw_tracks if item.get("source") == "manual"]
    automatic = [item for item in raw_tracks if item.get("source") == "auto"]
    original_auto = [item for item in automatic if _looks_original_auto(item)]

    if original_auto:
        visible = manual + original_auto
    elif manual:
        # Creator captions are already a better source than YouTube's translated
        # automatic catalogue. Keep that catalogue out of the normal workflow.
        visible = manual
    else:
        # Older/variant yt-dlp payloads do not always mark the source track with
        # `-orig`. Keep a bounded, human-readable fallback rather than showing 150+.
        preferred = [
            item
            for item in automatic
            if _base_language(str(item.get("language") or "")) in _PREFERRED_BASE_CODES
        ]
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in preferred or automatic:
            base = _base_language(str(item.get("language") or ""))
            if base in seen:
                continue
            seen.add(base)
            deduped.append(item)
            if len(deduped) >= 8:
                break
        visible = deduped

    visible_values = {str(item.get("value")) for item in visible}
    hidden = [item for item in raw_tracks if str(item.get("value")) not in visible_values]
    payload["subtitle_tracks"] = visible
    payload["caption_hidden_count"] = len(hidden)
    payload["caption_inventory_text"] = _inventory_text(payload)
    return payload


def _inventory_text(info: dict[str, Any]) -> str:
    tracks = info.get("subtitle_tracks", []) or []
    if not tracks:
        return "No usable existing subtitles found."

    labels = [str(item.get("label") or "Subtitle track") for item in tracks]
    shown = "; ".join(labels[:4])
    if len(labels) > 4:
        shown += f"; +{len(labels) - 4} more"

    hidden = int(info.get("caption_hidden_count") or 0)
    if hidden:
        shown += (
            f". {hidden} YouTube machine-translated variant"
            f"{'s are' if hidden != 1 else ' is'} hidden from this list; use DubLocal Translate for another language."
        )
    return shown


def caption_inventory_text(info: dict[str, Any] | None) -> str:
    payload = info or {}
    return str(payload.get("caption_inventory_text") or _inventory_text(payload))
