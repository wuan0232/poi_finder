from typing import Any


CONTACT_FIELDS = ("phone", "email", "website")


def record_contact_sources(item: dict[str, Any]) -> None:
    sources = item.setdefault("contact_sources", {})
    provider = str(item.get("provider") or "unknown")
    for field in CONTACT_FIELDS:
        if item.get(field) and not sources.get(field):
            sources[field] = provider


def persist_contact_sources(item: dict[str, Any]) -> None:
    record_contact_sources(item)
    raw = item.get("raw")
    if isinstance(raw, dict):
        raw["_contact_sources"] = item.pop("contact_sources", {})
    else:
        item.pop("contact_sources", None)
