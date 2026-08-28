from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, urlparse, urlunparse

from yt_dlp import YoutubeDL

from .job_control import JobCancelled, cancel_requested, check_cancelled
from .magic_flow import MagicFlowResult, run_magic_flow
from .media import DubLocalError
from .output_naming import safe_language_suffix


ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True, slots=True)
class QueueItem:
    source_type: str
    locator: str
    label: str


@dataclass(frozen=True, slots=True)
class QueueItemResult:
    item: QueueItem
    state: str
    result: MagicFlowResult | None
    published: tuple[tuple[str, Path], ...]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class BatchFlowResult:
    items: tuple[QueueItemResult, ...]

    @property
    def succeeded(self) -> tuple[QueueItemResult, ...]:
        return tuple(item for item in self.items if item.state == "done")

    @property
    def failed(self) -> tuple[QueueItemResult, ...]:
        return tuple(item for item in self.items if item.state == "failed")

    @property
    def cancelled(self) -> tuple[QueueItemResult, ...]:
        return tuple(item for item in self.items if item.state == "cancelled")


def _notify(callback: ProgressCallback | None, fraction: float, label: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, float(fraction))), label)


def _file_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, (str, os.PathLike)):
        return Path(value).expanduser()
    name = getattr(value, "name", None)
    if name:
        return Path(str(name)).expanduser()
    return None


def local_queue_items(files: Any) -> tuple[QueueItem, ...]:
    if files is None:
        values: list[Any] = []
    elif isinstance(files, (str, os.PathLike)) or getattr(files, "name", None):
        values = [files]
    else:
        values = list(files)

    seen: set[str] = set()
    items: list[QueueItem] = []
    for raw in values:
        path = _file_path(raw)
        if path is None:
            continue
        resolved = path.resolve()
        if not resolved.is_file():
            raise DubLocalError(f"Selected local file no longer exists: {resolved}")
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        items.append(QueueItem("Local file", str(resolved), resolved.name))
    if not items:
        raise DubLocalError("Choose one or more local media files first.")
    return tuple(items)


def _youtube_host(hostname: str | None) -> bool:
    host = (hostname or "").lower().split(":", 1)[0]
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


def _single_youtube_video_url(url: str) -> bool:
    parsed = urlparse(url)
    if not _youtube_host(parsed.hostname):
        return False
    if (parsed.hostname or "").lower() == "youtu.be":
        return bool(parsed.path.strip("/"))
    path = parsed.path.rstrip("/")
    if path in {"/watch"} and parse_qs(parsed.query).get("v"):
        return True
    return path.startswith(("/shorts/", "/live/", "/embed/"))


def _channel_videos_url(url: str) -> str:
    parsed = urlparse(url)
    if not _youtube_host(parsed.hostname) or (parsed.hostname or "").lower() == "youtu.be":
        return url
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) == 1 and parts[0].startswith("@"):
        path = "/" + parts[0] + "/videos"
    elif len(parts) == 2 and parts[0] in {"channel", "c", "user"}:
        path = "/" + "/".join(parts) + "/videos"
    else:
        return url
    return urlunparse(parsed._replace(path=path))


def _youtube_entry_url(entry: dict[str, Any]) -> tuple[str | None, str | None]:
    video_id = str(entry.get("id") or "").strip() or None
    webpage = str(entry.get("webpage_url") or "").strip()
    raw = str(entry.get("url") or "").strip()
    if webpage.startswith(("http://", "https://")):
        return webpage, video_id
    if raw.startswith(("http://", "https://")):
        return raw, video_id
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}", video_id
    if raw and len(raw) >= 6 and "/" not in raw:
        return f"https://www.youtube.com/watch?v={raw}", raw
    return None, video_id


def _flatten_youtube_entries(info: dict[str, Any]) -> list[QueueItem]:
    items: list[QueueItem] = []
    seen: set[str] = set()

    def visit(entry: Any) -> None:
        if not isinstance(entry, dict):
            return
        nested = entry.get("entries")
        if nested:
            for child in nested:
                visit(child)
            return
        url, video_id = _youtube_entry_url(entry)
        if not url:
            return
        key = video_id or url
        if key in seen:
            return
        seen.add(key)
        title = str(entry.get("title") or video_id or url).strip()
        items.append(QueueItem("YouTube", url, title))

    for entry in info.get("entries") or []:
        visit(entry)
    return items


def expand_youtube_queue(url: str) -> tuple[QueueItem, ...]:
    check_cancelled()
    clean = (url or "").strip()
    if not clean:
        raise DubLocalError("Paste a YouTube video, playlist, or channel URL first.")
    parsed = urlparse(clean)
    if not _youtube_host(parsed.hostname):
        raise DubLocalError("DubLocal batch input currently supports YouTube URLs only.")

    # A normal watch/short/live URL remains exactly one job even when it carries a
    # playlist query parameter. Playlist expansion is opt-in by pasting the playlist
    # or channel URL itself.
    if _single_youtube_video_url(clean):
        return (QueueItem("YouTube", clean, clean),)

    collection_url = _channel_videos_url(clean)
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "noplaylist": False,
        "extractor_retries": 3,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(collection_url, download=False)
    except JobCancelled:
        raise
    except Exception as exc:
        if cancel_requested():
            raise JobCancelled("Stopped by user.") from exc
        raise DubLocalError(f"Could not enumerate the YouTube source: {exc}") from exc

    check_cancelled()
    if not isinstance(info, dict):
        raise DubLocalError("YouTube did not return a usable video or collection.")
    entries = _flatten_youtube_entries(info)
    if entries:
        return tuple(entries)

    # Some extractors return ordinary video metadata even without a canonical watch
    # URL. Keep that as a single queue item rather than rejecting a valid source.
    url_from_info, _video_id = _youtube_entry_url(info)
    if url_from_info:
        return (
            QueueItem(
                "YouTube",
                url_from_info,
                str(info.get("title") or url_from_info),
            ),
        )
    raise DubLocalError(
        "No processable videos were found in this YouTube playlist/channel. Private, deleted, or unavailable entries are skipped."
    )


def youtube_output_root() -> Path:
    downloads = Path.home() / "Downloads"
    root = downloads / "DubLocal" if downloads.exists() else Path.home() / "DubLocal Outputs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _atomic_copy(source: Path, destination: Path) -> Path:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise DubLocalError(f"Generated output is no longer available: {source}")
    destination = destination.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source == destination.resolve(strict=False):
        return source
    temporary = destination.with_name(f".{destination.name}.dublocal-tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)
    return destination


def _youtube_stem(result: MagicFlowResult) -> str:
    for path, language in (
        (result.translated_subtitle, result.target_language),
        (result.source_subtitle, result.source_language),
    ):
        if path:
            name = Path(path).name
            suffix = f".{safe_language_suffix(language)}.srt"
            if name.endswith(suffix):
                return name[: -len(suffix)] or "youtube"
            if name.lower().endswith(".srt"):
                return name[:-4] or "youtube"
    if result.media_output:
        name = Path(result.media_output).name
        marker = ".dub."
        if marker in name:
            return name.split(marker, 1)[0] or "youtube"
        return Path(name).stem or "youtube"
    return "youtube"


def publish_magic_result(item: QueueItem, result: MagicFlowResult) -> tuple[tuple[str, Path], ...]:
    published: list[tuple[str, Path]] = []
    if item.source_type == "Local file":
        source_path = Path(item.locator).expanduser().resolve()
        parent = source_path.parent
        stem = source_path.stem
    else:
        parent = youtube_output_root()
        stem = _youtube_stem(result)

    if result.source_subtitle:
        language = safe_language_suffix(result.source_language)
        destination = parent / f"{stem}.{language}.srt"
        published.append(("Source subtitles", _atomic_copy(Path(result.source_subtitle), destination)))
    if result.translated_subtitle:
        language = safe_language_suffix(result.target_language)
        destination = parent / f"{stem}.{language}.srt"
        published.append(("Translated subtitles", _atomic_copy(Path(result.translated_subtitle), destination)))
    if result.voice_wav:
        language = safe_language_suffix(result.target_language or result.source_language)
        destination = parent / f"{stem}.voice.{language}.wav"
        published.append(("Voice WAV", _atomic_copy(Path(result.voice_wav), destination)))
    if result.media_output:
        internal = Path(result.media_output)
        destination = parent / internal.name
        published.append(("Media", _atomic_copy(internal, destination)))
    return tuple(published)


def _mark_cancelled_tail(
    completed: list[QueueItemResult],
    queue: tuple[QueueItem, ...],
    start_index: int,
    *,
    current_error: str = "Stopped by user.",
) -> None:
    for position in range(start_index, len(queue)):
        message = current_error if position == start_index else "Not started because the queue was stopped."
        completed.append(QueueItemResult(queue[position], "cancelled", None, (), error=message))


def run_magic_queue(
    *,
    source_type: str,
    youtube_url: str,
    local_files: Any,
    rights_confirmed: bool,
    target_language: str,
    tasks: Iterable[str] | None,
    subtitle_policy: str = "auto",
    keep_original_audio_track: bool = True,
    container: str = "mkv",
    video_quality: str = "source",
    progress_callback: ProgressCallback | None = None,
) -> BatchFlowResult:
    check_cancelled()
    if not rights_confirmed:
        raise DubLocalError("Confirm that you have the right or legal authority to process this media.")

    if source_type == "YouTube":
        _notify(progress_callback, 0.0, "Reading YouTube video/playlist/channel")
        queue = expand_youtube_queue(youtube_url)
    else:
        queue = local_queue_items(local_files)

    total = len(queue)
    if not total:
        raise DubLocalError("The queue is empty.")

    completed: list[QueueItemResult] = []
    for index, item in enumerate(queue):
        if cancel_requested():
            _mark_cancelled_tail(completed, queue, index)
            break

        prefix = f"{index + 1}/{total} · {item.label}"

        def item_progress(fraction: float, label: str) -> None:
            check_cancelled()
            overall = (index + max(0.0, min(1.0, float(fraction)))) / total
            _notify(progress_callback, overall, f"{prefix} · {label}")

        _notify(progress_callback, index / total, f"{prefix} · starting")
        try:
            result = run_magic_flow(
                source_type=item.source_type,
                youtube_url=item.locator if item.source_type == "YouTube" else "",
                local_file=item.locator if item.source_type == "Local file" else None,
                rights_confirmed=True,
                target_language=target_language,
                tasks=tasks,
                subtitle_policy=subtitle_policy,
                keep_original_audio_track=keep_original_audio_track,
                container=container,
                video_quality=video_quality,
                progress_callback=item_progress,
            )
            check_cancelled()
            published = publish_magic_result(item, result)
            completed.append(QueueItemResult(item, "done", result, published))
            _notify(progress_callback, (index + 1) / total, f"{prefix} · complete")
        except JobCancelled as exc:
            _mark_cancelled_tail(completed, queue, index, current_error=str(exc) or "Stopped by user.")
            _notify(progress_callback, index / total, f"{prefix} · stopped")
            break
        except Exception as exc:
            if cancel_requested():
                _mark_cancelled_tail(completed, queue, index)
                _notify(progress_callback, index / total, f"{prefix} · stopped")
                break
            message = str(exc)
            completed.append(QueueItemResult(item, "failed", None, (), error=message))
            _notify(
                progress_callback,
                (index + 1) / total,
                f"{prefix} · failed · continuing with next item",
            )

    return BatchFlowResult(tuple(completed))


def queue_rows(result: BatchFlowResult) -> list[list[str]]:
    rows: list[list[str]] = []
    for index, item in enumerate(result.items, start=1):
        if item.state == "done":
            saved = " · ".join(str(path) for _label, path in item.published) or "Completed"
            detail = saved
        else:
            detail = item.error or "Unknown error"
        rows.append([str(index), item.item.label, item.state.upper(), detail])
    return rows


def download_groups(result: BatchFlowResult) -> tuple[list[str], list[str], list[str], list[str]]:
    source_subtitles: list[str] = []
    translated_subtitles: list[str] = []
    voices: list[str] = []
    media: list[str] = []
    for item in result.succeeded:
        assert item.result is not None
        if item.result.source_subtitle:
            source_subtitles.append(str(item.result.source_subtitle))
        if item.result.translated_subtitle:
            translated_subtitles.append(str(item.result.translated_subtitle))
        if item.result.voice_wav:
            voices.append(str(item.result.voice_wav))
        if item.result.media_output:
            media.append(str(item.result.media_output))
    return source_subtitles, translated_subtitles, voices, media
