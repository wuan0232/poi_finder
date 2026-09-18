import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Task


def find_cached_task(
    db: Session,
    *,
    center_name: str,
    center_address: str,
    city: str,
    keyword: str,
    keywords: list[str],
    types_code: str,
    radius_m: int,
    providers: list[str],
    ttl_hours: float,
    center_lng: float | None = None,
    center_lat: float | None = None,
) -> Task | None:
    if ttl_hours <= 0:
        return None
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=ttl_hours)
    providers_json = json.dumps(providers, ensure_ascii=False)
    keywords_json = json.dumps(keywords, ensure_ascii=False)
    conditions = [
            Task.status == "completed",
            Task.center_name == center_name,
            Task.center_address == center_address,
            Task.city == city,
            Task.keyword == keyword,
            Task.keywords_json == keywords_json,
            Task.types_code == (types_code or None),
            Task.radius_m == radius_m,
            Task.providers_json == providers_json,
            Task.created_at >= cutoff,
    ]
    if center_lng is not None and center_lat is not None:
        conditions.extend([Task.center_lng == center_lng, Task.center_lat == center_lat])
    return db.scalar(
        select(Task)
        .where(*conditions)
        .order_by(Task.created_at.desc(), Task.id.desc())
        .limit(1)
    )
