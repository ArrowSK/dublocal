"""Compatibility alias for the consolidated detailed UI.

New code should import :mod:`dublocal.detailed_ui` directly. This alias is kept only so
older development imports and saved environments do not break during the 0.6 transition.
"""

from __future__ import annotations

import sys as _sys

from . import detailed_ui as _detailed_ui

_sys.modules[__name__] = _detailed_ui
