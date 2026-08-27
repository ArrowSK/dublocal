"""DubLocal package."""

__version__ = "0.5.2.dev0"

# Install small runtime safety guards before UI modules import transcription symbols.
# This keeps the fix global for the launcher, CLI and tests without redesigning the
# working transcription module during the v0.5.2 hotfix.
from .transcription_guard import install_transcription_guard as _install_transcription_guard

_install_transcription_guard()
del _install_transcription_guard
