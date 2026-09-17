import argparse
import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from services.config import settings  # noqa: E402
from services.map_client import create_client  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="直接测试单个平台的 POI 采集链路")
    parser.add_argument("--provider", choices=["amap", "baidu", "tencent"], default="amap")
    parser.add_argument("--city", default="上海市")
    parser.add_argument("--keyword", default="口腔诊所")
    parser.add_argument("--pages", type=int, default=1)
    args = parser.parse_args()

    map_client = create_client(args.provider)
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        rows = await map_client.search(client, args.city, args.keyword, args.pages)
    print(f"采集到 {len(rows)} 条原始数据")
    for row in rows[:5]:
        print(row["name"], row.get("address"), row.get("phone"))


if __name__ == "__main__":
    asyncio.run(main())
