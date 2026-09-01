from __future__ import annotations

from dublocal import authenticated_web as web
from dublocal.source_providers import SourceInspection, SourceItem


def _inspection() -> SourceInspection:
    return SourceInspection(
        provider_id="domestika",
        provider_label="Domestika",
        source_url="https://www.domestika.org/en/courses/123-watercolour?token=secret",
        title="Watercolour",
        items=(
            SourceItem(
                id="one",
                url="https://www.domestika.org/en/courses/123-watercolour/lessons/1",
                title="Introduction",
                index=1,
                provider_id="domestika",
                course_title="Watercolour",
            ),
            SourceItem(
                id="two",
                url="https://www.domestika.org/en/courses/123-watercolour/lessons/2",
                title="Materials",
                index=2,
                provider_id="domestika",
                course_title="Watercolour",
            ),
        ),
    )


def test_domestika_is_selected_before_generic_provider() -> None:
    provider = web.provider_for_url("https://www.domestika.org/en/courses/123-watercolour")
    assert provider.provider_id == "domestika"
    assert web.provider_for_url("https://training.example.com/lesson/1").provider_id == "generic-authenticated-web"


def test_signed_url_values_are_redacted_and_not_used_for_persistent_identity() -> None:
    source = "https://media.example.com/video.m3u8?token=topsecret&Signature=abc123&quality=hd#part"
    redacted = web.sanitize_url(source)
    assert "topsecret" not in redacted
    assert "abc123" not in redacted
    assert "REDACTED" in redacted
    assert "quality=hd" in redacted
    canonical = web.canonical_source_url(source)
    assert "token=" not in canonical
    assert "Signature=" not in canonical
    assert canonical == "https://media.example.com/video.m3u8?quality=hd"


def test_drm_manifest_detection_is_conservative() -> None:
    clear_hls = "#EXTM3U\n#EXT-X-TARGETDURATION:10\nsegment01.ts\n"
    encrypted_hls = '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\nsegment01.ts\n'
    clear_mpd = "<MPD><Period><AdaptationSet /></Period></MPD>"
    protected_mpd = '<MPD><Period><AdaptationSet><ContentProtection schemeIdUri="urn:uuid:test"/></AdaptationSet></Period></MPD>'
    assert not web._manifest_is_protected(clear_hls, "https://example.com/master.m3u8")
    assert web._manifest_is_protected(encrypted_hls, "https://example.com/master.m3u8")
    assert not web._manifest_is_protected(clear_mpd, "https://example.com/manifest.mpd")
    assert web._manifest_is_protected(protected_mpd, "https://example.com/manifest.mpd")


def test_course_resume_excludes_completed_lessons(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(web, "course_manifest_root", lambda: tmp_path)
    inspection = _inspection()
    assert web.pending_item_ids(inspection) == ("one", "two")
    web._update_course_state(inspection, inspection.items[0], "done")
    assert web.pending_item_ids(inspection) == ("two",)
    assert web.reset_course_resume(inspection.source_url)
    assert web.pending_item_ids(inspection) == ("one", "two")
