from __future__ import annotations

from dublocal.progress import ProgressEstimator, format_duration
from dublocal.transcription import _PROGRESS_RE


def test_format_duration_is_human_readable():
    assert format_duration(None) == "estimating…"
    assert format_duration(42) == "42s"
    assert format_duration(125) == "2m 05s"
    assert format_duration(3720) == "1h 02m"


def test_progress_estimator_reports_percent_and_eta(monkeypatch):
    monkeypatch.setattr("dublocal.progress.time.monotonic", lambda: 20.0)
    estimator = ProgressEstimator(started_at=0.0)

    assert estimator.message(0.5, "Working") == "Working · 50% · 20s remaining"
    assert estimator.message(1.0, "Working") == "Working · 100% · done"


def test_whisper_progress_parser_accepts_official_cli_shape():
    match = _PROGRESS_RE.search("whisper_print_progress_callback: progress =  35%")
    assert match is not None
    assert int(match.group(1)) == 35
