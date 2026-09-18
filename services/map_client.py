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


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


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

    async def _get(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
        endpoint: str | None = None,
    ) -> dict[str, Any]:
        error: Exception | None = None
        for attempt in range(settings.max_retries):
            await self._throttle()
            try:
                response = await client.get(endpoint or self.endpoint, params=params)
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
    geocode_endpoint = "https://restapi.amap.com/v3/geocode/geo"
    reverse_geocode_endpoint = "https://restapi.amap.com/v3/geocode/regeo"
    around_endpoint = "https://restapi.amap.com/v3/place/around"

    async def geocode(
        self, client: httpx.AsyncClient, address: str, city: str = ""
    ) -> tuple[float, float]:
        params = {"key": self.key, "address": address}
        if city:
            params["city"] = city
        data = await self._get(client, params, self.geocode_endpoint)
        if data.get("status") != "1" or not data.get("geocodes"):
            raise MapApiError(f"高德地理编码失败：{data.get('info', '没有匹配地址')}")
        location = str(data["geocodes"][0].get("location") or "").split(",")
        if len(location) != 2 or _float(location[0]) is None or _float(location[1]) is None:
            raise MapApiError("高德地理编码未返回有效坐标")
        return float(location[0]), float(location[1])

    async def reverse_geocode(
        self, client: httpx.AsyncClient, longitude: float, latitude: float
    ) -> dict[str, str]:
        data = await self._get(
            client,
            {
                "key": self.key,
                "location": f"{longitude},{latitude}",
                "extensions": "base",
                "roadlevel": 0,
            },
            self.reverse_geocode_endpoint,
        )
        regeocode = data.get("regeocode") or {}
        if data.get("status") != "1" or not regeocode:
            raise MapApiError(f"高德位置名称解析失败：{data.get('info', '没有匹配地址')}")
        component = regeocode.get("addressComponent") or {}

        def text(value: Any) -> str:
            return value if isinstance(value, str) else ""

        return {
            "name": text(regeocode.get("formatted_address")),
            "province": text(component.get("province")),
            "city": text(component.get("city")),
            "district": text(component.get("district")),
            "township": text(component.get("township")),
        }

    async def search_around(
        self,
        client: httpx.AsyncClient,
        longitude: float,
        latitude: float,
        radius_m: int,
        keyword: str = "",
        types_code: str = "",
        pages: int = 10,
    ) -> list[dict[str, Any]]:
        result = []
        for page in range(1, pages + 1):
            params: dict[str, Any] = {
                "key": self.key,
                "location": f"{longitude},{latitude}",
                "radius": radius_m,
                "offset": 25,
                "page": page,
                "extensions": "all",
                "sortrule": "distance",
            }
            if types_code:
                params["types"] = types_code
            elif keyword:
                params["keywords"] = keyword
            data = await self._get(client, params, self.around_endpoint)
            if data.get("status") != "1":
                raise MapApiError(f"高德周边检索失败：{data.get('info', '未知错误')}")
            pois = data.get("pois") or []
            for item in pois:
                location = str(item.get("location") or "").split(",")
                result.append({
                    "provider": self.name,
                    "source_id": item.get("id"),
                    "keyword": keyword or types_code,
                    "name": item.get("name"),
                    "category": item.get("type"),
                    "address": item.get("address"),
                    "province": item.get("pname"),
                    "city": item.get("cityname"),
                    "district": item.get("adname"),
                    "phone": item.get("tel"),
                    "email": _text(item.get("email")),
                    "website": _text(item.get("website")) or _text(item.get("url")),
                    "longitude": _float(location[0]) if len(location) == 2 else None,
                    "latitude": _float(location[1]) if len(location) == 2 else None,
                    "distance_m": int(item["distance"]) if str(item.get("distance", "")).isdigit() else None,
                    "raw": item,
                })
            if len(pois) < 25:
                break
        return result

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
                    "email": _text(item.get("email")),
                    "website": _text(item.get("website")) or _text(item.get("url")),
                    "longitude": _float(location[0]) if len(location) == 2 else None,
                    "latitude": _float(location[1]) if len(location) == 2 else None,
                    "distance_m": None,
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
                    "phone": item.get("telephone"),
                    "email": _text(detail.get("email")) or _text(item.get("email")),
                    "website": _text(detail.get("website")) or _text(item.get("website")),
                    "longitude": _float(location.get("lng")),
                    "latitude": _float(location.get("lat")), "distance_m": None, "raw": item,
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
                    "phone": item.get("tel"),
                    "email": _text(item.get("email")),
                    "website": _text(item.get("website")) or _text(item.get("url")),
                    "longitude": _float(location.get("lng")),
                    "latitude": _float(location.get("lat")), "distance_m": None, "raw": item,
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
