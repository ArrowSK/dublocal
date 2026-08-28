from __future__ import annotations

import re
from typing import Any

from . import authenticated_web as web
from .batch_flow import BatchFlowResult, QueueItemResult
from .media import DubLocalError


_INSTALLED = False
_URL_RE = re.compile(r"https?://[^\s<>\]\[)('\"]+", re.IGNORECASE)
_SECRET_RE = re.compile(
    r"(?i)\b(access_token|authorization|cookie|key|policy|signature|sig|token)=([^\s&]+)"
)


def redact_authenticated_error(value: str | None) -> str | None:
    """Make provider/import errors safe to persist or render in the UI."""

    if value is None:
        return None
    text = str(value)

    def replace_url(match: re.Match[str]) -> str:
        return web.sanitize_url(match.group(0))

    text = _URL_RE.sub(replace_url, text)
    text = _SECRET_RE.sub(lambda match: f"{match.group(1)}=REDACTED", text)
    return text


def install_authenticated_web_policy() -> None:
    """Install P0 safety policy without changing the provider/acquisition architecture."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_selected_items = web._selected_items
    original_update_course_state = web._update_course_state
    original_run_queue = web.run_authenticated_magic_queue

    def selected_items(inspection, selected_ids):
        # ``None`` means no explicit filter (all pending). An explicit empty list means
        # the user deliberately selected nothing and must never expand back to all.
        if selected_ids is None:
            return original_selected_items(inspection, None)
        wanted = {str(value) for value in selected_ids}
        states = web._manifest_states(inspection.source_url)
        return tuple(
            item
            for item in inspection.items
            if item.id in wanted and states.get(item.id) != "done"
        )

    def update_course_state(
        inspection,
        item,
        state,
        *,
        outputs=(),
        error=None,
    ):
        return original_update_course_state(
            inspection,
            item,
            state,
            outputs=outputs,
            error=redact_authenticated_error(error),
        )

    def run_queue(*args: Any, **kwargs: Any) -> BatchFlowResult:
        try:
            result = original_run_queue(*args, **kwargs)
        except DubLocalError as exc:
            raise DubLocalError(redact_authenticated_error(str(exc)) or "Authenticated import failed.") from exc
        safe_items = tuple(
            QueueItemResult(
                item=item.item,
                state=item.state,
                result=item.result,
                published=item.published,
                error=redact_authenticated_error(item.error),
            )
            for item in result.items
        )
        return BatchFlowResult(safe_items)

    web._selected_items = selected_items
    web._update_course_state = update_course_state
    web.run_authenticated_magic_queue = run_queue
