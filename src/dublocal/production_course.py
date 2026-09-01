from __future__ import annotations

from . import authenticated_web as web
from .authenticated_web_policy import redact_authenticated_error
from .batch_flow import BatchFlowResult, QueueItem, QueueItemResult
from .job_control import JobCancelled, cancel_requested, check_cancelled
from .media import DubLocalError
from .production_pipeline import run_standard_workflow
from .source_providers import SourceInspection, SourceItem


ProgressCallback = web.ProgressCallback


def _pending_selection(
    inspection: SourceInspection,
    selected_ids: list[str] | tuple[str, ...] | None,
) -> tuple[SourceItem, ...]:
    states = web._manifest_states(inspection.source_url)
    if selected_ids is None:
        candidates = inspection.items
    else:
        wanted = {str(value) for value in selected_ids}
        candidates = tuple(item for item in inspection.items if item.id in wanted)
    return tuple(item for item in candidates if states.get(item.id) != "done")


def _safe_error(value: object) -> str:
    return redact_authenticated_error(str(value)) or "Authenticated processing failed."


def run_course_queue(
    *,
    inspection: SourceInspection,
    selected_ids: list[str] | tuple[str, ...] | None,
    rights_confirmed: bool,
    target_language: str,
    tasks: list[str] | tuple[str, ...] | None,
    subtitle_policy: str = "auto",
    keep_original_audio_track: bool = True,
    container: str = "mkv",
    video_quality: str = "source",
    progress_callback: ProgressCallback | None = None,
) -> BatchFlowResult:
    """Process authenticated lessons through the canonical Standard workflow."""

    check_cancelled()
    if not rights_confirmed:
        raise DubLocalError(
            "Confirm that you have legitimate access to this content and the right or legal authority to process it for your intended use."
        )
    if inspection.login_required:
        raise DubLocalError("The authenticated website session is not signed in yet.")
    if inspection.drm_protected:
        raise DubLocalError("This source appears DRM protected. DubLocal does not bypass DRM.")

    selected = _pending_selection(inspection, selected_ids)
    if not selected:
        raise DubLocalError("There are no pending selected lessons. Completed lessons are preserved and are not reprocessed.")

    provider = web.provider_for_url(inspection.source_url)
    completed: list[QueueItemResult] = []
    total = len(selected)

    for index, item in enumerate(selected):
        queue_item = QueueItem(web.SOURCE_TYPE, item.url, f"{item.index:02d} · {item.title}")
        if cancel_requested():
            for tail in selected[index:]:
                tail_q = QueueItem(web.SOURCE_TYPE, tail.url, f"{tail.index:02d} · {tail.title}")
                message = "Not started because the queue was stopped."
                completed.append(QueueItemResult(tail_q, "cancelled", None, (), error=message))
                web._update_course_state(inspection, tail, "cancelled", error=message)
            break

        prefix = f"{index + 1}/{total} · {item.title}"

        def overall(fraction: float, label: str) -> None:
            check_cancelled()
            web._notify(
                progress_callback,
                (index + max(0.0, min(1.0, fraction))) / total,
                f"{prefix} · {label}",
            )

        web._update_course_state(inspection, item, "running")
        try:
            web._notify(progress_callback, index / total, f"{prefix} · acquiring authorised source")
            acquired = provider.acquire(item, progress_callback=lambda f, l: overall(f * 0.22, l))
            result = run_standard_workflow(
                source_type="Local file",
                youtube_url="",
                local_file=str(acquired.path),
                rights_confirmed=True,
                target_language=target_language,
                tasks=tasks,
                subtitle_policy=subtitle_policy,
                keep_original_audio_track=keep_original_audio_track,
                container=container,
                video_quality=video_quality,
                progress_callback=lambda f, l: overall(0.22 + f * 0.78, l),
            )
            check_cancelled()
            published = web.publish_course_result(inspection, item, result)
            completed.append(QueueItemResult(queue_item, "done", result, published))
            web._update_course_state(inspection, item, "done", outputs=published)
            web._notify(progress_callback, (index + 1) / total, f"{prefix} · complete")
        except JobCancelled as exc:
            message = _safe_error(str(exc) or "Stopped by user.")
            completed.append(QueueItemResult(queue_item, "cancelled", None, (), error=message))
            web._update_course_state(inspection, item, "cancelled", error=message)
            for tail in selected[index + 1 :]:
                tail_q = QueueItem(web.SOURCE_TYPE, tail.url, f"{tail.index:02d} · {tail.title}")
                tail_message = "Not started because the queue was stopped."
                completed.append(QueueItemResult(tail_q, "cancelled", None, (), error=tail_message))
                web._update_course_state(inspection, tail, "cancelled", error=tail_message)
            break
        except Exception as exc:
            if cancel_requested():
                message = "Stopped by user."
                completed.append(QueueItemResult(queue_item, "cancelled", None, (), error=message))
                web._update_course_state(inspection, item, "cancelled", error=message)
                break
            message = _safe_error(exc)
            completed.append(QueueItemResult(queue_item, "failed", None, (), error=message))
            web._update_course_state(inspection, item, "failed", error=message)
            web._notify(progress_callback, (index + 1) / total, f"{prefix} · failed · continuing")

    return BatchFlowResult(tuple(completed))
