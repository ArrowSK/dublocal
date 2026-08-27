from pathlib import Path

from dublocal.output_naming import dubbed_media_path, friendly_subtitle_path, safe_media_stem


def test_local_filename_becomes_readable_language_suffixed_subtitle(tmp_path: Path):
    source = tmp_path / "captions.srt"
    source.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    info = {"kind": "local", "path": "/tmp/My Movie (2026).mkv", "title": "My Movie (2026).mkv"}
    output = friendly_subtitle_path(source, info, "en")
    assert output.name == "My Movie (2026).en.srt"
    assert output.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_youtube_title_is_sanitized_and_used_for_dubbed_media(tmp_path: Path):
    info = {"kind": "youtube", "title": 'A Song: Live / 2026?'}
    assert safe_media_stem(info) == "A Song Live 2026"
    output = dubbed_media_path(tmp_path, info, "es", "mkv")
    assert output.name == "A Song Live 2026.dub.es.mkv"
