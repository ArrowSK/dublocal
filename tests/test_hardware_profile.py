from __future__ import annotations

from dublocal.hardware_profile import HardwareProfile, recommend_translation_profile


def _profile(cpu: str, arch: str, gib: int) -> HardwareProfile:
    return HardwareProfile(
        architecture=arch,
        memory_bytes=gib * 1024**3,
        cpu_name=cpu,
    )


def test_m1_8gb_gets_lightweight_4b_profile():
    recommendation = recommend_translation_profile(_profile("Apple M1", "arm64", 8))
    assert recommendation.tier == "light"
    assert recommendation.model_key == "4b"
    assert recommendation.review is False
    assert recommendation.context_cap_tokens == 8192


def test_m1_16gb_gets_balanced_8b_single_pass():
    recommendation = recommend_translation_profile(_profile("Apple M1", "arm64", 16))
    assert recommendation.tier == "balanced"
    assert recommendation.model_key == "8b"
    assert recommendation.review is False
    assert recommendation.context_cap_tokens == 16384


def test_apple_silicon_24gb_gets_8b_review_profile():
    recommendation = recommend_translation_profile(_profile("Apple M2 Pro", "arm64", 24))
    assert recommendation.tier == "best"
    assert recommendation.model_key == "8b"
    assert recommendation.review is True
    assert recommendation.context_cap_tokens == 24576


def test_intel_16gb_is_biased_to_4b():
    recommendation = recommend_translation_profile(_profile("Intel Core i7", "x86_64", 16))
    assert recommendation.tier == "light"
    assert recommendation.model_key == "4b"
    assert recommendation.review is False


def test_intel_32gb_uses_8b_without_review():
    recommendation = recommend_translation_profile(_profile("Intel Core i9", "x86_64", 32))
    assert recommendation.tier == "balanced"
    assert recommendation.model_key == "8b"
    assert recommendation.review is False
    assert recommendation.context_cap_tokens == 12288
