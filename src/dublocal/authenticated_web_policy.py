from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from . import authenticated_web as web
from .batch_flow import BatchFlowResult, QueueItemResult
from .media import DubLocalError


_INSTALLED = False
_URL_RE = re.compile(r"https?://[^\s<>\]\[)('\"]+", re.IGNORECASE)
_SECRET_RE = re.compile(
    r"(?i)\b(access_token|authorization|cookie|credential|key-pair-id|policy|signature|sig|token)=([^\s&]+)"
)


def _sensitive_query_key(key: str) -> bool:
    lower = str(key or "").strip().lower()
    if lower in web._SENSITIVE_QUERY_KEYS:
        return True
    if lower.startswith(("x-amz-", "x-goog-")):
        return True
    if lower in {"api_key", "apikey", "key-pair-id", "jwt", "security-token"}:
        return True
    return any(marker in lower for marker in ("access_token", "auth_token", "signature", "credential"))


def sanitize_authenticated_url(value: str) -> str:
    """Redact reusable query credentials while preserving non-secret routing."""

    try:
        parsed = urlparse(str(value or ""))
    except Exception:
        return ""
    filtered = [
        (key, "REDACTED" if _sensitive_query_key(key) else item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunparse(parsed._replace(query=urlencode(filtered, doseq=True), fragment=""))


def redact_authenticated_error(value: str | None) -> str | None:
    """Make provider/import errors safe to persist or render in the UI."""

    if value is None:
        return None
    text = str(value)

    def replace_url(match: re.Match[str]) -> str:
        return sanitize_authenticated_url(match.group(0))

    text = _URL_RE.sub(replace_url, text)
    text = _SECRET_RE.sub(lambda match: f"{match.group(1)}=REDACTED", text)
    return text


def canonical_authenticated_url(value: str) -> str:
    """Keep stable routing/query identity while discarding reusable credentials."""

    clean = web._valid_web_url(value)
    parsed = urlparse(clean)
    filtered = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not _sensitive_query_key(key)
    ]
    return urlunparse(parsed._replace(query=urlencode(filtered, doseq=True), fragment=""))


def install_authenticated_web_policy() -> None:
    """Install P0 safety policy without changing the provider/acquisition architecture."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_selected_items = web._selected_items
    original_update_course_state = web._update_course_state
    original_run_queue = web.run_authenticated_magic_queue

    # Canonical course/lesson identity must retain non-secret query parameters. Some
    # training portals route lessons through ?lesson=<id>; dropping every query value
    # would collapse distinct lessons into one resume identity. Only credentials/signing
    # material is removed. The same policy backs UI/log redaction for common CloudFront,
    # S3 and Google-style signed query parameters.
    web.sanitize_url = sanitize_authenticated_url
    web.canonical_source_url = canonical_authenticated_url

    def check_manifest(self, context, candidate: str) -> None:
        # Signed HLS/DASH URLs usually end in `master.m3u8?...` / `manifest.mpd?...`.
        # Inspect the parsed path rather than the complete URL so query signing cannot
        # accidentally skip the DRM/encryption boundary.
        lower = candidate.lower()
        path = urlparse(candidate).path.lower()
        is_manifest = path.endswith((".m3u8", ".mpd"))
        has_drm_marker = any(marker in lower for marker in web._DRM_MARKERS)
        if not is_manifest and not has_drm_marker:
            return
        if has_drm_marker:
            raise DubLocalError(
                "This lesson appears to use DRM-protected media. DubLocal does not bypass DRM."
            )
        try:
            response = context.request.get(candidate, timeout=20_000)
            text = response.text()
        except Exception:
            # Failure to inspect is not permission to bypass a DRM system. yt-dlp still
            # performs its own protected-media refusal and its errors are converted to
            # DubLocal's hard DRM boundary by the provider.
            return
        if web._manifest_is_protected(text, candidate):
            raise DubLocalError(
                "This lesson appears to use encrypted/DRM-protected media. DubLocal does not bypass DRM."
            )

    web.GenericAuthenticatedProvider._check_manifest = check_manifest

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
            raise DubLocalError(
                redact_authenticated_error(str(exc)) or "Authenticated import failed."
            ) from exc
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
