from __future__ import annotations

import pytest

from dublocal import authenticated_web as web
from dublocal.media import DubLocalError
from dublocal.source_providers import SourceInspection, SourceItem


def _inspection() -> SourceInspection:
    return SourceInspection(
        provider_id="domestika",
        provider_label="Domestika",
        source_url="https://www.domestika.org/courses/1",
        title="Course",
        items=(
            SourceItem("one", "https://www.domestika.org/courses/1/lesson/1", "One", 1),
            SourceItem("two", "https://www.domestika.org/courses/1/lesson/2", "Two", 2),
        ),
    )


def test_explicit_empty_selection_never_expands_to_all(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(web, "course_manifest_root", lambda: tmp_path)
    inspection = _inspection()
    assert web._selected_items(inspection, []) == ()
    assert [item.id for item in web._selected_items(inspection, ["two"])] == ["two"]
    assert [item.id for item in web._selected_items(inspection, None)] == ["one", "two"]


def test_authenticated_errors_redact_signed_url_credentials() -> None:
    source = (
        "download failed: https://cdn.example.com/master.m3u8?token=very-secret&quality=hd&Signature=abc123"
    )
    safe = web.redact_authenticated_error(source)
    assert safe is not None
    assert "very-secret" not in safe
    assert "abc123" not in safe
    assert "REDACTED" in safe
    assert "quality=hd" in safe


def test_canonical_identity_preserves_non_secret_query_routing() -> None:
    canonical = web.canonical_source_url(
        "https://training.example.com/watch?lesson=42&token=secret&lang=fr#chapter"
    )
    assert canonical == "https://training.example.com/watch?lesson=42&lang=fr"


def test_signed_hls_url_is_still_inspected_for_encryption() -> None:
    calls: list[str] = []

    class Response:
        def text(self) -> str:
            return '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\nsegment.ts\n'

    class Request:
        def get(self, url: str, timeout: int):
            calls.append(url)
            assert timeout == 20_000
            return Response()

    class Context:
        request = Request()

    provider = web.GenericAuthenticatedProvider()
    signed = "https://cdn.example.com/master.m3u8?token=secret&Signature=abc123"
    with pytest.raises(DubLocalError, match="encrypted/DRM-protected"):
        provider._check_manifest(Context(), signed)
    assert calls == [signed]


def test_persisted_course_error_is_redacted(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(web, "course_manifest_root", lambda: tmp_path)
    inspection = _inspection()
    error = "failed https://cdn.example.com/file.mp4?token=secret&lesson=1"

    web._update_course_state(inspection, inspection.items[0], "failed", error=error)

    payload = web._read_manifest(inspection.source_url)
    persisted = payload["items"]["one"]["error"]
    assert "secret" not in persisted
    assert "token=REDACTED" in persisted
    assert "lesson=1" in persisted
