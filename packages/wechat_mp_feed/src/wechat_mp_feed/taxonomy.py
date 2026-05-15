"""Small taxonomy loader for deterministic local classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TaxonomyEntry:
    id: str
    name_zh: str | None = None
    aliases_zh: tuple[str, ...] = ()
    description_zh: str | None = None

    @property
    def keywords(self) -> tuple[str, ...]:
        values = [self.name_zh, *self.aliases_zh]
        return tuple(value for value in values if value)


@dataclass(frozen=True)
class TagGroup:
    id: str
    name_zh: str | None
    tags: tuple[TaxonomyEntry, ...]


@dataclass(frozen=True)
class Taxonomy:
    name: str
    source_categories: tuple[TaxonomyEntry, ...]
    article_categories: tuple[TaxonomyEntry, ...]
    tag_groups: tuple[TagGroup, ...]


def load_taxonomy(path: str | Path) -> Taxonomy:
    taxonomy_path = Path(path)
    text = taxonomy_path.read_text(encoding="utf-8")
    return parse_taxonomy(text, name=taxonomy_path.stem.replace("taxonomy.", ""))


def parse_taxonomy(text: str, name: str = "default") -> Taxonomy:
    lines = text.splitlines()
    source_categories = _parse_entry_list(lines, "source_categories")
    article_categories = _parse_entry_list(lines, "article_categories")
    tag_groups = _parse_tag_groups(lines)
    return Taxonomy(
        name=name,
        source_categories=tuple(source_categories),
        article_categories=tuple(article_categories),
        tag_groups=tuple(tag_groups),
    )


def _parse_entry_list(lines: list[str], section_name: str) -> list[TaxonomyEntry]:
    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    in_section = False

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            in_section = line[:-1] == section_name
            if not in_section and current:
                entries.append(current)
                current = None
            continue
        if not in_section:
            continue

        stripped = line.strip()
        if stripped.startswith("- id: "):
            if current:
                entries.append(current)
            current = {"id": _parse_scalar(stripped.removeprefix("- id: "))}
            continue
        if current and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            current[key] = _parse_value(raw_value.strip())

    if in_section and current:
        entries.append(current)

    return [_entry_from_dict(item) for item in entries]


def _parse_tag_groups(lines: list[str]) -> list[TagGroup]:
    groups: list[TagGroup] = []
    in_section = False
    current_group_id: str | None = None
    current_group_name: str | None = None
    current_tags: list[dict[str, object]] = []
    current_tag: dict[str, object] | None = None

    def flush_tag() -> None:
        nonlocal current_tag
        if current_tag:
            current_tags.append(current_tag)
            current_tag = None

    def flush_group() -> None:
        nonlocal current_group_id, current_group_name, current_tags
        flush_tag()
        if current_group_id:
            groups.append(
                TagGroup(
                    id=current_group_id,
                    name_zh=current_group_name,
                    tags=tuple(_entry_from_dict(item) for item in current_tags),
                )
            )
        current_group_id = None
        current_group_name = None
        current_tags = []

    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            if in_section:
                flush_group()
            in_section = line[:-1] == "tag_groups"
            continue
        if not in_section:
            continue

        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
            flush_group()
            current_group_id = line.strip()[:-1]
            continue

        stripped = line.strip()
        if stripped.startswith("- id: "):
            flush_tag()
            current_tag = {"id": _parse_scalar(stripped.removeprefix("- id: "))}
            continue
        if current_tag and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            current_tag[key] = _parse_value(raw_value.strip())
            continue
        if current_group_id and stripped.startswith("name_zh:"):
            current_group_name = str(_parse_value(stripped.split(":", 1)[1].strip()))

    if in_section:
        flush_group()
    return groups


def _entry_from_dict(item: dict[str, object]) -> TaxonomyEntry:
    aliases = item.get("aliases_zh") or ()
    if isinstance(aliases, str):
        aliases = (aliases,)
    return TaxonomyEntry(
        id=str(item["id"]),
        name_zh=str(item["name_zh"]) if item.get("name_zh") else None,
        aliases_zh=tuple(str(value) for value in aliases),
        description_zh=str(item["description_zh"]) if item.get("description_zh") else None,
    )


def _parse_value(value: str) -> object:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return ()
        return tuple(_parse_scalar(part.strip()) for part in inner.split(","))
    return _parse_scalar(value)


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
