from __future__ import annotations

from typing import Any, Iterable

from . import batch_flow
from .batch_flow import BatchFlowResult, QueueItemResult
from .job_control import JobCancelled, cancel_requested, check_cancelled
from .media import DubLocalError
from .production_pipeline import run_standard_workflow


ProgressCallback = batch_flow.ProgressCallback


def run_processing_queue(
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
    """Run the Standard workflow sequentially without replacing batch-flow globals."""

    check_cancelled()
    if not rights_confirmed:
        raise DubLocalError("Confirm that you have the right or legal authority to process this media.")

    if source_type == "YouTube":
        batch_flow._notify(progress_callback, 0.0, "Reading YouTube video/playlist/channel")
        queue = batch_flow.expand_youtube_queue(youtube_url)
    else:
        queue = batch_flow.local_queue_items(local_files)

    total = len(queue)
    if not total:
        raise DubLocalError("The queue is empty.")

    completed: list[QueueItemResult] = []
    for index, item in enumerate(queue):
        if cancel_requested():
            batch_flow._mark_cancelled_tail(completed, queue, index)
            break

        prefix = f"{index + 1}/{total} · {item.label}"

        def item_progress(fraction: float, label: str) -> None:
            check_cancelled()
            overall = (index + max(0.0, min(1.0, float(fraction)))) / total
            batch_flow._notify(progress_callback, overall, f"{prefix} · {label}")

        batch_flow._notify(progress_callback, index / total, f"{prefix} · starting")
        try:
            result = run_standard_workflow(
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
            published = batch_flow.publish_magic_result(item, result)
            completed.append(QueueItemResult(item, "done", result, published))
            batch_flow._notify(progress_callback, (index + 1) / total, f"{prefix} · complete")
        except JobCancelled as exc:
            batch_flow._mark_cancelled_tail(
                completed,
                queue,
                index,
                current_error=str(exc) or "Stopped by user.",
            )
            batch_flow._notify(progress_callback, index / total, f"{prefix} · stopped")
            break
        except Exception as exc:
            if cancel_requested():
                batch_flow._mark_cancelled_tail(completed, queue, index)
                batch_flow._notify(progress_callback, index / total, f"{prefix} · stopped")
                break
            completed.append(QueueItemResult(item, "failed", None, (), error=str(exc)))
            batch_flow._notify(
                progress_callback,
                (index + 1) / total,
                f"{prefix} · failed · continuing with next item",
            )

    return BatchFlowResult(tuple(completed))
