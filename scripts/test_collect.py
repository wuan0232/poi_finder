import argparse
import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json  # noqa: E402

import models  # noqa: E402,F401
from database import Base, SessionLocal, engine  # noqa: E402
from models import Task  # noqa: E402
from services.collect import collect_task  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="测试目的地周边 POI 采集及入库链路")
    parser.add_argument("--center", default="北京协和医院", help="目的地名称")
    parser.add_argument("--address", default="", help="目的地详细地址，选填")
    parser.add_argument("--city", default="北京市", help="用于提高地理编码准确度")
    parser.add_argument("--keyword", default="药店")
    parser.add_argument("--types-code", default="")
    parser.add_argument("--radius-km", type=float, default=3.0)
    parser.add_argument("--pages", type=int, default=2)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        task = Task(
            center_name=args.center,
            center_address=args.address or args.center,
            keyword=args.keyword,
            types_code=args.types_code or None,
            radius_m=int(args.radius_km * 1000),
            city=args.city,
            keywords_json=json.dumps([args.keyword], ensure_ascii=False),
            providers_json=json.dumps(["amap"]),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id

    await collect_task(task_id, args.pages)
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        print(f"任务 {task.id}：{task.status}，入库 {task.total} 条")
        print(f"中心坐标：{task.center_lng}, {task.center_lat}")
        if task.error_message:
            print(task.error_message)


if __name__ == "__main__":
    asyncio.run(main())
