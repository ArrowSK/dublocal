from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from platformdirs import user_cache_dir, user_data_dir
from tqdm.auto import tqdm
from yt_dlp import YoutubeDL

from .media import DubLocalError
from .progress import ProgressEstimator
from .timeline import Segment, parse_srt


WHISPER_MODELS: dict[str, dict[str, str]] = {
    "tiny": {
        "label": "Tiny · 75 MiB · fastest",
        "size": "75 MiB",
        "sha1": "bd577a113a864445d4c299885e0cb97d4ba92b5f",
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
        "license": "MIT",
    },
    "base": {
        "label": "Base · 142 MiB · recommended",
        "size": "142 MiB",
        "sha1": "465707469ff3a37a2b9b8d8f89f2f99de7299dac",
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
        "license": "MIT",
    },
    "small": {
        "label": "Small · 466 MiB · better accuracy",
        "size": "466 MiB",
        "sha1": "55356645c2b361a969dfd0ef2c5a50d530afd8d5",
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
        "license": "MIT",
    },
}

_PROGRESS_RE = re.compile(r"progress\s*=\s*(\d{1,3})%", re.IGNORECASE)


class WhisperEngineMissingError(DubLocalError):
    """Raised when whisper-cli is unavailable."""


class WhisperModelMissingError(DubLocalError):
    """Raised when a requested local model is not installed."""


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    srt_path: Path
    segments: list[Segment]
    model_id: str
    language: str


def whisper_models_dir() -> Path:
    root = Path(user_data_dir("DubLocal")) / "models" / "whisper"
    root.mkdir(parents=True, exist_ok=True)
    return root


def whisper_model_path(model_id: str) -> Path:
    if model_id not in WHISPER_MODELS:
        raise DubLocalError(f"Unknown Whisper model: {model_id}")
    return whisper_models_dir() / f"ggml-{model_id}.bin"


def installed_whisper_models() -> list[str]:
    return [model_id for model_id in WHISPER_MODELS if whisper_model_path(model_id).is_file()]


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_whisper_model(model_id: str) -> Path:
    metadata = WHISPER_MODELS.get(model_id)
    if not metadata:
        raise DubLocalError(f"Unknown Whisper model: {model_id}")

    destination = whisper_model_path(model_id)
    expected_sha1 = metadata["sha1"]

    if destination.is_file():
        if _sha1(destination) == expected_sha1:
            return destination
        destination.unlink(missing_ok=True)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".bin.part")
    temporary.unlink(missing_ok=True)

    request = Request(
        metadata["url"],
        headers={"User-Agent": "DubLocal/0.4 (+https://github.com/ArrowSK/dublocal)"},
    )
    try:
        with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        raise DubLocalError(f"Whisper model download failed: {exc}") from exc

    actual_sha1 = _sha1(temporary)
    if actual_sha1 != expected_sha1:
        temporary.unlink(missing_ok=True)
        raise DubLocalError(
            "Downloaded Whisper model failed its checksum verification. "
            "The file was deleted rather than used."
        )

    temporary.replace(destination)
    return destination


def remove_whisper_model(model_id: str) -> bool:
    path = whisper_model_path(model_id)
    existed = path.exists()
    path.unlink(missing_ok=True)
    return existed


def find_whisper_cli() -> str | None:
    candidates = [
        shutil.which("whisper-cli"),
        "/opt/homebrew/bin/whisper-cli",
        "/usr/local/bin/whisper-cli",
        "/opt/homebrew/opt/whisper-cpp/bin/whisper-cli",
        "/usr/local/opt/whisper-cpp/bin/whisper-cli",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def whisper_engine_status() -> tuple[bool, str]:
    executable = find_whisper_cli()
    if executable:
        return True, f"whisper.cpp ready · {executable}"
    return False, "whisper.cpp engine missing · rerun the DubLocal launcher installer"


def model_manager_status() -> str:
    engine_ready, engine_text = whisper_engine_status()
    installed = set(installed_whisper_models())
    lines = [f"[engine] {'ready' if engine_ready else 'missing'} · {engine_text}"]
    for model_id, metadata in WHISPER_MODELS.items():
        state = "installed" if model_id in installed else "not installed"
        lines.append(
            f"[model] {model_id:<5} · {state:<13} · {metadata['size']} · {metadata['license']}"
        )
    return "```text\n" + "\n".join(lines) + "\n```"


def _new_job_dir(prefix: str) -> Path:
    root = Path(user_cache_dir("DubLocal")) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=root))


def _download_youtube_audio(info: dict[str, Any], output_dir: Path) -> Path:
    url = str(info.get("url") or "").strip()
    if not url:
        raise DubLocalError("The scanned YouTube source no longer has a usable URL.")

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "source.%(ext)s"),
        "retries": 3,
        "extractor_retries": 3,
    }
    try:
        with YoutubeDL(options) as ydl:
            downloaded = ydl.extract_info(url, download=True)
            prepared = Path(ydl.prepare_filename(downloaded)) if downloaded else None
    except Exception as exc:
        message = str(exc)
        if "429" in message or "Too Many Requests" in message:
            raise DubLocalError(
                "YouTube is also rate-limiting media delivery, so local transcription cannot fetch "
                "the audio right now. Wait a few minutes or use a local copy of the media."
            ) from exc
        raise DubLocalError(f"Could not fetch YouTube audio for local transcription: {message}") from exc

    if prepared and prepared.is_file():
        return prepared

    candidates = [
        path
        for path in output_dir.glob("source.*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        raise DubLocalError("YouTube audio download completed without a usable media file.")
    return candidates[0]


def _source_media_path(info: dict[str, Any], output_dir: Path) -> Path:
    kind = info.get("kind")
    if kind == "local":
        path = Path(str(info.get("path") or "")).expanduser()
        if not path.is_file():
            raise DubLocalError("The selected local media file no longer exists.")
        return path
    if kind == "youtube":
        return _download_youtube_audio(info, output_dir)
    raise DubLocalError("Scan a source before starting local transcription.")


def _convert_to_whisper_wav(source: Path, output_dir: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise DubLocalError(
            "FFmpeg is required to prepare audio for local transcription. "
            "Rerun the DubLocal installer to install/check it."
        )

    output = output_dir / "speech-16k-mono.wav"
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise DubLocalError(f"FFmpeg could not prepare the speech audio: {message}") from exc

    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("FFmpeg did not create usable 16 kHz transcription audio.")
    return output


def _whisper_environment() -> dict[str, str]:
    env = os.environ.copy()
    for resource_dir in (
        Path("/opt/homebrew/opt/whisper-cpp/share/whisper-cpp"),
        Path("/usr/local/opt/whisper-cpp/share/whisper-cpp"),
    ):
        if resource_dir.is_dir():
            env.setdefault("GGML_METAL_PATH_RESOURCES", str(resource_dir))
            break
    return env


def _detected_language(output_prefix: Path, requested_language: str) -> str:
    json_path = output_prefix.with_suffix(".json")
    if json_path.is_file():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
            detected = str((payload.get("result") or {}).get("language") or "").strip().lower()
            if detected:
                return detected
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    return requested_language


def _run_whisper_with_progress(command: list[str]) -> None:
    """Run whisper.cpp and expose its own real percentage through tqdm/Gradio."""

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=_whisper_environment(),
        )
    except OSError as exc:
        raise DubLocalError(f"Could not start whisper.cpp: {exc}") from exc

    estimator = ProgressEstimator()
    captured: list[str] = []
    last = 0
    with tqdm(total=100, unit="%", desc="Transcribing speech", leave=False) as bar:
        assert process.stdout is not None
        for line in process.stdout:
            captured.append(line)
            match = _PROGRESS_RE.search(line)
            if not match:
                continue
            current = max(0, min(100, int(match.group(1))))
            if current > last:
                bar.update(current - last)
                last = current
            bar.set_description(estimator.message(current / 100.0, "Transcribing speech"))
        return_code = process.wait()
        if return_code == 0 and last < 100:
            bar.update(100 - last)

    if return_code != 0:
        detail = "".join(captured).strip()
        raise DubLocalError(
            "Local Whisper transcription failed: "
            + (detail.splitlines()[-1] if detail else f"exit code {return_code}")
        )


def transcribe_source(
    info: dict[str, Any],
    model_id: str = "base",
    language: str = "auto",
) -> TranscriptionResult:
    executable = find_whisper_cli()
    if not executable:
        raise WhisperEngineMissingError(
            "The local whisper.cpp engine is not installed. Rerun "
            "`zsh scripts/macos/install-launcher.sh` and allow whisper.cpp installation."
        )

    model = whisper_model_path(model_id)
    if not model.is_file():
        metadata = WHISPER_MODELS[model_id]
        raise WhisperModelMissingError(
            f"Whisper {model_id} is not installed ({metadata['size']}). "
            "Install it in Settings → Model Manager before starting."
        )

    job_dir = _new_job_dir("transcription")
    source = _source_media_path(info, job_dir)
    wav = _convert_to_whisper_wav(source, job_dir)
    output_prefix = job_dir / "captions"
    requested_language = (language or "auto").strip().lower()

    command = [
        executable,
        "-m",
        str(model),
        "-f",
        str(wav),
        "-osrt",
        "-oj",
        "-of",
        str(output_prefix),
        "-l",
        requested_language,
        "-pp",
    ]

    # CPU mode is slower but is the safest common denominator on Intel Macs.
    # Apple Silicon keeps whisper.cpp's Metal acceleration enabled by default.
    if platform.machine().lower() in {"x86_64", "amd64"}:
        command.append("-ng")

    _run_whisper_with_progress(command)

    srt_path = output_prefix.with_suffix(".srt")
    if not srt_path.is_file() or srt_path.stat().st_size == 0:
        raise DubLocalError("whisper.cpp completed but did not create an SRT subtitle file.")

    text = srt_path.read_text(encoding="utf-8", errors="replace")
    try:
        segments = parse_srt(text)
    except ValueError as exc:
        raise DubLocalError(f"Whisper created an invalid subtitle timeline: {exc}") from exc

    if not segments:
        raise DubLocalError("Whisper produced an empty transcription.")

    return TranscriptionResult(
        srt_path=srt_path,
        segments=segments,
        model_id=model_id,
        language=_detected_language(output_prefix, requested_language),
    )
