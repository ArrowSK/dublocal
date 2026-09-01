from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from platformdirs import user_cache_dir, user_config_dir
from yt_dlp import YoutubeDL

from .batch_flow import BatchFlowResult, QueueItem, QueueItemResult
from .job_control import JobCancelled, cancel_requested, check_cancelled, run_process, start_process
from .magic_flow import MagicFlowResult, run_magic_flow
from .media import DubLocalError
from .output_naming import safe_language_suffix
from .source_providers import (
    AUTHENTICATED_SOURCE_PROVIDERS,
    AcquiredMedia,
    ProgressCallback,
    SourceInspection,
    SourceItem,
    SourceProvider,
)


SOURCE_TYPE = "Course / Website"
_PLAYWRIGHT_SPEC = "playwright>=1.49,<2.0"
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "auth_token",
    "authorization",
    "cookie",
    "credential",
    "expires",
    "jwt",
    "key",
    "key-pair-id",
    "policy",
    "security-token",
    "signature",
    "sig",
    "token",
}
_MEDIA_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".mp3", ".m4a", ".aac", ".wav", ".flac"}
_MEDIA_CONTENT_TYPES = (
    "video/",
    "audio/",
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "application/dash+xml",
)
_DRM_MARKERS = ("widevine", "fairplay", "playready", "/license", "drmlicense", "license-server")
_LOGIN_MARKERS = ("/login", "/signin", "/sign-in", "/users/sign_in")
_URL_RE = re.compile(r"https?://[^\s<>\]\[)('\"]+", re.IGNORECASE)
_SECRET_RE = re.compile(
    r"(?i)\b(access_token|authorization|cookie|credential|key-pair-id|policy|signature|sig|token)=([^\s&]+)"
)


def _notify(callback: ProgressCallback | None, fraction: float, label: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, float(fraction))), label)


def _valid_web_url(value: str) -> str:
    clean = (value or "").strip()
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DubLocalError("Paste a normal http/https course or lesson URL first.")
    return clean


def _sensitive_query_key(key: str) -> bool:
    lower = str(key or "").strip().lower()
    if lower in _SENSITIVE_QUERY_KEYS:
        return True
    if lower.startswith(("x-amz-", "x-goog-")):
        return True
    return any(marker in lower for marker in ("access_token", "auth_token", "signature", "credential"))


def sanitize_url(value: str) -> str:
    """Redact reusable credentials from URLs before persistence or rendering."""

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
    """Make authenticated-source errors safe to persist or display."""

    if value is None:
        return None
    text = str(value)
    text = _URL_RE.sub(lambda match: sanitize_url(match.group(0)), text)
    return _SECRET_RE.sub(lambda match: f"{match.group(1)}=REDACTED", text)


def canonical_source_url(value: str) -> str:
    """Preserve stable routing while removing transient credentials and fragments."""

    parsed = urlparse(_valid_web_url(value))
    filtered = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not _sensitive_query_key(key)
    ]
    return urlunparse(parsed._replace(query=urlencode(filtered, doseq=True), fragment=""))


def _safe_component(value: str, fallback: str = "Course") -> str:
    text = re.sub(r"[\x00-\x1f/:*?\"<>|]+", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text[:120] or fallback).strip()


def _duration_seconds(text: str) -> float | None:
    match = re.search(r"(?<!\d)(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?!\d)", str(text or ""))
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    if seconds >= 60 or minutes >= 60:
        return None
    return float(hours * 3600 + minutes * 60 + seconds)


def _manifest_is_protected(text: str, url: str = "") -> bool:
    lower = (text or "").lower()
    lower_url = (url or "").lower()
    if any(marker in lower_url for marker in _DRM_MARKERS):
        return True
    if "#extm3u" in lower:
        for line in lower.splitlines():
            if line.startswith("#ext-x-key") and "method=none" not in line:
                return True
    if "<contentprotection" in lower or "urn:uuid:" in lower:
        return True
    return False


def browser_profile_root() -> Path:
    root = Path(user_config_dir("DubLocal")) / "authenticated-web" / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    return root


def browser_profile_dir(provider_id: str) -> Path:
    root = browser_profile_root() / _safe_component(provider_id, "generic").lower().replace(" ", "-")
    root.mkdir(parents=True, exist_ok=True)
    return root


def course_manifest_root() -> Path:
    root = Path(user_config_dir("DubLocal")) / "course-jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def course_manifest_path(source_url: str) -> Path:
    key = hashlib.sha256(canonical_source_url(source_url).encode("utf-8")).hexdigest()[:24]
    return course_manifest_root() / f"{key}.json"


def _read_manifest(source_url: str) -> dict[str, Any]:
    path = course_manifest_path(source_url)
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_manifest(source_url: str, value: dict[str, Any]) -> None:
    path = course_manifest_path(source_url)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _manifest_states(source_url: str) -> dict[str, str]:
    payload = _read_manifest(source_url)
    return {
        str(item_id): str(item.get("state") or "")
        for item_id, item in dict(payload.get("items") or {}).items()
        if isinstance(item, dict)
    }


def pending_item_ids(inspection: SourceInspection) -> tuple[str, ...]:
    states = _manifest_states(inspection.source_url)
    return tuple(item.id for item in inspection.items if states.get(item.id) != "done")


def reset_course_resume(source_url: str) -> bool:
    path = course_manifest_path(source_url)
    if not path.exists():
        return False
    path.unlink()
    return True


def _update_course_state(
    inspection: SourceInspection,
    item: SourceItem,
    state: str,
    *,
    outputs: tuple[tuple[str, Path], ...] = (),
    error: str | None = None,
) -> None:
    payload = _read_manifest(inspection.source_url)
    if not payload:
        payload = {
            "schema_version": 1,
            "provider": inspection.provider_id,
            "provider_label": inspection.provider_label,
            "course_title": inspection.title,
            "source_url": canonical_source_url(inspection.source_url),
            "items": {},
        }
    items = dict(payload.get("items") or {})
    items[item.id] = {
        "title": item.title,
        "index": item.index,
        "url": canonical_source_url(item.url),
        "state": state,
        "outputs": [str(path) for _label, path in outputs],
        "error": redact_authenticated_error(error),
        "updated_at": int(time.time()),
    }
    payload["items"] = items
    _write_manifest(inspection.source_url, payload)


def _browser_runtime_importable() -> bool:
    return importlib.util.find_spec("playwright") is not None


def _browser_executable() -> Path | None:
    if not _browser_runtime_importable():
        return None
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as api:
            path = Path(api.chromium.executable_path)
            return path if path.is_file() else None
    except Exception:
        return None


def browser_runtime_status() -> str:
    if not _browser_runtime_importable():
        return "Authenticated website browser is not prepared."
    executable = _browser_executable()
    if executable is None:
        return "Playwright is installed, but its local Chromium browser is not prepared."
    sessions = sorted(path.name for path in browser_profile_root().iterdir() if path.is_dir())
    suffix = f" Stored local sessions: {', '.join(sessions)}." if sessions else " No website sessions stored yet."
    return f"Authenticated website browser is ready.{suffix}"


def prepare_browser_runtime(*, progress_callback: ProgressCallback | None = None) -> str:
    _notify(progress_callback, 0.05, "Checking authenticated website browser")
    if not _browser_runtime_importable():
        result = run_process(
            [sys.executable, "-m", "pip", "install", _PLAYWRIGHT_SPEC],
            capture_output=True,
            text=True,
            timeout=900,
        )
        if result.returncode:
            raise DubLocalError(f"Could not install the authenticated website browser runtime: {result.stderr or result.stdout}")
        importlib.invalidate_caches()
    _notify(progress_callback, 0.45, "Preparing local Chromium")
    result = run_process(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode:
        raise DubLocalError(f"Could not prepare local Chromium: {result.stderr or result.stdout}")
    _notify(progress_callback, 1.0, "Authenticated website browser ready")
    return browser_runtime_status()


def _require_browser() -> None:
    if _browser_executable() is None:
        raise DubLocalError(
            "Authenticated website browser is not ready. Open Settings → Authenticated Websites and choose Prepare browser first."
        )


def _login_helper(url: str, provider_id: str) -> None:
    from playwright.sync_api import sync_playwright

    profile = browser_profile_dir(provider_id)
    closed = threading.Event()
    with sync_playwright() as api:
        context = api.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            accept_downloads=False,
        )
        context.on("close", lambda: closed.set())
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception:
            pass
        while not closed.wait(0.5):
            try:
                if not context.pages:
                    break
            except Exception:
                break
        try:
            context.close()
        except Exception:
            pass


def open_login_browser(url: str) -> str:
    clean = _valid_web_url(url)
    _require_browser()
    provider = provider_for_url(clean)
    command = [
        sys.executable,
        "-m",
        "dublocal.authenticated_web",
        "--login",
        clean,
        provider.provider_id,
    ]
    start_process(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (
        f"Opened a dedicated local {provider.label} browser session. Sign in on the website itself, then close that browser window before inspecting the course."
    )


def clear_session(provider_id: str) -> bool:
    target = browser_profile_root() / _safe_component(provider_id, "generic").lower().replace(" ", "-")
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True


def clear_all_sessions() -> int:
    count = 0
    for target in list(browser_profile_root().iterdir()):
        if target.is_dir():
            shutil.rmtree(target)
            count += 1
    return count


def _cookie_file(context: Any, output_dir: Path) -> Path:
    path = output_dir / ".cookies.txt"
    lines = ["# Netscape HTTP Cookie File", "# Generated locally by DubLocal; delete after acquisition."]
    for cookie in context.cookies():
        domain = str(cookie.get("domain") or "")
        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        cookie_path = str(cookie.get("path") or "/")
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = int(cookie.get("expires") or 0)
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        lines.append("\t".join((domain, include_sub, cookie_path, secure, str(max(0, expires)), name, value)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _collect_page(page: Any, source_url: str, provider_id: str) -> dict[str, Any]:
    responses: list[dict[str, str]] = []

    def capture(response: Any) -> None:
        try:
            content_type = str(response.headers.get("content-type") or "").lower()
            url = str(response.url)
            media_path = urlparse(url).path.lower()
            if any(content_type.startswith(prefix) for prefix in _MEDIA_CONTENT_TYPES) or media_path.endswith((".m3u8", ".mpd", ".mp4", ".webm")):
                responses.append({"url": url, "content_type": content_type})
        except Exception:
            pass

    page.on("response", capture)
    try:
        page.goto(source_url, wait_until="domcontentloaded", timeout=60_000)
    except Exception as exc:
        raise DubLocalError(f"Could not open the authenticated page: {redact_authenticated_error(str(exc)) or exc}") from exc
    try:
        page.wait_for_timeout(1_500)
    except Exception:
        pass

    title = str(page.title() or "Authenticated media").strip()
    try:
        heading = page.locator("h1").first.text_content(timeout=1500)
        if heading and heading.strip():
            title = heading.strip()
    except Exception:
        pass
    try:
        anchors = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({href: a.href || '', text: (a.innerText || a.textContent || '').trim(), download: a.hasAttribute('download')}))",
        )
    except Exception:
        anchors = []
    try:
        media = page.eval_on_selector_all(
            "video[src], video source[src], audio[src], audio source[src]",
            "els => els.map(e => ({url: e.currentSrc || e.src || '', content_type: e.type || ''}))",
        )
    except Exception:
        media = []
    try:
        performance_entries = page.evaluate(
            "performance.getEntriesByType('resource').map(e => e.name).filter(Boolean)"
        )
    except Exception:
        performance_entries = []
    for raw in performance_entries or []:
        text = str(raw)
        if urlparse(text).path.lower().endswith((".m3u8", ".mpd", ".mp4", ".webm")):
            media.append({"url": text, "content_type": ""})
    media.extend(responses)
    seen: set[str] = set()
    media_clean: list[dict[str, str]] = []
    for entry in media:
        url = str((entry or {}).get("url") or "")
        if not url or url.startswith("blob:") or url in seen:
            continue
        seen.add(url)
        media_clean.append({"url": url, "content_type": str((entry or {}).get("content_type") or "")})
    login_required = any(marker in str(page.url).lower() for marker in _LOGIN_MARKERS)
    try:
        login_required = login_required or page.locator('input[type="password"]').count() > 0
    except Exception:
        pass
    obvious_drm = any(any(marker in entry["url"].lower() for marker in _DRM_MARKERS) for entry in media_clean)
    return {
        "title": title,
        "page_url": str(page.url),
        "anchors": list(anchors or []),
        "media": media_clean,
        "login_required": login_required,
        "drm": obvious_drm,
        "provider_id": provider_id,
    }


def _lesson_id(provider_id: str, url: str, index: int) -> str:
    raw = f"{provider_id}|{canonical_source_url(url)}|{index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


class GenericAuthenticatedProvider(SourceProvider):
    provider_id = "generic-authenticated-web"
    label = "Authenticated website"

    def can_handle(self, locator: str) -> bool:
        try:
            parsed = urlparse(locator)
            return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        except Exception:
            return False

    def _items(self, page_data: dict[str, Any], original_url: str) -> tuple[SourceItem, ...]:
        url = str(page_data.get("page_url") or original_url)
        title = str(page_data.get("title") or "Authenticated media")
        return (
            SourceItem(
                id=_lesson_id(self.provider_id, url, 1),
                url=canonical_source_url(url),
                title=title,
                index=1,
                provider_id=self.provider_id,
                course_title=title,
            ),
        )

    def inspect(self, locator: str) -> SourceInspection:
        clean = _valid_web_url(locator)
        _require_browser()
        from playwright.sync_api import sync_playwright

        profile = browser_profile_dir(self.provider_id)
        with sync_playwright() as api:
            try:
                context = api.chromium.launch_persistent_context(str(profile), headless=True, accept_downloads=False)
            except Exception as exc:
                raise DubLocalError(
                    "Could not open the dedicated authenticated browser profile. Close any DubLocal sign-in browser window and try again."
                ) from exc
            try:
                page = context.pages[0] if context.pages else context.new_page()
                data = _collect_page(page, clean, self.provider_id)
            finally:
                context.close()
        items = self._items(data, clean)
        status = "login-required" if data["login_required"] else ("drm-protected" if data["drm"] else "ready")
        detail = (
            "Sign in with Open / Sign in, close the sign-in window, then inspect again."
            if data["login_required"]
            else "This page is ready for authenticated acquisition."
        )
        return SourceInspection(
            provider_id=self.provider_id,
            provider_label=self.label,
            source_url=canonical_source_url(clean),
            title=str(data["title"]),
            items=items,
            login_required=bool(data["login_required"]),
            drm_protected=bool(data["drm"]),
            status=status,
            detail=detail,
        )

    def _media_candidates(self, context: Any, page: Any, item: SourceItem) -> tuple[list[str], dict[str, str]]:
        data = _collect_page(page, item.url, self.provider_id)
        headers = {"Referer": str(data.get("page_url") or item.url)}
        try:
            headers["User-Agent"] = str(page.evaluate("navigator.userAgent"))
        except Exception:
            pass
        candidates: list[str] = []
        for anchor in data.get("anchors") or []:
            href = str((anchor or {}).get("href") or "")
            text = str((anchor or {}).get("text") or "").lower()
            if href and ((anchor or {}).get("download") or "download" in text):
                candidates.append(href)
        candidates.extend(str(entry.get("url") or "") for entry in (data.get("media") or []))
        candidates.append(item.url)
        clean: list[str] = []
        seen: set[str] = set()
        for value in candidates:
            if not value or value.startswith("blob:") or value in seen:
                continue
            seen.add(value)
            clean.append(value)
        return clean, headers

    def _check_manifest(self, context: Any, candidate: str) -> None:
        lower = candidate.lower()
        path = urlparse(candidate).path.lower()
        has_drm_marker = any(marker in lower for marker in _DRM_MARKERS)
        if not path.endswith((".m3u8", ".mpd")) and not has_drm_marker:
            return
        if has_drm_marker:
            raise DubLocalError("This lesson appears to use DRM-protected media. DubLocal does not bypass DRM.")
        try:
            response = context.request.get(candidate, timeout=20_000)
            text = response.text()
        except Exception:
            return
        if _manifest_is_protected(text, candidate):
            raise DubLocalError("This lesson appears to use encrypted/DRM-protected media. DubLocal does not bypass DRM.")

    def acquire(self, item: SourceItem, *, progress_callback: ProgressCallback | None = None) -> AcquiredMedia:
        check_cancelled()
        _require_browser()
        from playwright.sync_api import sync_playwright

        output_dir = Path(user_cache_dir("DubLocal")) / "jobs" / f"authenticated-{uuid.uuid4().hex[:12]}"
        output_dir.mkdir(parents=True, exist_ok=True)
        _notify(progress_callback, 0.03, f"Opening {self.label} lesson")
        profile = browser_profile_dir(self.provider_id)
        with sync_playwright() as api:
            try:
                context = api.chromium.launch_persistent_context(str(profile), headless=True, accept_downloads=False)
            except Exception as exc:
                raise DubLocalError(
                    "Could not use the dedicated website session. Close any DubLocal sign-in browser window and try again."
                ) from exc
            cookie_file: Path | None = None
            try:
                page = context.pages[0] if context.pages else context.new_page()
                candidates, headers = self._media_candidates(context, page, item)
                if any(marker in str(page.url).lower() for marker in _LOGIN_MARKERS):
                    raise DubLocalError("The website session is not signed in. Use Open / Sign in first.")
                cookie_file = _cookie_file(context, output_dir)
                last_error: str | None = None
                for position, candidate in enumerate(candidates, start=1):
                    check_cancelled()
                    self._check_manifest(context, candidate)
                    _notify(progress_callback, min(0.25, 0.08 + 0.03 * position), "Acquiring authorised media")
                    options = {
                        "quiet": True,
                        "no_warnings": True,
                        "cookiefile": str(cookie_file),
                        "http_headers": headers,
                        "outtmpl": str(output_dir / "source.%(ext)s"),
                        "format": "bestvideo*+bestaudio/best",
                        "merge_output_format": "mkv",
                        "writesubtitles": True,
                        "writeautomaticsub": False,
                        "allsubtitles": True,
                        "embedsubtitles": True,
                        "noplaylist": True,
                        "retries": 3,
                        "fragment_retries": 3,
                        "progress_hooks": [lambda _data: check_cancelled()],
                    }
                    try:
                        with YoutubeDL(options) as ydl:
                            ydl.extract_info(candidate, download=True)
                    except JobCancelled:
                        raise
                    except Exception as exc:
                        message = str(exc).lower()
                        if "drm" in message or "encrypted" in message or "widevine" in message:
                            raise DubLocalError("This lesson appears to use DRM-protected media. DubLocal does not bypass DRM.") from exc
                        last_error = redact_authenticated_error(str(exc))
                        continue
                    media_files = [
                        path
                        for path in output_dir.iterdir()
                        if path.is_file() and path.suffix.lower() in _MEDIA_SUFFIXES and path.stat().st_size > 0
                    ]
                    if media_files:
                        media = max(media_files, key=lambda path: path.stat().st_size)
                        _notify(progress_callback, 1.0, "Authenticated media ready")
                        return AcquiredMedia(
                            path=media,
                            title=item.title,
                            provider_id=self.provider_id,
                            source_url=canonical_source_url(item.url),
                            course_title=item.course_title,
                            lesson_title=item.title,
                            lesson_number=item.index,
                            metadata={"provider_label": self.label},
                        )
                suffix = f" {last_error}" if last_error else ""
                raise DubLocalError(
                    f"No usable unprotected media could be acquired from this authenticated page.{suffix}"
                )
            finally:
                if cookie_file is not None:
                    try:
                        cookie_file.unlink(missing_ok=True)
                    except OSError:
                        pass
                context.close()


class DomestikaProvider(GenericAuthenticatedProvider):
    provider_id = "domestika"
    label = "Domestika"

    def can_handle(self, locator: str) -> bool:
        try:
            host = (urlparse(locator).hostname or "").lower()
        except Exception:
            return False
        return host == "domestika.org" or host.endswith(".domestika.org")

    def _items(self, page_data: dict[str, Any], original_url: str) -> tuple[SourceItem, ...]:
        current = urlparse(str(page_data.get("page_url") or original_url))
        course_match = re.search(r"/courses/(\d+)", current.path)
        anchors = page_data.get("anchors") or []
        candidates: list[tuple[str, str, float | None]] = []
        seen: set[str] = set()
        for anchor in anchors:
            href = str((anchor or {}).get("href") or "")
            text = re.sub(r"\s+", " ", str((anchor or {}).get("text") or "")).strip()
            if not href or not text:
                continue
            parsed = urlparse(href)
            if not parsed.hostname or not self.can_handle(href):
                continue
            if course_match and f"/courses/{course_match.group(1)}" not in parsed.path:
                continue
            lower_path = parsed.path.lower()
            duration = _duration_seconds(text)
            likely_lesson = duration is not None or any(token in lower_path for token in ("/lessons/", "/lesson/", "/units/", "/unit/", "/course/"))
            if not likely_lesson:
                continue
            canonical = canonical_source_url(href)
            if canonical in seen:
                continue
            seen.add(canonical)
            clean_title = re.sub(r"\s+(?:\d{1,2}:)?\d{1,2}:\d{2}\s*$", "", text).strip() or f"Lesson {len(candidates) + 1}"
            candidates.append((canonical, clean_title, duration))

        course_title = str(page_data.get("title") or "Domestika course")
        if not candidates:
            current_url = canonical_source_url(str(page_data.get("page_url") or original_url))
            return (
                SourceItem(
                    id=_lesson_id(self.provider_id, current_url, 1),
                    url=current_url,
                    title=course_title,
                    index=1,
                    provider_id=self.provider_id,
                    course_title=course_title,
                ),
            )
        return tuple(
            SourceItem(
                id=_lesson_id(self.provider_id, url, index),
                url=url,
                title=title,
                index=index,
                duration_seconds=duration,
                provider_id=self.provider_id,
                course_title=course_title,
            )
            for index, (url, title, duration) in enumerate(candidates, start=1)
        )


_GENERIC = GenericAuthenticatedProvider()
_DOMESTIKA = DomestikaProvider()
AUTHENTICATED_SOURCE_PROVIDERS.register(_GENERIC)
AUTHENTICATED_SOURCE_PROVIDERS.register(_DOMESTIKA, first=True)


def provider_for_url(url: str) -> SourceProvider:
    clean = _valid_web_url(url)
    try:
        return AUTHENTICATED_SOURCE_PROVIDERS.resolve(clean)
    except LookupError as exc:
        raise DubLocalError(str(exc)) from exc


def inspect_authenticated_url(url: str) -> SourceInspection:
    provider = provider_for_url(url)
    try:
        return provider.inspect(url)
    except DubLocalError as exc:
        raise DubLocalError(redact_authenticated_error(str(exc)) or "Authenticated source inspection failed.") from exc


def inspection_summary(inspection: SourceInspection) -> str:
    if inspection.login_required:
        return f"{inspection.provider_label} · login required · {inspection.detail}"
    if inspection.drm_protected:
        return f"{inspection.provider_label} · DRM protected · DubLocal will not bypass DRM."
    states = _manifest_states(inspection.source_url)
    done = sum(1 for item in inspection.items if states.get(item.id) == "done")
    duration = sum(item.duration_seconds or 0.0 for item in inspection.items)
    duration_note = ""
    if duration:
        minutes = int(round(duration / 60.0))
        duration_note = f" · ~{minutes} min"
    resume = f" · resume: {done}/{len(inspection.items)} already completed" if done else ""
    return f"{inspection.provider_label} · {inspection.title} · {len(inspection.items)} lesson(s){duration_note}{resume}"


def _course_output_root(inspection: SourceInspection) -> Path:
    movies = Path.home() / "Movies"
    base = movies / "DubLocal" if movies.exists() else Path.home() / "DubLocal Outputs"
    root = base / _safe_component(inspection.provider_label, "Website") / _safe_component(inspection.title, "Course")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _copy_atomic(source: Path, destination: Path) -> Path:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise DubLocalError(f"Generated output is no longer available: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(f".{destination.name}.dublocal-tmp")
    shutil.copy2(source, temp)
    os.replace(temp, destination)
    return destination


def _lesson_stem(item: SourceItem) -> str:
    return f"{max(1, item.index):02d} - {_safe_component(item.title, f'Lesson {item.index}') }"


def publish_course_result(
    inspection: SourceInspection,
    item: SourceItem,
    result: MagicFlowResult,
) -> tuple[tuple[str, Path], ...]:
    root = _course_output_root(inspection)
    stem = _lesson_stem(item)
    published: list[tuple[str, Path]] = []
    if result.source_subtitle:
        language = safe_language_suffix(result.source_language)
        published.append(("Source subtitles", _copy_atomic(Path(result.source_subtitle), root / f"{stem}.{language}.srt")))
    if result.translated_subtitle:
        language = safe_language_suffix(result.target_language)
        published.append(("Translated subtitles", _copy_atomic(Path(result.translated_subtitle), root / f"{stem}.{language}.srt")))
    if result.voice_wav:
        language = safe_language_suffix(result.target_language or result.source_language)
        published.append(("Voice WAV", _copy_atomic(Path(result.voice_wav), root / f"{stem}.voice.{language}.wav")))
    if result.media_output:
        source = Path(result.media_output)
        suffix = source.suffix.lower() or ".mkv"
        lower = source.name.lower()
        if ".share." in lower:
            middle = f".share.{safe_language_suffix(result.target_language or result.source_language)}"
        elif ".subtitles." in lower:
            middle = f".subtitles.{safe_language_suffix(result.target_language or result.source_language)}"
        else:
            middle = f".dub.{safe_language_suffix(result.target_language or result.source_language)}"
        published.append(("Media", _copy_atomic(source, root / f"{stem}{middle}{suffix}")))
    return tuple(published)


def _selected_items(inspection: SourceInspection, selected_ids: list[str] | tuple[str, ...] | None) -> tuple[SourceItem, ...]:
    states = _manifest_states(inspection.source_url)
    if selected_ids is None:
        items = list(inspection.items)
    else:
        wanted = {str(value) for value in selected_ids}
        items = [item for item in inspection.items if item.id in wanted]
    # Resume is deliberately conservative: a completed lesson is never reprocessed.
    return tuple(item for item in items if states.get(item.id) != "done")


def run_authenticated_magic_queue(
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
    check_cancelled()
    if not rights_confirmed:
        raise DubLocalError(
            "Confirm that you have legitimate access to this content and the right or legal authority to process it for your intended use."
        )
    if inspection.login_required:
        raise DubLocalError("The authenticated website session is not signed in yet.")
    if inspection.drm_protected:
        raise DubLocalError("This source appears DRM protected. DubLocal does not bypass DRM.")
    selected = _selected_items(inspection, selected_ids)
    if not selected:
        raise DubLocalError("There are no pending selected lessons. Completed lessons are preserved and are not reprocessed.")

    provider = provider_for_url(inspection.source_url)
    completed: list[QueueItemResult] = []
    total = len(selected)
    for index, item in enumerate(selected):
        queue_item = QueueItem(SOURCE_TYPE, item.url, f"{item.index:02d} · {item.title}")
        if cancel_requested():
            for tail in selected[index:]:
                tail_q = QueueItem(SOURCE_TYPE, tail.url, f"{tail.index:02d} · {tail.title}")
                message = "Not started because the queue was stopped."
                completed.append(QueueItemResult(tail_q, "cancelled", None, (), error=message))
                _update_course_state(inspection, tail, "cancelled", error=message)
            break
        prefix = f"{index + 1}/{total} · {item.title}"

        def overall(fraction: float, label: str) -> None:
            check_cancelled()
            _notify(progress_callback, (index + max(0.0, min(1.0, fraction))) / total, f"{prefix} · {label}")

        _update_course_state(inspection, item, "running")
        try:
            _notify(progress_callback, index / total, f"{prefix} · acquiring authorised source")
            acquired = provider.acquire(item, progress_callback=lambda f, l: overall(f * 0.22, l))
            check_cancelled()
            result = run_magic_flow(
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
            published = publish_course_result(inspection, item, result)
            completed.append(QueueItemResult(queue_item, "done", result, published))
            _update_course_state(inspection, item, "done", outputs=published)
            _notify(progress_callback, (index + 1) / total, f"{prefix} · complete")
        except JobCancelled as exc:
            message = redact_authenticated_error(str(exc) or "Stopped by user.") or "Stopped by user."
            completed.append(QueueItemResult(queue_item, "cancelled", None, (), error=message))
            _update_course_state(inspection, item, "cancelled", error=message)
            for tail in selected[index + 1 :]:
                tail_q = QueueItem(SOURCE_TYPE, tail.url, f"{tail.index:02d} · {tail.title}")
                tail_message = "Not started because the queue was stopped."
                completed.append(QueueItemResult(tail_q, "cancelled", None, (), error=tail_message))
                _update_course_state(inspection, tail, "cancelled", error=tail_message)
            break
        except Exception as exc:
            if cancel_requested():
                message = "Stopped by user."
                completed.append(QueueItemResult(queue_item, "cancelled", None, (), error=message))
                _update_course_state(inspection, item, "cancelled", error=message)
                break
            message = redact_authenticated_error(str(exc)) or "Authenticated processing failed."
            completed.append(QueueItemResult(queue_item, "failed", None, (), error=message))
            _update_course_state(inspection, item, "failed", error=message)
            _notify(progress_callback, (index + 1) / total, f"{prefix} · failed · continuing")
    return BatchFlowResult(tuple(completed))


def acquire_single_authenticated_source(
    url: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> AcquiredMedia:
    inspection = inspect_authenticated_url(url)
    if inspection.login_required:
        raise DubLocalError("Sign in through the dedicated DubLocal browser first.")
    if inspection.drm_protected:
        raise DubLocalError("This source appears DRM protected. DubLocal does not bypass DRM.")
    if len(inspection.items) != 1:
        raise DubLocalError(
            "Advanced mode accepts one authenticated lesson at a time. Paste a direct lesson URL, or use Standard → Course / Website for the full course."
        )
    provider = provider_for_url(url)
    return provider.acquire(inspection.items[0], progress_callback=progress_callback)


def _main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[1] == "--login":
        _login_helper(argv[2], argv[3])
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
