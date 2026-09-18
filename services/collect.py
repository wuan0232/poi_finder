import asyncio
import json
import logging

import httpx
from sqlalchemy import delete

from database import SessionLocal
from models import Poi, Task
from services.clean import clean_and_deduplicate
from services.config import settings
from services.contact_enrichment import persist_contact_sources
from services.map_client import AmapClient, MapApiError, create_client
from services.relevance import filter_healthcare_items
from services.website_contacts import enrich_items_from_websites


logger = logging.getLogger(__name__)
_collect_lock = asyncio.Lock()


def summarize_errors(errors: list[str]) -> str | None:
    if not errors:
        return None
    messages = [error.split(": ", 1)[-1] for error in errors]
    if len(errors) > 1 and len(set(messages)) == 1:
        message = messages[0]
        hint = ""
        if "connection attempts failed" in message.lower():
            hint = "\n请确认运行服务的电脑可以访问 https://restapi.amap.com。"
        return f"{len(errors)} 类机构均未完成：{message}{hint}"
    return "\n".join(errors)


async def collect_task(task_id: int, pages: int = 2) -> None:
    async with _collect_lock:
        await _collect_task_unlocked(task_id, pages)


async def _collect_task_unlocked(task_id: int, pages: int = 2) -> None:
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None:
            return
        task.status = "running"
        task.error_message = None
        db.commit()
        logger.info("开始采集任务 %s", task_id)

        try:
            keywords = json.loads(task.keywords_json)
            providers = json.loads(task.providers_json)
            collected: list[dict] = []
            errors: list[str] = []
            async with httpx.AsyncClient(timeout=settings.request_timeout) as http_client:
                if task.center_name or task.center_address or (
                    task.center_lng is not None and task.center_lat is not None
                ):
                    map_client = create_client("amap")
                    if not isinstance(map_client, AmapClient):
                        raise MapApiError("周边检索需要高德地图客户端")
                    if task.center_lng is not None and task.center_lat is not None:
                        longitude, latitude = task.center_lng, task.center_lat
                    else:
                        address = task.center_address or task.center_name or ""
                        longitude, latitude = await map_client.geocode(
                            http_client, address, task.city
                        )
                        task.center_lng = longitude
                        task.center_lat = latitude
                    around_keywords = [task.keyword or ""] if task.types_code else keywords
                    for keyword in around_keywords:
                        try:
                            batch = await map_client.search_around(
                                    http_client,
                                    longitude,
                                    latitude,
                                    task.radius_m or 3000,
                                    keyword,
                                    task.types_code or "",
                                    pages,
                                )
                            batch, rejected = filter_healthcare_items(batch)
                            if rejected:
                                logger.info(
                                    "任务 %s 过滤非人类医疗机构：%s",
                                    task_id,
                                    rejected,
                                )
                            await enrich_items_from_websites(http_client, batch)
                            collected.extend(batch)
                        except Exception as exc:
                            errors.append(f"amap/{keyword or task.types_code}: {exc}")
                else:
                    for provider in providers:
                        map_client = create_client(provider)
                        for keyword in keywords:
                            try:
                                batch = await map_client.search(
                                    http_client, task.city, keyword, pages
                                )
                                batch, rejected = filter_healthcare_items(batch)
                                if rejected:
                                    logger.info(
                                        "任务 %s 过滤非人类医疗机构：%s",
                                        task_id,
                                        rejected,
                                    )
                                await enrich_items_from_websites(http_client, batch)
                                for item in batch:
                                    persist_contact_sources(item)
                                collected.extend(batch)
                            except Exception as exc:
                                errors.append(f"{provider}/{keyword}: {exc}")

            for item in collected:
                persist_contact_sources(item)
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
            task.error_message = summarize_errors(errors)
            task.status = "completed" if cleaned or not errors else "failed"
            db.commit()
            logger.info("任务 %s 完成，入库 %s 条", task_id, len(cleaned))
        except Exception as exc:
            db.rollback()
            task = db.get(Task, task_id)
            if task is not None:
                task.status = "failed"
                task.error_message = str(exc)
                db.commit()
            logger.exception("任务 %s 采集失败", task_id)
