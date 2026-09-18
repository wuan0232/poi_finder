from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ProviderName = Literal["amap", "baidu", "tencent"]


class TaskCreate(BaseModel):
    center_name: str = Field(default="", max_length=255, examples=["北京协和医院"])
    center_address: str = Field(default="", max_length=500)
    center_lng: float | None = Field(default=None, ge=-180, le=180)
    center_lat: float | None = Field(default=None, ge=-90, le=90)
    keyword: str = Field(default="药店", max_length=100)
    types_code: str = Field(default="", max_length=20, examples=["090601"])
    radius_km: float = Field(default=3.0, ge=0.1, le=50)
    city: str = Field(default="", max_length=100, examples=["上海市"])
    keywords: list[str] = Field(default_factory=list, max_length=20)
    providers: list[ProviderName] = Field(
        default_factory=lambda: ["amap"], min_length=1, max_length=3
    )
    pages: int = Field(default=2, ge=1, le=20, description="每个平台、每个关键词采集页数")

    @field_validator(
        "center_name", "center_address", "keyword", "types_code", "city"
    )
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        result = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if any(len(value) > 100 for value in result):
            raise ValueError("单个机构类型不能超过 100 个字符")
        return result

    @field_validator("providers")
    @classmethod
    def clean_providers(cls, values: list[ProviderName]) -> list[ProviderName]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_search_mode(self):
        has_one_coordinate = self.center_lng is not None or self.center_lat is not None
        has_coordinates = self.center_lng is not None and self.center_lat is not None
        if has_one_coordinate and not has_coordinates:
            raise ValueError("经度和纬度必须同时提供")
        if self.center_name or self.center_address or has_coordinates:
            if not self.keyword and not self.keywords and not self.types_code:
                raise ValueError("周边检索必须填写关键词或高德分类码")
        elif not self.city or not self.keywords:
            raise ValueError("请填写目的地/地址，或同时填写城市和关键词")
        return self


class TaskRead(BaseModel):
    id: int
    center_name: str | None
    center_address: str | None
    keyword: str | None
    types_code: str | None
    radius_m: int | None
    center_lng: float | None
    center_lat: float | None
    city: str
    keywords: list[str]
    providers: list[str]
    status: str
    total: int
    error_message: str | None
    cache_hit: bool = False
    created_at: datetime
    updated_at: datetime


class PoiRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    provider: str
    source_id: str | None
    keyword: str
    name: str
    category: str | None
    address: str | None
    province: str | None
    city: str | None
    district: str | None
    phone: str | None
    email: str | None
    website: str | None
    contact_sources: dict[str, str]
    longitude: float | None
    latitude: float | None
    distance_m: int | None
    products: list[str]
    products_verified: bool
    product_note: str | None
    product_updated_at: datetime | None
    created_at: datetime


class PoiProductUpdate(BaseModel):
    products: list[str] = Field(default_factory=list, max_length=30)
    verified: bool = True
    note: str = Field(default="", max_length=1000)

    @field_validator("products")
    @classmethod
    def clean_products(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if any(len(value) > 50 for value in cleaned):
            raise ValueError("单个产品名称不能超过 50 个字符")
        return list(dict.fromkeys(cleaned))

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str) -> str:
        return value.strip()


class PoiPage(BaseModel):
    items: list[PoiRead]
    total: int
    page: int
    page_size: int
