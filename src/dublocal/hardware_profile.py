from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    architecture: str
    memory_bytes: int | None
    cpu_name: str

    @property
    def memory_gib(self) -> float | None:
        if self.memory_bytes is None:
            return None
        return self.memory_bytes / (1024**3)

    @property
    def apple_silicon(self) -> bool:
        return self.architecture.lower() in {"arm64", "aarch64"} and "apple" in self.cpu_name.lower()


@dataclass(frozen=True, slots=True)
class TranslationRecommendation:
    tier: str
    label: str
    model_key: str
    model_label: str
    review: bool
    context_cap_tokens: int
    explanation: str


def _sysctl_value(name: str) -> str | None:
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", name],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip() if result.returncode == 0 else ""
    return value or None


def _physical_memory_bytes() -> int | None:
    raw = _sysctl_value("hw.memsize")
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass

    # Portable fallback for development/tests on Unix-like hosts.
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        value = int(pages) * int(page_size)
        return value if value > 0 else None
    except (AttributeError, OSError, ValueError):
        return None


def detect_hardware_profile() -> HardwareProfile:
    architecture = platform.machine() or "unknown"
    cpu_name = _sysctl_value("machdep.cpu.brand_string") or platform.processor() or architecture
    return HardwareProfile(
        architecture=architecture,
        memory_bytes=_physical_memory_bytes(),
        cpu_name=cpu_name,
    )


def recommend_translation_profile(
    profile: HardwareProfile | None = None,
) -> TranslationRecommendation:
    """Choose a conservative local translation profile for the current Mac.

    The thresholds deliberately protect low-memory Macs from loading the 8B model plus
    a large KV cache. They are recommendations, not claims that other profiles cannot run.
    """

    hardware = profile or detect_hardware_profile()
    memory = hardware.memory_gib
    memory_text = f"{memory:.0f} GB" if memory is not None else "unknown RAM"
    apple_silicon = hardware.apple_silicon
    architecture = hardware.architecture

    if apple_silicon and memory is not None and memory < 12:
        return TranslationRecommendation(
            tier="light",
            label="Lightweight",
            model_key="4b",
            model_label="Qwen3 4B Q4_K_M",
            review=False,
            context_cap_tokens=8192,
            explanation=(
                f"{memory_text} Apple Silicon → Qwen3 4B, single pass and an 8k context cap. "
                "This keeps unified-memory pressure and swap risk down while retaining contextual translation."
            ),
        )

    if apple_silicon and memory is not None and memory < 24:
        return TranslationRecommendation(
            tier="balanced",
            label="Balanced",
            model_key="8b",
            model_label="Qwen3 8B Q4_K_M",
            review=False,
            context_cap_tokens=16384,
            explanation=(
                f"{memory_text} Apple Silicon → Qwen3 8B, single pass and a 16k context cap. "
                "This favors translation quality without making the review pass or maximum context the default."
            ),
        )

    if apple_silicon and memory is not None:
        return TranslationRecommendation(
            tier="best",
            label="Best quality",
            model_key="8b",
            model_label="Qwen3 8B Q4_K_M",
            review=True,
            context_cap_tokens=24576,
            explanation=(
                f"{memory_text} Apple Silicon → Qwen3 8B with the senior review pass and up to 24k input context. "
                "The same model remains loaded, so the review costs time rather than another model-sized memory allocation."
            ),
        )

    # Intel Macs are biased one tier lighter because llama.cpp inference is CPU-bound.
    if architecture.lower() in {"x86_64", "amd64"}:
        if memory is not None and memory >= 24:
            return TranslationRecommendation(
                tier="balanced",
                label="Balanced",
                model_key="8b",
                model_label="Qwen3 8B Q4_K_M",
                review=False,
                context_cap_tokens=12288,
                explanation=(
                    f"{memory_text} Intel Mac → Qwen3 8B, single pass and a 12k context cap. "
                    "DubLocal avoids the automatic review pass because CPU inference is substantially slower."
                ),
            )
        return TranslationRecommendation(
            tier="light",
            label="Lightweight",
            model_key="4b",
            model_label="Qwen3 4B Q4_K_M",
            review=False,
            context_cap_tokens=6144,
            explanation=(
                f"{memory_text} Intel Mac → Qwen3 4B, single pass and a smaller context cap. "
                "This is the practical default for CPU-only local inference."
            ),
        )

    # Unknown/non-Mac development hosts get the safest contextual profile.
    return TranslationRecommendation(
        tier="light",
        label="Lightweight",
        model_key="4b",
        model_label="Qwen3 4B Q4_K_M",
        review=False,
        context_cap_tokens=6144,
        explanation=(
            f"{architecture} · {memory_text} → conservative Qwen3 4B profile because DubLocal could not classify this Mac confidently."
        ),
    )


def hardware_summary(profile: HardwareProfile | None = None) -> str:
    hardware = profile or detect_hardware_profile()
    memory = hardware.memory_gib
    memory_text = f"{memory:.0f} GB" if memory is not None else "RAM unknown"
    return f"{hardware.cpu_name} · {hardware.architecture} · {memory_text}"
