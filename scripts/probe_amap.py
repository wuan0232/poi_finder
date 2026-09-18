import asyncio
import argparse
import sys
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from services.config import settings  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="检查高德 Web 服务 HTTPS 连通性")
    parser.add_argument("--configured-key", action="store_true")
    args = parser.parse_args()
    key = settings.amap_key if args.configured_key else "invalid-connectivity-test"
    if args.configured_key and not key:
        raise SystemExit("AMAP_KEY 尚未配置")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://restapi.amap.com/v3/place/around",
                params={
                    "key": key,
                    "location": "120.607905,31.252827",
                    "keywords": "test",
                },
            )
        data = response.json()
        print(
            "高德 HTTPS 可达："
            f"HTTP {response.status_code}，API status={data.get('status')}，"
            f"info={data.get('info')}，结果数={len(data.get('pois') or [])}"
        )
    except Exception as exc:
        print(f"高德 HTTPS 不可达：{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    asyncio.run(main())
