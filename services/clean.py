import re
from typing import Any


def _compact(value: Any) -> str:
    return re.sub(r"[\s\-—_,，。·()（）]", "", str(value or "")).lower()


def _dedupe_key(poi: dict[str, Any]) -> tuple:
    phone = _compact(poi.get("phone"))
    name = _compact(poi.get("name"))
    address = _compact(poi.get("address"))
    if phone:
        return "phone", phone
    if name and address:
        return "name_address", name, address
    return "source", poi.get("provider"), poi.get("source_id") or name


def clean_and_deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for item in items:
        item["name"] = str(item.get("name") or "").strip()
        if not item["name"]:
            continue
        for field in (
            "category", "address", "province", "city", "district", "phone",
            "email", "website",
        ):
            value = item.get(field)
            item[field] = str(value).strip() if value not in (None, "", []) else None
        key = _dedupe_key(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
