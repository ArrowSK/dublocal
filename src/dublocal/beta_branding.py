from __future__ import annotations

from typing import Any

import gradio as gr


_INSTALLED = False

_BRAND_CSS = r"""
.dl-header {
  display: flex !important;
  align-items: center !important;
  gap: 14px !important;
}
.dl-app-mark {
  width: 58px;
  height: 58px;
  flex: 0 0 58px;
  filter: drop-shadow(0 0 12px rgba(66, 239, 131, 0.10));
}
.dl-app-mark svg {
  display: block;
  width: 100%;
  height: 100%;
}
.dl-brand-copy {
  min-width: 0;
}
@media (max-width: 640px) {
  .dl-header { gap: 10px !important; }
  .dl-app-mark { width: 46px; height: 46px; flex-basis: 46px; }
}
"""

# This deliberately mirrors the established assets/macos/DubLocal.svg geometry rather
# than introducing a second visual identity. Keeping the mark inline means the local
# browser UI does not need another Gradio-accessible file path just to render branding.
_MARK = """<svg viewBox="0 0 1024 1024" aria-hidden="true" focusable="false">
<defs>
  <linearGradient id="dl-bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#101b15"/><stop offset="0.55" stop-color="#07100a"/><stop offset="1" stop-color="#030604"/>
  </linearGradient>
  <linearGradient id="dl-green" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#a8ffbf"/><stop offset="0.45" stop-color="#60f285"/><stop offset="1" stop-color="#21bf58"/>
  </linearGradient>
</defs>
<rect x="48" y="48" width="928" height="928" rx="228" fill="url(#dl-bg)"/>
<rect x="70" y="70" width="884" height="884" rx="206" fill="none" stroke="#173923" stroke-width="12"/>
<g fill="none" stroke="url(#dl-green)" stroke-linecap="round" stroke-linejoin="round">
  <path d="M365 260v504" stroke-width="72"/><path d="M365 260h126c174 0 284 99 284 252S665 764 491 764H365" stroke-width="72"/>
</g>
<g fill="url(#dl-green)">
  <rect x="245" y="438" width="24" height="148" rx="12"/><rect x="286" y="390" width="24" height="244" rx="12"/>
  <rect x="327" y="348" width="24" height="328" rx="12"/><rect x="368" y="408" width="24" height="208" rx="12"/>
  <rect x="409" y="458" width="24" height="108" rx="12"/>
</g>
</svg>"""


def branded_header(value: str) -> str:
    """Add the established DubLocal mark to the existing product header only."""

    if 'class="dl-header"' not in value or 'class="dl-brand"' not in value:
        return value
    if 'class="dl-app-mark"' in value:
        return value
    marker = '<div class="dl-header">'
    replacement = (
        marker
        + f'<div class="dl-app-mark" aria-label="DubLocal logo">{_MARK}</div>'
        + '<div class="dl-brand-copy">'
    )
    result = value.replace(marker, replacement, 1)
    # The current header has exactly brand + subtitle children. Close the new copy
    # wrapper immediately before the established header closing tag.
    result = result.replace(
        '<div class="dl-subtitle">Subtitles, contextual translation and local AI voice-over — processed on your Mac.</div>\n            </div>',
        '<div class="dl-subtitle">Subtitles, contextual translation and local AI voice-over — processed on your Mac.</div></div>\n            </div>',
        1,
    )
    return result


def install_beta_branding(product_ui: Any) -> None:
    """Add packaged-app branding without redesigning or duplicating the product UI."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_build = product_ui.build_app
    product_ui.MATRIX_CSS = product_ui.MATRIX_CSS + _BRAND_CSS

    def build_app_with_branding():
        original_html = gr.HTML

        def html_with_branding(value=None, *args, **kwargs):
            if isinstance(value, str):
                value = branded_header(value)
            return original_html(value, *args, **kwargs)

        gr.HTML = html_with_branding
        try:
            return original_build()
        finally:
            gr.HTML = original_html

    product_ui.build_app = build_app_with_branding
