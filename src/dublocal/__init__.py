"""DubLocal package."""

__version__ = "0.6.0b3"

# Install transcription safety guards before UI modules import transcription symbols.
# The guard keeps local Whisper fail-safe behavior consistent for the launcher, CLI
# and tests while preserving the stable transcription engine API.
from .transcription_guard import install_transcription_guard as _install_transcription_guard

_install_transcription_guard()
del _install_transcription_guard
