from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True, slots=True)
class SourceItem:
    """One independently processable item exposed by a source provider."""

    id: str
    url: str
    title: str
    index: int = 1
    duration_seconds: float | None = None
    provider_id: str = ""
    course_title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceItem":
        return cls(
            id=str(value.get("id") or ""),
            url=str(value.get("url") or ""),
            title=str(value.get("title") or "Untitled item"),
            index=max(1, int(value.get("index") or 1)),
            duration_seconds=(
                float(value["duration_seconds"])
                if value.get("duration_seconds") not in {None, ""}
                else None
            ),
            provider_id=str(value.get("provider_id") or ""),
            course_title=str(value.get("course_title") or ""),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class SourceInspection:
    """Provider-neutral description of a URL/course before acquisition."""

    provider_id: str
    provider_label: str
    source_url: str
    title: str
    items: tuple[SourceItem, ...]
    login_required: bool = False
    drm_protected: bool = False
    status: str = "ready"
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_label": self.provider_label,
            "source_url": self.source_url,
            "title": self.title,
            "items": [item.to_dict() for item in self.items],
            "login_required": self.login_required,
            "drm_protected": self.drm_protected,
            "status": self.status,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceInspection":
        return cls(
            provider_id=str(value.get("provider_id") or "generic-authenticated-web"),
            provider_label=str(value.get("provider_label") or "Authenticated website"),
            source_url=str(value.get("source_url") or ""),
            title=str(value.get("title") or "Authenticated media"),
            items=tuple(SourceItem.from_dict(item) for item in (value.get("items") or [])),
            login_required=bool(value.get("login_required")),
            drm_protected=bool(value.get("drm_protected")),
            status=str(value.get("status") or "ready"),
            detail=str(value.get("detail") or ""),
        )


@dataclass(frozen=True, slots=True)
class AcquiredMedia:
    """Normalized local boundary returned by every acquiring provider."""

    path: Path
    title: str
    provider_id: str
    source_url: str
    course_title: str = ""
    lesson_title: str = ""
    lesson_number: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class SourceProvider(ABC):
    """Stable boundary between source acquisition and the DubLocal media pipeline.

    Providers end their responsibility after ``acquire`` returns an ordinary local
    ``AcquiredMedia``. Whisper, translation, TTS, mixing and export must never live in
    provider implementations.
    """

    provider_id = "provider"
    label = "Source provider"

    @abstractmethod
    def can_handle(self, locator: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def inspect(self, locator: str) -> SourceInspection:
        raise NotImplementedError

    @abstractmethod
    def acquire(
        self,
        item: SourceItem,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> AcquiredMedia:
        raise NotImplementedError


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: list[SourceProvider] = []

    def register(self, provider: SourceProvider, *, first: bool = False) -> None:
        self._providers = [
            existing
            for existing in self._providers
            if existing.provider_id != provider.provider_id
        ]
        if first:
            self._providers.insert(0, provider)
        else:
            self._providers.append(provider)

    def providers(self) -> tuple[SourceProvider, ...]:
        return tuple(self._providers)

    def resolve(self, locator: str) -> SourceProvider:
        for provider in self._providers:
            if provider.can_handle(locator):
                return provider
        raise LookupError(f"No source provider accepts {locator!r}.")


AUTHENTICATED_SOURCE_PROVIDERS = ProviderRegistry()
