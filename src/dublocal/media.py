from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from platformdirs import user_cache_dir
from yt_dlp import YoutubeDL


TEXT_SUBTITLE_CODECS = {
    "ass",
    "mov_text",
    "ssa",
    "srt",
    "subrip",
    "text",
    "webvtt",
}

YOUTUBE_SUBTITLE_EXTENSIONS = ["vtt", "srt", "ttml", "srv3", "srv2", "srv1", "ass", "json3"]
YOUTUBE_RETRY_DELAYS = (2, 5, 10)


class DubLocalError(RuntimeError):
    """Base error presented to the user."""


class ToolMissingError(DubLocalError):
    """Raised when a required local executable is missing."""


class YoutubeRateLimitError(DubLocalError):
    """Raised when YouTube temporarily refuses caption delivery."""


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ToolMissingError(
            f"Required tool '{name}' was not found. Rerun the DubLocal launcher installer "
            "to install/check local media dependencies."
        )
    return path


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise DubLocalError(message) from exc


def _new_job_dir(prefix: str) -> Path:
    root = Path(user_cache_dir("DubLocal", ensure_exists=True)) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=root))


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def inspect_local_media(path: str | Path) -> dict[str, Any]:
    media_path = Path(path).expanduser().resolve()
    if not media_path.exists() or not media_path.is_file():
        raise DubLocalError("The selected local file no longer exists.")

    ffprobe = _require_tool("ffprobe")
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(media_path),
        ]
    )
    probe = json.loads(result.stdout)

    streams: list[dict[str, Any]] = []
    subtitle_tracks: list[dict[str, Any]] = []

    for raw in probe.get("streams", []):
        tags = raw.get("tags") or {}
        stream = {
            "index": raw.get("index"),
            "codec_type": raw.get("codec_type"),
            "codec_name": raw.get("codec_name") or "unknown",
            "language": tags.get("language") or "und",
            "title": tags.get("title") or "",
            "channels": raw.get("channels"),
            "width": raw.get("width"),
            "height": raw.get("height"),
        }
        streams.append(stream)

        if stream["codec_type"] == "subtitle":
            index = int(stream["index"])
            codec = str(stream["codec_name"])
            language = str(stream["language"])
            title = str(stream["title"])
            text_capable = codec in TEXT_SUBTITLE_CODECS
            details = [language, codec]
            if title:
                details.append(title)
            if not text_capable:
                details.append("image-based · use local transcription")
            subtitle_tracks.append(
                {
                    "value": f"local:{index}",
                    "label": " · ".join(details),
                    "index": index,
                    "codec": codec,
                    "language": language,
                    "title": title,
                    "text_capable": text_capable,
                }
            )

    format_info = probe.get("format") or {}
    return {
        "kind": "local",
        "path": str(media_path),
        "title": media_path.name,
        "duration": _safe_float(format_info.get("duration")),
        "format_name": format_info.get("format_long_name") or format_info.get("format_name"),
        "size": media_path.stat().st_size,
        "streams": streams,
        "subtitle_tracks": subtitle_tracks,
    }


def _normalise_youtube_formats(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    formats: list[dict[str, str]] = []
    for item in items:
        url = item.get("url")
        ext = item.get("ext")
        if not url or not ext:
            continue
        formats.append(
            {
                "url": str(url),
                "ext": str(ext),
                "name": str(item.get("name") or ""),
            }
        )
    return formats


def inspect_youtube(url: str) -> dict[str, Any]:
    clean_url = (url or "").strip()
    if not clean_url:
        raise DubLocalError("Paste a YouTube URL first.")

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extractor_retries": 3,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(clean_url, download=False)

    if not info or info.get("_type") == "playlist":
        raise DubLocalError("DubLocal currently accepts one video at a time, not playlists.")

    subtitle_tracks: list[dict[str, Any]] = []
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}

    for language in sorted(manual):
        formats = _normalise_youtube_formats(manual.get(language, []))
        subtitle_tracks.append(
            {
                "value": f"yt:manual:{language}",
                "label": f"{language} · creator captions",
                "language": language,
                "source": "manual",
                "formats": formats,
            }
        )

    for language in sorted(automatic):
        formats = _normalise_youtube_formats(automatic.get(language, []))
        subtitle_tracks.append(
            {
                "value": f"yt:auto:{language}",
                "label": f"{language} · automatic captions",
                "language": language,
                "source": "auto",
                "formats": formats,
            }
        )

    return {
        "kind": "youtube",
        "url": info.get("webpage_url") or clean_url,
        "id": info.get("id"),
        "title": info.get("title") or "Untitled YouTube video",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": _safe_float(info.get("duration")),
        "subtitle_tracks": subtitle_tracks,
        "http_headers": dict(info.get("http_headers") or {}),
    }


def extract_local_subtitle(info: dict[str, Any], track_value: str) -> Path:
    if info.get("kind") != "local":
        raise DubLocalError("Internal source mismatch: expected a local file.")
    try:
        _, raw_index = track_value.split(":", 1)
        stream_index = int(raw_index)
    except (AttributeError, ValueError) as exc:
        raise DubLocalError("Invalid subtitle-track selection.") from exc

    track = next(
        (item for item in info.get("subtitle_tracks", []) if item.get("index") == stream_index),
        None,
    )
    if not track:
        raise DubLocalError("The selected subtitle track is no longer available.")
    if not track.get("text_capable"):
        raise DubLocalError(
            "This subtitle stream is image-based and cannot be extracted as text. "
            "Use Local transcription below to create timestamped subtitles from the audio."
        )

    ffmpeg = _require_tool("ffmpeg")
    output_dir = _new_job_dir("local-subtitle")
    output = output_dir / "captions.srt"
    _run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(info["path"]),
            "-map",
            f"0:{stream_index}",
            "-c:s",
            "srt",
            str(output),
        ]
    )
    if not output.exists() or output.stat().st_size == 0:
        raise DubLocalError("FFmpeg completed but did not create a subtitle file.")
    return output


def _youtube_track(info: dict[str, Any], track_value: str) -> dict[str, Any]:
    track = next(
        (item for item in info.get("subtitle_tracks", []) if item.get("value") == track_value),
        None,
    )
    if not track:
        raise DubLocalError("The selected YouTube caption track is no longer available.")
    return track


def _preferred_youtube_formats(track: dict[str, Any]) -> list[dict[str, str]]:
    formats = list(track.get("formats") or [])
    rank = {ext: index for index, ext in enumerate(YOUTUBE_SUBTITLE_EXTENSIONS)}
    formats.sort(key=lambda item: rank.get(item.get("ext", ""), len(rank)))
    return formats


def _normalise_subtitle_to_srt(path: Path) -> Path:
    if path.suffix.lower() == ".srt":
        return path

    ffmpeg = _require_tool("ffmpeg")
    output = path.parent / "captions.srt"
    _run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(path),
            str(output),
        ]
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("FFmpeg could not normalize the downloaded caption track to SRT.")
    return output


def _download_youtube_caption_direct(
    info: dict[str, Any], track: dict[str, Any], output_dir: Path
) -> Path | None:
    formats = _preferred_youtube_formats(track)
    if not formats:
        return None

    headers = {
        "User-Agent": (
            info.get("http_headers", {}).get("User-Agent")
            or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    for key, value in (info.get("http_headers") or {}).items():
        if value:
            headers[str(key)] = str(value)

    last_429: HTTPError | None = None
    for candidate in formats:
        url = candidate.get("url")
        ext = candidate.get("ext") or "vtt"
        if not url:
            continue

        output = output_dir / f"captions.{ext}"
        delays = (0, *YOUTUBE_RETRY_DELAYS)
        for attempt, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay)
            try:
                request = Request(url, headers=headers)
                with urlopen(request, timeout=30) as response:
                    payload = response.read()
                if payload:
                    output.write_bytes(payload)
                    return output
            except HTTPError as exc:
                if exc.code == 429:
                    last_429 = exc
                    if attempt < len(delays):
                        continue
                    break
                break
            except (URLError, TimeoutError):
                break

    if last_429 is not None:
        raise YoutubeRateLimitError(
            "YouTube temporarily rate-limited caption delivery (HTTP 429). "
            "Use Local transcription below to create subtitles from the media audio instead."
        ) from last_429
    return None


def extract_youtube_subtitle(info: dict[str, Any], track_value: str) -> Path:
    if info.get("kind") != "youtube":
        raise DubLocalError("Internal source mismatch: expected YouTube.")

    try:
        _, source, language = track_value.split(":", 2)
    except (AttributeError, ValueError) as exc:
        raise DubLocalError("Invalid YouTube caption selection.") from exc

    if source not in {"manual", "auto"}:
        raise DubLocalError("Unknown YouTube caption source.")

    track = _youtube_track(info, track_value)
    output_dir = _new_job_dir("youtube-subtitle")

    direct = _download_youtube_caption_direct(info, track, output_dir)
    if direct is not None:
        return _normalise_subtitle_to_srt(direct)

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "subtitleslangs": [language],
        "subtitlesformat": "vtt/best",
        "writesubtitles": source == "manual",
        "writeautomaticsub": source == "auto",
        "retries": 3,
        "extractor_retries": 3,
        "sleep_interval_subtitles": 2,
    }

    try:
        with YoutubeDL(options) as ydl:
            ydl.extract_info(str(info["url"]), download=True)
    except Exception as exc:
        message = str(exc)
        if "429" in message or "Too Many Requests" in message:
            raise YoutubeRateLimitError(
                "YouTube temporarily rate-limited caption delivery (HTTP 429). "
                "Use Local transcription below to create subtitles from the media audio instead."
            ) from exc
        raise DubLocalError(f"YouTube subtitle extraction failed: {message}") from exc

    preferred_suffixes = [".vtt", ".srt", ".ass", ".ttml", ".srv3", ".srv2", ".srv1"]
    candidates = [path for path in output_dir.iterdir() if path.is_file()]
    candidates.sort(
        key=lambda path: preferred_suffixes.index(path.suffix)
        if path.suffix in preferred_suffixes
        else len(preferred_suffixes)
    )
    if not candidates:
        raise DubLocalError(
            "yt-dlp reported the caption track but did not produce a subtitle file. "
            "Use Local transcription if the caption remains unavailable."
        )
    return _normalise_subtitle_to_srt(candidates[0])


def extract_subtitle(info: dict[str, Any], track_value: str) -> Path:
    kind = info.get("kind")
    if kind == "local":
        return extract_local_subtitle(info, track_value)
    if kind == "youtube":
        return extract_youtube_subtitle(info, track_value)
    raise DubLocalError("Scan a source before extracting subtitles.")
