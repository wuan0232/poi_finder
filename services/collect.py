import json

import httpx
from sqlalchemy import delete

from database import SessionLocal
from models import Poi, Task
from services.clean import clean_and_deduplicate
from services.config import settings
from services.map_client import create_client


async def collect_task(task_id: int, pages: int = 2) -> None:
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None:
            return
        task.status = "running"
        task.error_message = None
        db.commit()

        try:
            keywords = json.loads(task.keywords_json)
            providers = json.loads(task.providers_json)
            collected: list[dict] = []
            errors: list[str] = []
            async with httpx.AsyncClient(timeout=settings.request_timeout) as http_client:
                for provider in providers:
                    map_client = create_client(provider)
                    for keyword in keywords:
                        try:
                            collected.extend(
                                await map_client.search(http_client, task.city, keyword, pages)
                            )
                        except Exception as exc:
                            errors.append(f"{provider}/{keyword}: {exc}")

            cleaned = clean_and_deduplicate(collected)
            db.execute(delete(Poi).where(Poi.task_id == task_id))
            for item in cleaned:
                raw = item.pop("raw", None)
                db.add(Poi(
                    task_id=task_id,
                    extra_json=json.dumps(raw, ensure_ascii=False) if raw else None,
                    **item,
                ))
            task.total = len(cleaned)
            task.error_message = "\n".join(errors) or None
            task.status = "completed" if cleaned or not errors else "failed"
            db.commit()
        except Exception as exc:
            db.rollback()
            task = db.get(Task, task_id)
            if task is not None:
                task.status = "failed"
                task.error_message = str(exc)
                db.commit()
