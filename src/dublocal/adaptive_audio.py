from __future__ import annotations

import json
import math
import os
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Callable

import numpy as np

from . import m51, m53
from .media import DubLocalError
from .source_separation import (
    SeparationResult,
    prepare_separation_runtime,
    recommend_separation_profile,
    separate_vocals,
    separation_runtime,
    separation_status,
)
from .timeline import parse_srt
from .voice_text import spoken_text


ProgressCallback = Callable[[float, str], None]
MIX_STRATEGY_CHOICES = [
    ("Auto · recommended", "auto"),
    ("Dialogue · fast / no separation model", "dialogue"),
    ("Vocal separation · best for music · slower", "separated"),
]

_RENDER_LOCK = threading.RLock()
_ORIGINAL_RENDER = m51.render_dubbed_media
_ADVANCED_MIX_PREFERENCE = "auto"
_LAST_MIX_SUMMARY = "adaptive audio mix not used yet"


@dataclass(frozen=True, slots=True)
class MixPlan:
    requested: str
    resolved: str
    reason: str
    music_score: float


@dataclass(frozen=True, slots=True)
class SegmentMixPlan:
    index: int
    source_start_ms: int
    adjusted_start_ms: int
    end_ms: int
    voice_duration_ms: int
    delay_ms: int
    gain_db: float
    wav_path: Path


def set_advanced_mix_preference(value: str | None) -> str:
    global _ADVANCED_MIX_PREFERENCE
    selected = str(value or "auto").strip().lower()
    if selected not in {"auto", "dialogue", "separated"}:
        selected = "auto"
    _ADVANCED_MIX_PREFERENCE = selected
    return audio_mix_status(selected)


def advanced_mix_preference() -> str:
    return _ADVANCED_MIX_PREFERENCE


def last_mix_summary() -> str:
    return _LAST_MIX_SUMMARY


def _subtitle_music_score(subtitle_path: str | Path | None) -> float:
    if not subtitle_path:
        return 0.0
    path = Path(subtitle_path).expanduser()
    if not path.is_file():
        return 0.0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        segments = parse_srt(text)
    except (OSError, ValueError):
        return 0.0
    if not segments:
        return 0.0

    lowered = text.lower()
    score = 0.0
    if any(marker in text for marker in ("♪", "♫", "♬", "♩")):
        score += 4.0
    if any(
        cue in lowered
        for cue in (
            "[music]",
            "(music)",
            "[singing]",
            "(singing)",
            "[song]",
            "[instrumental]",
        )
    ):
        score += 4.0

    spoken = [segment for segment in segments if spoken_text(segment.text)]
    if spoken:
        timeline_ms = max(1, max(segment.end_ms for segment in spoken) - min(segment.start_ms for segment in spoken))
        occupied_ms = sum(max(0, segment.end_ms - segment.start_ms) for segment in spoken)
        duty = min(1.0, occupied_ms / timeline_ms)
        lengths = [len(segment.text.strip()) for segment in spoken if segment.text.strip()]
        typical_length = median(lengths) if lengths else 999
        # Lyrics commonly use short, almost continuously timed lines. This is only a
        # weak signal so a long interview is not routed to a heavy model by itself.
        if duty >= 0.62 and typical_length <= 54:
            score += 1.0
    return score


def music_signal_score(
    source_info: dict[str, Any] | None,
    subtitle_path: str | Path | None,
) -> float:
    info = source_info or {}
    title = str(info.get("title") or "").lower()
    uploader = str(info.get("uploader") or "").lower()
    score = _subtitle_music_score(subtitle_path)

    strong_title_markers = (
        "official music video",
        "official video",
        "lyric video",
        "lyrics video",
        "official audio",
    )
    if any(marker in title for marker in strong_title_markers):
        score += 3.0
    elif any(marker in title for marker in ("music video", " lyrics", " song", " karaoke")):
        score += 2.0

    if "vevo" in uploader:
        score += 2.0
    if any(marker in uploader for marker in ("records", "recordings", "music")):
        score += 1.0
    return score


def resolve_mix_plan(
    source_info: dict[str, Any] | None,
    subtitle_path: str | Path | None,
    requested: str | None,
) -> MixPlan:
    selected = str(requested or "auto").strip().lower()
    if selected not in {"auto", "dialogue", "separated"}:
        selected = "auto"
    score = music_signal_score(source_info, subtitle_path)

    if selected == "dialogue":
        return MixPlan(selected, "dialogue", "explicit fast dialogue mix", score)
    if selected == "separated":
        return MixPlan(selected, "separated", "explicit vocal-separation mix", score)

    if score >= 3.5 and separation_runtime() is not None:
        return MixPlan(
            selected,
            "separated",
            "music-heavy source detected and a separation runtime is already prepared",
            score,
        )
    if score >= 3.5:
        return MixPlan(
            selected,
            "dialogue",
            "music-heavy source detected, but separation is not prepared; using the safe lightweight path",
            score,
        )
    return MixPlan(selected, "dialogue", "source does not strongly require vocal separation", score)


def audio_mix_status(selected: str | None = None) -> str:
    preference = str(selected or advanced_mix_preference())
    return (
        separation_status()
        + "\n"
        + "```text\n"
        + f"[Advanced preference] {preference}\n"
        + "[Simple mode] always Auto · vocal separation is used only when music is strongly indicated and the runtime is already prepared\n"
        + "[fallback] any Auto separation failure returns to the lightweight dialogue mixer instead of failing the dub\n"
        + "```"
    )


def prepare_separation_ui() -> str:
    try:
        result = prepare_separation_runtime()
        return separation_status() + f"\n```text\n[done] {result}\n[model] separation weights download on first separated export\n```"
    except Exception as exc:
        return f"```text\n[error] {exc}\n```"


def _notify(callback: ProgressCallback | None, fraction: float, label: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), label)


def _read_pcm16(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise DubLocalError(f"Expected 16-bit PCM WAV for {path.name}; got {width * 8}-bit.")
    raw = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        raw = raw.reshape(-1, channels).mean(axis=1)
    return raw, rate


def _read_pcm16_slice(
    handle: wave.Wave_read,
    start_ms: int,
    end_ms: int,
) -> tuple[np.ndarray, int]:
    rate = handle.getframerate()
    channels = handle.getnchannels()
    width = handle.getsampwidth()
    if width != 2:
        raise DubLocalError("Demucs returned a vocal stem in an unsupported WAV format.")
    start_frame = max(0, int(round(start_ms * rate / 1000)))
    end_frame = min(handle.getnframes(), max(start_frame, int(round(end_ms * rate / 1000))))
    handle.setpos(start_frame)
    frames = handle.readframes(max(0, end_frame - start_frame))
    raw = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1 and raw.size:
        raw = raw.reshape(-1, channels).mean(axis=1)
    return raw, rate


def _rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))


def detect_vocal_onset_ms(
    vocal_handle: wave.Wave_read,
    subtitle_start_ms: int,
    subtitle_end_ms: int,
) -> int:
    """Conservatively delay a subtitle start to an acoustic vocal onset when obvious."""

    start = max(0, int(subtitle_start_ms))
    end = max(start + 1, int(subtitle_end_ms))
    window_start = max(0, start - 180)
    window_end = min(end, start + 700)
    audio, rate = _read_pcm16_slice(vocal_handle, window_start, window_end)
    if audio.size == 0:
        return start

    frame = max(1, int(round(rate * 0.020)))
    hop = max(1, int(round(rate * 0.010)))
    values: list[tuple[int, float]] = []
    for offset in range(0, max(1, audio.size - frame + 1), hop):
        chunk = audio[offset : offset + frame]
        if chunk.size < frame // 2:
            continue
        time_ms = window_start + int(round(offset * 1000 / rate))
        values.append((time_ms, _rms(chunk)))
    if not values:
        return start

    pre = [value for time_ms, value in values if time_ms < start]
    search = [(time_ms, value) for time_ms, value in values if start - 50 <= time_ms <= start + 550]
    if not search:
        return start
    baseline = median(pre) if pre else 0.0
    peak = max(value for _time_ms, value in search)
    threshold = max(0.0035, baseline * 2.4, peak * 0.16)

    for index, (time_ms, value) in enumerate(search):
        next_value = search[index + 1][1] if index + 1 < len(search) else value
        if value >= threshold and next_value >= threshold * 0.72:
            if time_ms <= start + 35:
                return start
            return min(start + 450, time_ms)
    return start


def _segment_source_rms(
    vocal_handle: wave.Wave_read,
    start_ms: int,
    end_ms: int,
) -> float:
    audio, _rate = _read_pcm16_slice(vocal_handle, start_ms, end_ms)
    return _rms(audio)


def _load_voice_manifest(voice_wav: Path) -> dict[str, Any] | None:
    manifest = voice_wav.parent / "voice-manifest.json"
    if not manifest.is_file():
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _fallback_windows(subtitle_path: str | Path | None) -> list[tuple[float, float]]:
    if not subtitle_path:
        return []
    path = Path(subtitle_path).expanduser()
    if not path.is_file():
        return []
    try:
        segments = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return []
    return [
        (segment.start_ms / 1000.0, (segment.end_ms + 250) / 1000.0)
        for segment in segments
        if spoken_text(segment.text)
    ]


def _build_aligned_voice(
    voice_wav: Path,
    vocals_wav: Path,
    output_dir: Path,
    *,
    fallback_subtitle_path: str | Path | None,
) -> tuple[Path, list[tuple[float, float]], list[SegmentMixPlan]]:
    manifest = _load_voice_manifest(voice_wav)
    if not manifest or not isinstance(manifest.get("segments"), list):
        return voice_wav, _fallback_windows(fallback_subtitle_path), []

    sample_rate = int(manifest.get("sample_rate") or 24000)
    raw_plans: list[dict[str, Any]] = []
    with wave.open(str(vocals_wav), "rb") as vocal_handle:
        for raw in manifest.get("segments", []):
            if not isinstance(raw, dict):
                continue
            wav_path = Path(str(raw.get("wav") or ""))
            if not wav_path.is_file():
                continue
            source_start = max(0, int(raw.get("start_ms") or 0))
            end_ms = max(source_start + 1, int(raw.get("end_ms") or source_start + 1))
            duration_ms = max(1, int(raw.get("voice_duration_ms") or 1))
            onset = detect_vocal_onset_ms(vocal_handle, source_start, end_ms)
            slack_ms = max(0, end_ms - source_start - duration_ms)
            delay_ms = min(max(0, onset - source_start), min(450, slack_ms))
            adjusted_start = source_start + delay_ms

            voice_audio, voice_rate = _read_pcm16(wav_path)
            if voice_rate != sample_rate:
                raise DubLocalError(
                    f"Kokoro segment sample rate changed unexpectedly ({voice_rate} Hz vs {sample_rate} Hz)."
                )
            source_measure_end = min(end_ms, adjusted_start + max(350, duration_ms))
            source_rms = _segment_source_rms(vocal_handle, adjusted_start, source_measure_end)
            voice_rms = _rms(voice_audio)
            gain_db = 0.0
            if source_rms >= 0.004 and voice_rms >= 0.004:
                gain_db = 20.0 * math.log10(source_rms / voice_rms)
            raw_plans.append(
                {
                    "index": int(raw.get("index") or 0),
                    "source_start_ms": source_start,
                    "adjusted_start_ms": adjusted_start,
                    "end_ms": end_ms,
                    "voice_duration_ms": duration_ms,
                    "delay_ms": delay_ms,
                    "raw_gain_db": gain_db,
                    "wav_path": wav_path,
                    "voice_audio": voice_audio,
                }
            )

    if not raw_plans:
        return voice_wav, _fallback_windows(fallback_subtitle_path), []

    valid_gains = [float(item["raw_gain_db"]) for item in raw_plans if abs(float(item["raw_gain_db"])) > 1e-6]
    centre = max(-3.0, min(3.0, median(valid_gains))) if valid_gains else 0.0

    plans: list[SegmentMixPlan] = []
    for item in raw_plans:
        raw_gain = float(item["raw_gain_db"])
        gain_db = max(-4.0, min(4.0, max(centre - 2.0, min(centre + 2.0, raw_gain))))
        plans.append(
            SegmentMixPlan(
                index=int(item["index"]),
                source_start_ms=int(item["source_start_ms"]),
                adjusted_start_ms=int(item["adjusted_start_ms"]),
                end_ms=int(item["end_ms"]),
                voice_duration_ms=int(item["voice_duration_ms"]),
                delay_ms=int(item["delay_ms"]),
                gain_db=gain_db,
                wav_path=Path(item["wav_path"]),
            )
        )
        item["gain_db"] = gain_db

    total_ms = max(
        max(plan.end_ms + 300 for plan in plans),
        max(plan.adjusted_start_ms + plan.voice_duration_ms for plan in plans),
    )
    total_samples = max(1, int(round(total_ms * sample_rate / 1000)))
    raw_mix = output_dir / "voice-aligned.mix-f32"
    mix = np.memmap(raw_mix, dtype=np.float32, mode="w+", shape=(total_samples,))
    mix[:] = 0.0
    try:
        by_index = {plan.index: plan for plan in plans}
        for item in raw_plans:
            plan = by_index[int(item["index"])]
            audio = np.asarray(item["voice_audio"], dtype=np.float32)
            gain = float(10 ** (plan.gain_db / 20.0))
            audio = audio * gain
            start_sample = int(round(plan.adjusted_start_ms * sample_rate / 1000))
            end_sample = min(total_samples, start_sample + audio.size)
            if end_sample > start_sample:
                mix[start_sample:end_sample] += audio[: end_sample - start_sample]
        mix.flush()
        output = output_dir / "voice-aligned.wav"
        with wave.open(str(output), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            chunk = sample_rate * 20
            for offset in range(0, total_samples, chunk):
                values = np.asarray(mix[offset : offset + chunk])
                pcm = (np.clip(values, -1.0, 1.0) * 32767.0).astype("<i2")
                handle.writeframes(pcm.tobytes())
    finally:
        del mix
        raw_mix.unlink(missing_ok=True)

    windows = [
        (
            plan.adjusted_start_ms / 1000.0,
            max(plan.end_ms + 250, plan.adjusted_start_ms + plan.voice_duration_ms) / 1000.0,
        )
        for plan in plans
    ]
    return output, windows, plans


def _guide_expression(windows: list[tuple[float, float]]) -> str:
    return "+".join(f"between(t\\,{start:.3f}\\,{end:.3f})" for start, end in windows)


def _create_separated_mix(
    source_media: Path,
    fitted_voice: Path,
    output_dir: Path,
    *,
    stems: SeparationResult,
    dialogue_subtitle_path: str | Path | None,
    progress_callback: ProgressCallback | None,
) -> tuple[Path, list[SegmentMixPlan]]:
    ffmpeg = m53.m5._require("ffmpeg")
    duration = m53.m5._duration_seconds(m53.m5._probe(source_media))
    aligned_voice, windows, plans = _build_aligned_voice(
        fitted_voice,
        stems.vocals,
        output_dir,
        fallback_subtitle_path=dialogue_subtitle_path,
    )
    output = output_dir / "dubbed-mix.m4a"

    if windows and duration > 0:
        guide = _guide_expression(windows)
        filter_graph = (
            "[0:a:0]aresample=48000,aformat=channel_layouts=stereo[acc];"
            "[1:a:0]aresample=48000,aformat=channel_layouts=stereo[voc];"
            "[2:a:0]aresample=48000,aformat=channel_layouts=stereo,asplit=2[dub_key][dub_mix];"
            f"aevalsrc=exprs='{guide}':s=48000:d={duration:.3f}[vocal_guide];"
            "[acc][dub_key]sidechaincompress=threshold=0.22:ratio=1.7:attack=18:release=240[acc_duck];"
            "[voc][vocal_guide]sidechaincompress=threshold=0.025:ratio=24:attack=6:release=260[voc_suppressed];"
            "[acc_duck][voc_suppressed][dub_mix]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,"
            "acompressor=threshold=0.42:ratio=1.7:attack=20:release=220:makeup=1,"
            "alimiter=limit=0.92[mix]"
        )
    else:
        filter_graph = (
            "[0:a:0]aresample=48000,aformat=channel_layouts=stereo[acc];"
            "[1:a:0]aresample=48000,aformat=channel_layouts=stereo[voc];"
            "[2:a:0]aresample=48000,aformat=channel_layouts=stereo,asplit=3[dub_acc][dub_voc][dub_mix];"
            "[acc][dub_acc]sidechaincompress=threshold=0.22:ratio=1.7:attack=18:release=240[acc_duck];"
            "[voc][dub_voc]sidechaincompress=threshold=0.025:ratio=24:attack=6:release=260[voc_suppressed];"
            "[acc_duck][voc_suppressed][dub_mix]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,"
            "acompressor=threshold=0.42:ratio=1.7:attack=20:release=220:makeup=1,"
            "alimiter=limit=0.92[mix]"
        )

    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(stems.accompaniment),
        "-i",
        str(stems.vocals),
        "-i",
        str(aligned_voice),
        "-filter_complex",
        filter_graph,
        "-map",
        "[mix]",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]
    m53.m5._run_ffmpeg_progress(
        command,
        duration_seconds=duration,
        start_fraction=0.58,
        end_fraction=0.98,
        label="Mixing accompaniment, suppressed source vocal and loudness-matched dub",
        progress_callback=progress_callback,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise DubLocalError("Separated dubbing mix did not create a usable soundtrack.")
    return output, plans


def _write_mix_manifest(
    output_dir: Path,
    plan: MixPlan,
    *,
    actual: str,
    separation: SeparationResult | None = None,
    segment_plans: list[SegmentMixPlan] | None = None,
    fallback_error: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "requested": plan.requested,
        "resolved": actual,
        "reason": plan.reason,
        "music_score": plan.music_score,
        "fallback_error": fallback_error,
    }
    if separation is not None:
        payload["separation"] = {
            "model": separation.model,
            "device": separation.device,
            "runtime": separation.runtime_label,
            "profile": separation.profile_label,
        }
    if segment_plans is not None:
        payload["segments"] = [
            {
                "index": item.index,
                "source_start_ms": item.source_start_ms,
                "adjusted_start_ms": item.adjusted_start_ms,
                "delay_ms": item.delay_ms,
                "gain_db": round(item.gain_db, 3),
            }
            for item in segment_plans
        ]
    try:
        (output_dir / "audio-mix-manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def create_adaptive_dubbed_mix(
    source_media: Path,
    fitted_voice: Path,
    output_dir: Path,
    *,
    dialogue_subtitle_path: str | Path | None,
    progress_callback=None,
    source_info: dict[str, Any] | None = None,
    mix_strategy: str | None = None,
) -> Path:
    global _LAST_MIX_SUMMARY
    plan = resolve_mix_plan(source_info, dialogue_subtitle_path, mix_strategy)

    if plan.resolved == "separated":
        try:
            _notify(progress_callback, 0.02, "Music-aware mix · preparing vocal separation")
            stems = separate_vocals(
                source_media,
                output_dir,
                profile=recommend_separation_profile(),
                prepare_if_missing=plan.requested == "separated",
                progress_callback=(
                    (lambda fraction, label: _notify(progress_callback, 0.02 + 0.52 * fraction, label))
                    if progress_callback
                    else None
                ),
            )
            mixed, segment_plans = _create_separated_mix(
                source_media,
                fitted_voice,
                output_dir,
                stems=stems,
                dialogue_subtitle_path=dialogue_subtitle_path,
                progress_callback=progress_callback,
            )
            adjusted = sum(1 for item in segment_plans if item.delay_ms > 0)
            _LAST_MIX_SUMMARY = (
                f"vocal separation · {stems.model} · source vocal suppressed · accompaniment preserved · "
                f"{adjusted} onset adjustment(s)"
            )
            _write_mix_manifest(
                output_dir,
                plan,
                actual="separated",
                separation=stems,
                segment_plans=segment_plans,
            )
            return mixed
        except Exception as exc:
            if plan.requested == "separated":
                raise
            # Auto must be reliability-first. A source-separation backend/model failure
            # never blocks the normal local dub; the established lightweight path is safe.
            _LAST_MIX_SUMMARY = f"dialogue fallback · vocal separation unavailable: {exc}"
            _write_mix_manifest(
                output_dir,
                plan,
                actual="dialogue",
                fallback_error=str(exc),
            )

    _notify(progress_callback, 0.06, "Using lightweight dialogue-aware mix")
    mixed = m53.create_balanced_dubbed_mix(
        source_media,
        fitted_voice,
        output_dir,
        dialogue_subtitle_path=dialogue_subtitle_path,
        progress_callback=progress_callback,
    )
    if not _LAST_MIX_SUMMARY.startswith("dialogue fallback"):
        _LAST_MIX_SUMMARY = "dialogue mix · lightweight full-programme ducking"
    _write_mix_manifest(output_dir, plan, actual="dialogue")
    return mixed


def render_adaptive_dubbed_media(*args, mix_strategy: str | None = None, **kwargs):
    """Keep m51's public renderer while swapping only its audio-mix stage per job."""

    source_info = args[0] if args else kwargs.get("info")
    requested = mix_strategy if mix_strategy is not None else advanced_mix_preference()

    def mixer(
        source_media: Path,
        fitted_voice: Path,
        output_dir: Path,
        *,
        dialogue_subtitle_path: str | Path | None,
        progress_callback=None,
    ) -> Path:
        return create_adaptive_dubbed_mix(
            source_media,
            fitted_voice,
            output_dir,
            dialogue_subtitle_path=dialogue_subtitle_path,
            progress_callback=progress_callback,
            source_info=source_info if isinstance(source_info, dict) else None,
            mix_strategy=requested,
        )

    # m51.render_dubbed_media looks up its module-global create_dubbed_mix at runtime.
    # Keep the override tightly scoped so older library callers and tests retain their
    # stable function while the production render receives the adaptive mixer.
    with _RENDER_LOCK:
        previous = m51.create_dubbed_mix
        m51.create_dubbed_mix = mixer
        try:
            return _ORIGINAL_RENDER(*args, **kwargs)
        finally:
            m51.create_dubbed_mix = previous


def render_magic_dubbed_media(*args, **kwargs):
    """Simple/Magic Flow always stays automatic regardless of the Advanced preference."""

    return render_adaptive_dubbed_media(*args, mix_strategy="auto", **kwargs)


def install_adaptive_audio_refinement() -> None:
    """Install the adaptive renderer before UI modules capture m51 function references."""

    m51.render_dubbed_media = render_adaptive_dubbed_media
