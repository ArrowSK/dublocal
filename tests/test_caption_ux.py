from dublocal.caption_ux import caption_inventory_text, curate_caption_info


def test_youtube_original_auto_is_shown_and_mass_translations_are_hidden():
    tracks = [
        {
            "value": "yt:auto:en-orig",
            "label": "en-orig · automatic captions",
            "language": "en-orig",
            "source": "auto",
            "formats": [{"name": "English (Original)", "ext": "vtt", "url": "https://x/en"}],
        },
        {
            "value": "yt:auto:aa",
            "label": "aa · automatic captions",
            "language": "aa",
            "source": "auto",
            "formats": [{"name": "Afar", "ext": "vtt", "url": "https://x/aa"}],
        },
        {
            "value": "yt:auto:es",
            "label": "es · automatic captions",
            "language": "es",
            "source": "auto",
            "formats": [{"name": "Spanish", "ext": "vtt", "url": "https://x/es"}],
        },
    ]

    info = curate_caption_info({"kind": "youtube", "subtitle_tracks": tracks})

    assert [track["value"] for track in info["subtitle_tracks"]] == ["yt:auto:en-orig"]
    assert info["subtitle_tracks"][0]["label"] == "English · Automatic captions · original"
    assert info["caption_hidden_count"] == 2
    assert len(info["subtitle_tracks_all"]) == 3
    summary = caption_inventory_text(info)
    assert "English" in summary
    assert "2 YouTube machine-translated variants are hidden" in summary
    assert "aa" not in summary


def test_creator_captions_and_original_auto_are_both_visible():
    info = curate_caption_info(
        {
            "kind": "youtube",
            "subtitle_tracks": [
                {
                    "value": "yt:manual:es",
                    "language": "es",
                    "source": "manual",
                    "formats": [{"name": "Spanish", "ext": "vtt", "url": "https://x/es"}],
                },
                {
                    "value": "yt:auto:en-orig",
                    "language": "en-orig",
                    "source": "auto",
                    "formats": [{"name": "English (Original)", "ext": "vtt", "url": "https://x/en"}],
                },
                {
                    "value": "yt:auto:de",
                    "language": "de",
                    "source": "auto",
                    "formats": [{"name": "German", "ext": "vtt", "url": "https://x/de"}],
                },
            ],
        }
    )

    labels = [track["label"] for track in info["subtitle_tracks"]]
    assert labels == ["Spanish · Creator captions", "English · Automatic captions · original"]
    assert info["caption_hidden_count"] == 1


def test_local_subtitle_labels_are_human_readable():
    info = curate_caption_info(
        {
            "kind": "local",
            "subtitle_tracks": [
                {
                    "value": "local:2",
                    "language": "eng",
                    "codec": "subrip",
                    "title": "English",
                    "text_capable": True,
                },
                {
                    "value": "local:3",
                    "language": "deu",
                    "codec": "hdmv_pgs_subtitle",
                    "title": "",
                    "text_capable": False,
                },
            ],
        }
    )

    assert info["subtitle_tracks"][0]["label"] == "English · Text subtitles"
    assert info["subtitle_tracks"][1]["label"].startswith("German · Image subtitles")
    assert info["caption_hidden_count"] == 0
