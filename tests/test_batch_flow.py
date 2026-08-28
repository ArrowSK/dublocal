from __future__ import annotations

from pathlib import Path

import dublocal.batch_flow as batch
from dublocal.magic_flow import MagicFlowResult


def _magic_result(tmp_path: Path, stem: str = "Movie") -> MagicFlowResult:
    source = tmp_path / f"{stem}.en.srt"
    translated = tmp_path / f"{stem}.ru.srt"
    voice = tmp_path / "voice.wav"
    media = tmp_path / f"{stem}.dub.ru.mkv"
    for path in (source, translated, voice, media):
        path.write_bytes(b"output")
    return MagicFlowResult(
        source_subtitle=source,
        translated_subtitle=translated,
        voice_wav=voice,
        media_output=media,
        source_language="en",
        target_language="ru",
        decision="test",
        status="ok",
    )


def test_local_queue_accepts_multiple_files_and_deduplicates(tmp_path: Path) -> None:
    first = tmp_path / "one.mp4"
    second = tmp_path / "two.mov"
    first.write_bytes(b"1")
    second.write_bytes(b"2")

    items = batch.local_queue_items([str(first), str(second), str(first)])

    assert [Path(item.locator).name for item in items] == ["one.mp4", "two.mov"]
    assert all(item.source_type == "Local file" for item in items)


def test_watch_url_with_playlist_parameter_stays_one_video(monkeypatch) -> None:
    class ForbiddenYDL:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("single watch URL must not enumerate the playlist")

    monkeypatch.setattr(batch, "YoutubeDL", ForbiddenYDL)
    url = "https://www.youtube.com/watch?v=abc123&list=PLxyz"

    items = batch.expand_youtube_queue(url)

    assert len(items) == 1
    assert items[0].locator == url


def test_playlist_expands_to_ordered_unique_video_jobs(monkeypatch) -> None:
    class FakeYDL:
        def __init__(self, options):
            assert options["extract_flat"] == "in_playlist"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, _url, download=False):
            assert download is False
            return {
                "_type": "playlist",
                "entries": [
                    {"id": "aaa111", "title": "First"},
                    {"id": "bbb222", "title": "Second"},
                    {"id": "aaa111", "title": "Duplicate"},
                    None,
                ],
            }

    monkeypatch.setattr(batch, "YoutubeDL", FakeYDL)

    items = batch.expand_youtube_queue("https://www.youtube.com/playlist?list=PLtest")

    assert [item.label for item in items] == ["First", "Second"]
    assert [item.locator for item in items] == [
        "https://www.youtube.com/watch?v=aaa111",
        "https://www.youtube.com/watch?v=bbb222",
    ]


def test_local_results_are_saved_next_to_each_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    work = tmp_path / "work"
    source_dir.mkdir()
    work.mkdir()
    local = source_dir / "Family Clip.mp4"
    local.write_bytes(b"media")
    result = _magic_result(work, "Family Clip")
    item = batch.QueueItem("Local file", str(local), local.name)

    published = dict(batch.publish_magic_result(item, result))

    assert published["Source subtitles"] == source_dir / "Family Clip.en.srt"
    assert published["Translated subtitles"] == source_dir / "Family Clip.ru.srt"
    assert published["Voice WAV"] == source_dir / "Family Clip.voice.ru.wav"
    assert published["Media"] == source_dir / "Family Clip.dub.ru.mkv"
    assert all(path.is_file() for path in published.values())


def test_queue_is_sequential_and_continues_after_failure(monkeypatch, tmp_path: Path) -> None:
    files = []
    for name in ("one.mp4", "two.mp4", "three.mp4"):
        path = tmp_path / name
        path.write_bytes(b"media")
        files.append(str(path))

    calls: list[str] = []

    def fake_run_magic_flow(**kwargs):
        name = Path(kwargs["local_file"]).name
        calls.append(name)
        if name == "two.mp4":
            raise RuntimeError("broken input")
        work = tmp_path / f"work-{name}"
        work.mkdir()
        return _magic_result(work, Path(name).stem)

    monkeypatch.setattr(batch, "run_magic_flow", fake_run_magic_flow)
    monkeypatch.setattr(
        batch,
        "publish_magic_result",
        lambda item, result: (("Media", Path(item.locator).with_suffix(".done")),),
    )

    result = batch.run_magic_queue(
        source_type="Local file",
        youtube_url="",
        local_files=files,
        rights_confirmed=True,
        target_language="ru",
        tasks=["subtitles"],
    )

    assert calls == ["one.mp4", "two.mp4", "three.mp4"]
    assert [item.state for item in result.items] == ["done", "failed", "done"]
    assert result.items[1].error == "broken input"
