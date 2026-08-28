"""DubLocal package."""

__version__ = "0.5.2.dev0"

# Install transcription safety/refinement layers before UI modules import transcription
# symbols. This keeps local Whisper behavior identical for the launcher, direct Python
# entry points and tests while preserving the stable transcription engine API.
from .transcription_guard import install_transcription_guard as _install_transcription_guard

_install_transcription_guard()
del _install_transcription_guard

from .transcription_v053 import install_transcription_refinements as _install_transcription_refinements

_install_transcription_refinements()
del _install_transcription_refinements
