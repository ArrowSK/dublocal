"""Compatibility alias for the consolidated detailed UI.

The v0.4.2 hardware-aware translation behavior now lives in
:mod:`dublocal.detailed_ui`. This module remains temporarily for old imports only.
"""

from __future__ import annotations

import sys as _sys

from . import detailed_ui as _detailed_ui

_sys.modules[__name__] = _detailed_ui
