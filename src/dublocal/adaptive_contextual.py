from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contextual_quality_model import (
    QUALITY_CONTEXT_MODEL,
    install_quality_contextual_model,
    quality_contextual_model_path,
    quality_registered_model_valid,
    remove_quality_contextual_model,
)
from .contextual_translation import (
    QWEN_CONTEXT_MODEL,
    _registered_model_valid,
    contextual_model_path,
    install_contextual_model,
    install_llama_cpp,
    llama_cpp_status,
    remove_contextual_model,
)
from .dependencies import shared_huggingface_cache
from .hardware_profile import (
    TranslationRecommendation,
    hardware_summary,
    recommend_translation_profile,
)


@dataclass(frozen=True, slots=True)
class ContextualModelSpec:
    key: str
    label: str
    metadata: dict[str, object]
    path: Path


def contextual_model_spec(model_key: str) -> ContextualModelSpec:
    if model_key == "4b":
        return ContextualModelSpec(
            key="4b",
            label="Qwen3 4B",
            metadata=QWEN_CONTEXT_MODEL,
            path=contextual_model_path(),
        )
    if model_key == "8b":
        return ContextualModelSpec(
            key="8b",
            label="Qwen3 8B",
            metadata=QUALITY_CONTEXT_MODEL,
            path=quality_contextual_model_path(),
        )
    raise ValueError(f"Unknown contextual model key: {model_key}")


def contextual_model_valid(model_key: str) -> bool:
    if model_key == "4b":
        return _registered_model_valid()
    if model_key == "8b":
        return quality_registered_model_valid()
    return False


def install_contextual_model_for(model_key: str) -> Path:
    if model_key == "4b":
        return install_contextual_model()
    if model_key == "8b":
        return install_quality_contextual_model()
    raise ValueError(f"Unknown contextual model key: {model_key}")


def remove_contextual_model_for(model_key: str) -> bool:
    if model_key == "4b":
        return remove_contextual_model()
    if model_key == "8b":
        return remove_quality_contextual_model()
    return False


def active_recommendation() -> TranslationRecommendation:
    return recommend_translation_profile()


def prepare_recommended_contextual_translation() -> str:
    recommendation = active_recommendation()
    command = install_llama_cpp()
    model = install_contextual_model_for(recommendation.model_key)
    return f"{' '.join(command)} · {model.name} · {recommendation.label}"


def remove_recommended_contextual_model() -> bool:
    return remove_contextual_model_for(active_recommendation().model_key)


def adaptive_contextual_translation_status(
    source_language: str = "auto",
    target_language: str = "en",
    duration_ms: int | None = None,
) -> str:
    recommendation = active_recommendation()
    spec = contextual_model_spec(recommendation.model_key)
    state = "installed" if contextual_model_valid(recommendation.model_key) else "not installed"
    requested_budget = 4096 + max(0, int(duration_ms or 0)) // 60_000 * 128
    budget = min(24576, max(4096, requested_budget), recommendation.context_cap_tokens)
    review = "on" if recommendation.review else "off"
    return (
        "```text\n"
        f"[recommended] {recommendation.label} for this Mac\n"
        f"[hardware] {hardware_summary()}\n"
        f"[why] {recommendation.explanation}\n"
        f"[engine] llama.cpp · {llama_cpp_status()}\n"
        f"[model] {spec.label} · {state} · {spec.metadata['size']} · {spec.metadata['license']}\n"
        f"[route] {source_language} → {target_language}\n"
        f"[context] up to {recommendation.context_cap_tokens} input tokens · current job budget {budget}\n"
        f"[review] {review}\n"
        f"[shared cache] {shared_huggingface_cache()}\n"
        "[policy] local-only; no cloud fallback\n"
        "```"
    )
