from __future__ import annotations

from pathlib import Path

import pytest

from dublocal import authenticated_web as web
from dublocal.magic_flow import MagicFlowResult
from dublocal.media import DubLocalError
from dublocal.source_providers import AcquiredMedia, SourceInspection, SourceItem


def _inspection(url: str = "https://course.example.com/course/1") -> SourceInspection:
    return SourceInspection(
        provider_id="fake",
        provider_label="Course Site",
        source_url=url,
        title="French Course",
        items=(
            SourceItem("one", f"{url}/lesson/1", "One", 1, provider_id="fake", course_title="French Course"),
            SourceItem("two", f"{url}/lesson/2", "Two", 2, provider_id="fake", course_title="French Course"),
        ),
    )


class _FakeProvider:
    def __init__(self, root: Path, calls: list[str]) -> None:
        self.root = root
        self.calls = calls

    def acquire(self, item: SourceItem, *, progress_callback=None) -> AcquiredMedia:
        self.calls.append(f"acquire:{item.id}")
        path = self.root / f"{item.id}.mp4"
        path.write_bytes(b"media")
        if progress_callback:
            progress_callback(1.0, "ready")
        return AcquiredMedia(
            path=path,
            title=item.title,
            provider_id="fake",
            source_url=item.url,
            course_title=item.course_title,
            lesson_title=item.title,
            lesson_number=item.index,
            metadata={"provider_label": "Course Site"},
        )


def _result(root: Path, lesson: str) -> MagicFlowResult:
    subtitle = root / f"{lesson}.en.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    return MagicFlowResult(
        source_subtitle=subtitle,
        translated_subtitle=None,
        voice_wav=None,
        media_output=None,
        source_language="en",
        target_language="en",
        decision="test",
        status="ok",
    )


def test_authenticated_course_queue_is_sequential_and_resumable(monkeypatch, tmp_path: Path) -> None:
    manifest_root = tmp_path / "manifests"
    manifest_root.mkdir()
    monkeypatch.setattr(web, "course_manifest_root", lambda: manifest_root)
    calls: list[str] = []
    provider = _FakeProvider(tmp_path, calls)
    monkeypatch.setattr(web, "provider_for_url", lambda _url: provider)

    def fake_magic_flow(*, local_file, progress_callback=None, **_kwargs):
        lesson = Path(local_file).stem
        calls.append(f"process:{lesson}")
        if progress_callback:
            progress_callback(1.0, "processed")
        return _result(tmp_path, lesson)

    monkeypatch.setattr(web, "run_magic_flow", fake_magic_flow)
    monkeypatch.setattr(web, "publish_course_result", lambda *_args, **_kwargs: ())

    inspection = _inspection()
    result = web.run_authenticated_magic_queue(
        inspection=inspection,
        selected_ids=["one", "two"],
        rights_confirmed=True,
        target_language="en",
        tasks=["subtitles"],
    )
    assert [item.state for item in result.items] == ["done", "done"]
    assert calls == ["acquire:one", "process:one", "acquire:two", "process:two"]
    assert web.pending_item_ids(inspection) == ()

    with pytest.raises(DubLocalError, match="no pending selected lessons"):
        web.run_authenticated_magic_queue(
            inspection=inspection,
            selected_ids=["one", "two"],
            rights_confirmed=True,
            target_language="en",
            tasks=["subtitles"],
        )
    assert calls == ["acquire:one", "process:one", "acquire:two", "process:two"]


def test_one_failed_lesson_does_not_stop_the_course(monkeypatch, tmp_path: Path) -> None:
    manifest_root = tmp_path / "manifests"
    manifest_root.mkdir()
    monkeypatch.setattr(web, "course_manifest_root", lambda: manifest_root)
    calls: list[str] = []
    provider = _FakeProvider(tmp_path, calls)
    monkeypatch.setattr(web, "provider_for_url", lambda _url: provider)

    def fake_magic_flow(*, local_file, **_kwargs):
        lesson = Path(local_file).stem
        calls.append(f"process:{lesson}")
        if lesson == "one":
            raise RuntimeError("bad lesson")
        return _result(tmp_path, lesson)

    monkeypatch.setattr(web, "run_magic_flow", fake_magic_flow)
    monkeypatch.setattr(web, "publish_course_result", lambda *_args, **_kwargs: ())

    result = web.run_authenticated_magic_queue(
        inspection=_inspection("https://course.example.com/course/failure"),
        selected_ids=["one", "two"],
        rights_confirmed=True,
        target_language="en",
        tasks=["subtitles"],
    )
    assert [item.state for item in result.items] == ["failed", "done"]
    assert calls == ["acquire:one", "process:one", "acquire:two", "process:two"]
