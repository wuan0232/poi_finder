import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from services.config import settings


class MapApiError(RuntimeError):
    pass


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MapClient(ABC):
    name: str
    endpoint: str

    def __init__(self, key: str):
        self.key = key
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def _throttle(self) -> None:
        async with self._lock:
            wait = settings.request_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _get(self, client: httpx.AsyncClient, params: dict[str, Any]) -> dict[str, Any]:
        error: Exception | None = None
        for attempt in range(settings.max_retries):
            await self._throttle()
            try:
                response = await client.get(self.endpoint, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "地图服务暂时不可用", request=response.request, response=response
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                error = exc
                if attempt + 1 < settings.max_retries:
                    await asyncio.sleep(2**attempt)
        raise MapApiError(f"{self.name} 请求失败：{error}")

    @abstractmethod
    async def search(
        self, client: httpx.AsyncClient, city: str, keyword: str, pages: int
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class AmapClient(MapClient):
    name = "amap"
    endpoint = "https://restapi.amap.com/v3/place/text"

    async def search(self, client, city, keyword, pages):
        result = []
        for page in range(1, pages + 1):
            data = await self._get(client, {
                "key": self.key, "keywords": keyword, "city": city,
                "citylimit": "true", "page": page, "offset": 25, "extensions": "all",
            })
            if data.get("status") != "1":
                raise MapApiError(f"高德返回错误：{data.get('info', '未知错误')}")
            pois = data.get("pois") or []
            for item in pois:
                location = str(item.get("location") or "").split(",")
                result.append({
                    "provider": self.name, "source_id": item.get("id"), "keyword": keyword,
                    "name": item.get("name"), "category": item.get("type"),
                    "address": item.get("address"), "province": item.get("pname"),
                    "city": item.get("cityname"), "district": item.get("adname"),
                    "phone": item.get("tel"),
                    "longitude": _float(location[0]) if len(location) == 2 else None,
                    "latitude": _float(location[1]) if len(location) == 2 else None,
                    "raw": item,
                })
            if len(pois) < 25:
                break
        return result


class BaiduClient(MapClient):
    name = "baidu"
    endpoint = "https://api.map.baidu.com/place/v2/search"

    async def search(self, client, city, keyword, pages):
        result = []
        for page in range(pages):
            data = await self._get(client, {
                "ak": self.key, "query": keyword, "region": city, "city_limit": "true",
                "output": "json", "scope": 2, "page_size": 20, "page_num": page,
            })
            if data.get("status") != 0:
                raise MapApiError(f"百度返回错误：{data.get('message', data.get('status'))}")
            pois = data.get("results") or []
            for item in pois:
                location = item.get("location") or {}
                detail = item.get("detail_info") or {}
                result.append({
                    "provider": self.name, "source_id": item.get("uid"), "keyword": keyword,
                    "name": item.get("name"), "category": detail.get("type"),
                    "address": item.get("address"), "province": item.get("province"),
                    "city": item.get("city"), "district": item.get("area"),
                    "phone": item.get("telephone"), "longitude": _float(location.get("lng")),
                    "latitude": _float(location.get("lat")), "raw": item,
                })
            if len(pois) < 20:
                break
        return result


class TencentClient(MapClient):
    name = "tencent"
    endpoint = "https://apis.map.qq.com/ws/place/v1/search"

    async def search(self, client, city, keyword, pages):
        result = []
        for page in range(1, pages + 1):
            data = await self._get(client, {
                "key": self.key, "keyword": keyword, "boundary": f"region({city},0)",
                "page_size": 20, "page_index": page,
            })
            if data.get("status") != 0:
                raise MapApiError(f"腾讯返回错误：{data.get('message', data.get('status'))}")
            pois = data.get("data") or []
            for item in pois:
                location = item.get("location") or {}
                ad_info = item.get("ad_info") or {}
                result.append({
                    "provider": self.name, "source_id": item.get("id"), "keyword": keyword,
                    "name": item.get("title"), "category": item.get("category"),
                    "address": item.get("address"), "province": ad_info.get("province"),
                    "city": ad_info.get("city"), "district": ad_info.get("district"),
                    "phone": item.get("tel"), "longitude": _float(location.get("lng")),
                    "latitude": _float(location.get("lat")), "raw": item,
                })
            if len(pois) < 20:
                break
        return result


CLIENTS = {"amap": AmapClient, "baidu": BaiduClient, "tencent": TencentClient}


def create_client(provider: str) -> MapClient:
    client_class = CLIENTS.get(provider)
    if client_class is None:
        raise ValueError(f"不支持的地图平台：{provider}")
    key = settings.key_for(provider)
    if not key:
        raise ValueError(f"未配置 {provider} API Key")
    return client_class(key)
