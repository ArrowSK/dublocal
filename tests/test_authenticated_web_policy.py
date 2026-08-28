from __future__ import annotations

from dublocal import authenticated_web as web
from dublocal.authenticated_web_policy import (
    install_authenticated_web_policy,
    redact_authenticated_error,
)
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
    install_authenticated_web_policy()
    monkeypatch.setattr(web, "course_manifest_root", lambda: tmp_path)
    inspection = _inspection()
    assert web._selected_items(inspection, []) == ()
    assert [item.id for item in web._selected_items(inspection, ["two"])] == ["two"]


def test_authenticated_errors_redact_signed_url_credentials() -> None:
    source = (
        "download failed: https://cdn.example.com/master.m3u8?token=very-secret&quality=hd&Signature=abc123"
    )
    safe = redact_authenticated_error(source)
    assert safe is not None
    assert "very-secret" not in safe
    assert "abc123" not in safe
    assert "REDACTED" in safe
    assert "quality=hd" in safe
