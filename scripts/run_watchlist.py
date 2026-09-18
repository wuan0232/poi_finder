import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import models  # noqa: E402,F401
from database import Base, SessionLocal, engine  # noqa: E402
from models import Task  # noqa: E402
from services.cache import find_cached_task  # noqa: E402
from services.collect import collect_task  # noqa: E402
from services.config import settings  # noqa: E402


def configure_logging(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
        force=True,
    )
    return logging.getLogger("watchlist")


def load_watchlist(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("监控清单必须是 JSON 数组")
    return data


async def run_item(item: dict, pages: int, logger: logging.Logger) -> bool:
    center_name = str(item.get("center_name") or "").strip()
    if not center_name:
        raise ValueError("center_name 不能为空")
    center_address = str(item.get("center_address") or center_name).strip()
    city = str(item.get("city") or "").strip()
    keyword = str(item.get("keyword") or "药店").strip()
    keywords = item.get("keywords") or [keyword]
    keywords = list(dict.fromkeys(str(value).strip() for value in keywords if str(value).strip()))
    keyword_label = "、".join(keywords)[:100]
    types_code = str(item.get("types_code") or "").strip()
    radius_km = float(item.get("radius_km", 3))
    if not 0.1 <= radius_km <= 50:
        raise ValueError("radius_km 必须在 0.1 到 50 之间")
    radius_m = int(radius_km * 1000)
    providers = ["amap"]

    with SessionLocal() as db:
        cached = find_cached_task(
            db,
            center_name=center_name,
            center_address=center_address,
            city=city,
            keyword=keyword_label,
            keywords=keywords,
            types_code=types_code,
            radius_m=radius_m,
            providers=providers,
            ttl_hours=settings.cache_ttl_hours,
        )
        if cached is not None:
            logger.info("[CACHE] %s -> 任务 %s，共 %s 条", center_name, cached.id, cached.total)
            return True

        task = Task(
            center_name=center_name,
            center_address=center_address,
            city=city,
            keyword=keyword_label,
            types_code=types_code or None,
            radius_m=radius_m,
            keywords_json=json.dumps(keywords, ensure_ascii=False),
            providers_json=json.dumps(providers, ensure_ascii=False),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id

    await collect_task(task_id, pages)
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None or task.status != "completed":
            error = task.error_message if task else "任务记录不存在"
            logger.error("[FAIL] %s -> %s", center_name, error)
            return False
        logger.info("[OK] %s -> 任务 %s，共 %s 条", center_name, task.id, task.total)
        return True


async def main() -> None:
    parser = argparse.ArgumentParser(description="按监控清单批量采集周边 POI")
    parser.add_argument("--file", type=Path, default=ROOT_DIR / "watchlist.json")
    parser.add_argument("--pages", type=int, default=10, choices=range(1, 21))
    parser.add_argument("--log-file", type=Path, default=ROOT_DIR / "logs" / "watchlist.log")
    args = parser.parse_args()

    logger = configure_logging(args.log_file)
    Base.metadata.create_all(bind=engine)
    items = load_watchlist(args.file.resolve())
    enabled = [item for item in items if item.get("enabled", True)]
    logger.info("监控清单共 %s 条，启用 %s 条", len(items), len(enabled))

    failures = 0
    for item in enabled:
        name = str(item.get("center_name") or "未命名条目")
        try:
            if not await run_item(item, args.pages, logger):
                failures += 1
        except Exception:
            failures += 1
            logger.exception("[FAIL] %s", name)

    logger.info("批量任务结束：成功 %s，失败 %s", len(enabled) - failures, failures)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
