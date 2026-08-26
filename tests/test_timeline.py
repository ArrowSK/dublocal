from dublocal.timeline import (
    Segment,
    format_timestamp,
    parse_srt,
    parse_timestamp,
    segments_to_srt,
)


def test_parse_timestamp_round_trip():
    value = parse_timestamp("01:02:03,456")
    assert value == 3_723_456
    assert format_timestamp(value) == "01:02:03,456"


def test_parse_srt_preserves_multiline_text_and_milliseconds():
    text = """1
00:00:01,250 --> 00:00:03,900
Hello world.
Second line.

2
00:00:05,000 --> 00:00:06,125
Next segment.
"""

    segments = parse_srt(text)

    assert len(segments) == 2
    assert segments[0].index == 1
    assert segments[0].start_ms == 1250
    assert segments[0].end_ms == 3900
    assert segments[0].duration_ms == 2650
    assert segments[0].text == "Hello world.\nSecond line."
    assert segments[1].start_ms == 5000
    assert segments[1].end_ms == 6125


def test_segments_to_srt_round_trips_exact_timings():
    original = [
        Segment(index=7, start_ms=1250, end_ms=3900, text="Translated line."),
        Segment(index=8, start_ms=5000, end_ms=6125, text="Second translated line."),
    ]

    serialized = segments_to_srt(original)
    restored = parse_srt(serialized)

    assert [(item.index, item.start_ms, item.end_ms, item.text) for item in restored] == [
        (7, 1250, 3900, "Translated line."),
        (8, 5000, 6125, "Second translated line."),
    ]
