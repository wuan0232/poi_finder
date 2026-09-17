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
    amap_key: str = os.getenv("AMAP_KEY", "")
    baidu_key: str = os.getenv("BAIDU_KEY", "")
    tencent_key: str = os.getenv("TENCENT_KEY", "")
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "15"))
    request_interval: float = float(os.getenv("REQUEST_INTERVAL", "0.25"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))

    def key_for(self, provider: str) -> str:
        return {
            "amap": self.amap_key,
            "baidu": self.baidu_key,
            "tencent": self.tencent_key,
        }.get(provider, "")


settings = Settings()
