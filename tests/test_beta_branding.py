from __future__ import annotations

from dublocal.beta_branding import branded_header


def test_branding_adds_established_logo_to_product_header() -> None:
    source = """
    <div class="dl-header">
      <div class="dl-brand">DubLocal<span class="dl-cursor">_</span><span class="dl-local">LOCAL</span></div>
      <div class="dl-subtitle">Subtitles, contextual translation and local AI voice-over — processed on your Mac.</div>
    </div>
    """

    result = branded_header(source)

    assert 'class="dl-app-mark"' in result
    assert "<svg" in result
    assert 'class="dl-brand-copy"' in result
    assert "DubLocal" in result
    assert result.count('class="dl-app-mark"') == 1


def test_branding_is_idempotent_and_does_not_touch_other_html() -> None:
    unrelated = '<div class="dl-note">DubLocal</div>'
    assert branded_header(unrelated) == unrelated

    source = """
    <div class="dl-header">
      <div class="dl-brand">DubLocal</div>
      <div class="dl-app-mark"><svg></svg></div>
    </div>
    """
    assert branded_header(source) == source
