import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./poi_finder.db")
    sqlite_timeout: float = float(os.getenv("SQLITE_TIMEOUT", "30"))
    cache_ttl_hours: float = float(os.getenv("CACHE_TTL_HOURS", "24"))
    amap_key: str = os.getenv("AMAP_KEY") or os.getenv("AMAP_API_KEY", "")
    baidu_key: str = os.getenv("BAIDU_KEY") or os.getenv("BAIDU_API_KEY", "")
    tencent_key: str = os.getenv("TENCENT_KEY") or os.getenv("TENCENT_API_KEY", "")
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "15"))
    request_interval: float = float(os.getenv("REQUEST_INTERVAL", "0.25"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    website_enrichment_enabled: bool = os.getenv(
        "WEBSITE_ENRICHMENT_ENABLED", "true"
    ).lower() in {"1", "true", "yes", "on"}
    website_max_pages: int = max(1, min(int(os.getenv("WEBSITE_MAX_PAGES", "3")), 5))
    website_max_bytes: int = max(
        65536, min(int(os.getenv("WEBSITE_MAX_BYTES", "1000000")), 5000000)
    )
    website_request_interval: float = max(
        0.0, float(os.getenv("WEBSITE_REQUEST_INTERVAL", "0.5"))
    )

    def key_for(self, provider: str) -> str:
        return {
            "amap": self.amap_key,
            "baidu": self.baidu_key,
            "tencent": self.tencent_key,
        }.get(provider, "")


settings = Settings()
