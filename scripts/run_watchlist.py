import argparse
import asyncio
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models  # noqa: E402,F401
from database import Base, SessionLocal, engine  # noqa: E402
from models import Task  # noqa: E402
from services.collect import collect_task  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="批量创建并执行 POI 采集任务")
    parser.add_argument("--city", required=True)
    parser.add_argument("--keywords", required=True, help="英文逗号分隔")
    parser.add_argument("--providers", default="amap,baidu,tencent", help="英文逗号分隔")
    parser.add_argument("--pages", type=int, default=2)
    args = parser.parse_args()

    keywords = [item.strip() for item in args.keywords.split(",") if item.strip()]
    providers = [item.strip() for item in args.providers.split(",") if item.strip()]
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        task = Task(
            city=args.city,
            keywords_json=json.dumps(keywords, ensure_ascii=False),
            providers_json=json.dumps(providers, ensure_ascii=False),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    await collect_task(task_id, args.pages)
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        print(f"任务 {task_id}: {task.status}，共 {task.total} 条")
        if task.error_message:
            print(task.error_message)


if __name__ == "__main__":
    asyncio.run(main())
