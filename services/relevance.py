import re
from typing import Any


# These are explicit non-human-healthcare signals. Keep this list conservative:
# custom institution types should remain searchable unless they clearly describe
# veterinary, pet retail, breeding, or animal-care services.
EXCLUSION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "学校内部医疗机构",
        re.compile(
            r"校医院|校医务室|校卫生(?:室|所)|"
            r"(?:大学|学院|学校|校园|中学|小学|幼儿园|职业技术学院)"
            r".{0,12}(?:医务室|卫生室|卫生所|保健室)",
            re.I,
        ),
    ),
    (
        "宠物相关机构",
        re.compile(r"宠物|宠粮|猫舍|犬舍|宠物用品|宠物美容", re.I),
    ),
    (
        "动物诊疗机构",
        re.compile(
            r"动物医院|动物诊所|动物门诊|动物.{0,4}(?:医疗|诊疗|保健|卫生|检疫|防疫|疫病)",
            re.I,
        ),
    ),
    (
        "兽医或兽药机构",
        re.compile(r"兽医|兽药|兽用|畜牧|畜禽", re.I),
    ),
    (
        "英文宠物医疗机构",
        re.compile(r"\b(?:pet\s*(?:hospital|clinic|care)|animal\s*(?:hospital|clinic)|veterinary|vet\s+clinic)\b", re.I),
    ),
)


def healthcare_relevance(item: dict[str, Any]) -> tuple[bool, str | None]:
    """Return whether a POI is suitable for human-healthcare prospecting."""
    searchable = " ".join(
        str(item.get(field) or "") for field in ("name", "category")
    )
    for reason, pattern in EXCLUSION_RULES:
        if pattern.search(searchable):
            return False, reason
    return True, None


def filter_healthcare_items(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    accepted: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    for item in items:
        relevant, reason = healthcare_relevance(item)
        if relevant:
            accepted.append(item)
            continue
        label = reason or "非人类医疗健康机构"
        rejected[label] = rejected.get(label, 0) + 1
    return accepted, rejected
