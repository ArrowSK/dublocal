from __future__ import annotations

from . import m53


# A married consumer mix still contains the original dialogue/singing. Returning that
# mix close to full programme level between dubbed lines creates a very obvious jump.
# Keep the source as a quieter continuous background bed; M5.3 still applies its much
# stronger subtitle-window suppression while the dub is active.
_STABLE_ORIGINAL_BED_GAIN = 0.45


def install_audio_balance_refinement() -> None:
    """Apply the v0.6 resting soundtrack level without adding any extra DSP/model."""

    m53._ORIGINAL_BED_GAIN = _STABLE_ORIGINAL_BED_GAIN
