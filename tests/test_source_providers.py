from __future__ import annotations

from pathlib import Path

from dublocal.source_providers import (
    AcquiredMedia,
    ProviderRegistry,
    SourceInspection,
    SourceItem,
    SourceProvider,
)


class _Provider(SourceProvider):
    def __init__(self, provider_id: str, host: str) -> None:
        self.provider_id = provider_id
        self.label = provider_id
        self.host = host

    def can_handle(self, locator: str) -> bool:
        return self.host in locator

    def inspect(self, locator: str) -> SourceInspection:
        item = SourceItem("one", locator, "Lesson", provider_id=self.provider_id)
        return SourceInspection(self.provider_id, self.label, locator, "Course", (item,))

    def acquire(self, item: SourceItem, *, progress_callback=None) -> AcquiredMedia:
        return AcquiredMedia(Path("/tmp/example.mp4"), item.title, self.provider_id, item.url)


def test_source_inspection_round_trips() -> None:
    source = SourceInspection(
        provider_id="domestika",
        provider_label="Domestika",
        source_url="https://www.domestika.org/courses/1",
        title="Watercolour",
        items=(
            SourceItem(
                id="lesson-1",
                url="https://www.domestika.org/courses/1/lessons/1",
                title="Introduction",
                index=1,
                duration_seconds=83.0,
                provider_id="domestika",
                course_title="Watercolour",
                metadata={"language": "fr"},
            ),
        ),
    )
    restored = SourceInspection.from_dict(source.to_dict())
    assert restored == source


def test_provider_registry_resolves_specific_provider_first() -> None:
    registry = ProviderRegistry()
    generic = _Provider("generic", "https://")
    specific = _Provider("specific", "domestika.org")
    registry.register(generic)
    registry.register(specific, first=True)
    assert registry.resolve("https://www.domestika.org/courses/123").provider_id == "specific"
    assert registry.resolve("https://example.com/video").provider_id == "generic"
