from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir

from .adaptive_audio import install_adaptive_audio_refinement
from .job_cache import prune_job_cache
from .m53 import install_runtime_refinements
from .transcription_v053 import install_transcription_refinements
from . import tts_provider_refinement
from .tts_runtime_compat import install_russian_runtime_compat
from .v060_refinements import install_audio_balance_refinement

# Kokoro 0.9.x currently requires Python <3.13. DubLocal itself may run on
# Python 3.13, so Russian TTS gets a compatible isolated 3.11/3.12 runtime
# before provider routing captures its preparation/generation hooks.
install_russian_runtime_compat(tts_provider_refinement)

# Provider routing must be installed before native_tts_timing is imported: that
# module captures the then-current TTS generator as its stable synthesis backend.
tts_provider_refinement.install_tts_provider_refinement()
from .native_tts_timing import install_native_timing_refinement

# Install wrappers before UI modules import app/progress-operation/render symbols.
install_transcription_refinements()
install_native_timing_refinement()
install_adaptive_audio_refinement()

from .product_ui import MATRIX_CSS, build_app


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _gradio_allowed_paths() -> list[str]:
    """Expose only DubLocal's generated job files to the local Gradio UI."""

    jobs_dir = Path(user_cache_dir("DubLocal")) / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return [str(jobs_dir.resolve())]


def main() -> None:
    port = int(os.getenv("DUBLOCAL_PORT", "7861"))
    inbrowser = _env_bool("DUBLOCAL_INBROWSER", True)

    # Generated SRT/WAV/intermediate media live in the macOS cache, not the repo or
    # user documents. Prune stale/oversized jobs before a new session starts.
    prune_job_cache()

    # Keep the established lightweight mixer as the universal fallback. The adaptive
    # renderer swaps in vocal separation only for the current render when requested or
    # when Simple/Auto strongly identifies music and the optional runtime is prepared.
    install_audio_balance_refinement()
    install_runtime_refinements()

    demo = build_app()
    demo.queue(default_concurrency_limit=1).launch(
        inbrowser=inbrowser,
        server_name="127.0.0.1",
        server_port=port,
        show_error=False,
        css=MATRIX_CSS,
        allowed_paths=_gradio_allowed_paths(),
    )


if __name__ == "__main__":
    main()
