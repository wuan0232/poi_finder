from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProviderName = Literal["amap", "baidu", "tencent"]


class TaskCreate(BaseModel):
    city: str = Field(min_length=1, max_length=100, examples=["上海市"])
    keywords: list[str] = Field(min_length=1, max_length=20, examples=[["口腔诊所", "牙科"]])
    providers: list[ProviderName] = Field(
        default_factory=lambda: ["amap", "baidu", "tencent"], min_length=1, max_length=3
    )
    pages: int = Field(default=2, ge=1, le=20, description="每个平台、每个关键词采集页数")

    @field_validator("city")
    @classmethod
    def clean_city(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("城市不能为空")
        return value

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        result = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not result:
            raise ValueError("至少填写一个有效关键词")
        return result

    @field_validator("providers")
    @classmethod
    def clean_providers(cls, values: list[ProviderName]) -> list[ProviderName]:
        return list(dict.fromkeys(values))


class TaskRead(BaseModel):
    id: int
    city: str
    keywords: list[str]
    providers: list[str]
    status: str
    total: int
    error_message: str | None
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
    longitude: float | None
    latitude: float | None
    created_at: datetime


class PoiPage(BaseModel):
    items: list[PoiRead]
    total: int
    page: int
    page_size: int
