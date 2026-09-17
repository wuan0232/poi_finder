from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import models  # noqa: F401 - 注册 SQLAlchemy 表模型
from database import Base, engine
from routers.tasks import router as tasks_router


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="周边同类机构信息采集系统",
    description="统一采集高德、百度、腾讯地图中的 POI 数据。",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(tasks_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
