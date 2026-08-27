from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


ProgressCallback = Callable[[float, str], None]


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "estimating…"
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


@dataclass
class ProgressEstimator:
    """Convert real fractional progress into a user-facing percent + ETA label."""

    started_at: float = field(default_factory=time.monotonic)
    last_fraction: float = 0.0

    def message(self, fraction: float, label: str) -> str:
        value = max(0.0, min(1.0, float(fraction)))
        self.last_fraction = max(self.last_fraction, value)
        elapsed = max(0.0, time.monotonic() - self.started_at)
        eta: float | None = None
        if 0.02 <= self.last_fraction < 1.0 and elapsed > 0.2:
            eta = elapsed * (1.0 - self.last_fraction) / self.last_fraction
        percent = int(round(self.last_fraction * 100))
        if self.last_fraction >= 1.0:
            return f"{label} · 100% · done"
        return f"{label} · {percent}% · {format_duration(eta)} remaining"
