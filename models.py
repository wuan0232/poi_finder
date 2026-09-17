from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    center_name: Mapped[str | None] = mapped_column(String(255))
    center_address: Mapped[str | None] = mapped_column(String(500))
    keyword: Mapped[str | None] = mapped_column(String(100))
    types_code: Mapped[str | None] = mapped_column(String(20))
    radius_m: Mapped[int | None] = mapped_column(Integer)
    center_lng: Mapped[float | None] = mapped_column(Float)
    center_lat: Mapped[float | None] = mapped_column(Float)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    keywords_json: Mapped[str] = mapped_column(Text, nullable=False)
    providers_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    pois: Mapped[list["Poi"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class Poi(Base):
    __tablename__ = "pois"
    __table_args__ = (
        Index("ix_pois_task_provider", "task_id", "provider"),
        Index("ix_pois_task_name", "task_id", "name"),
        Index(
            "uq_pois_task_provider_source",
            "task_id",
            "provider",
            "source_id",
            unique=True,
            sqlite_where=text("source_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(200))
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str | None] = mapped_column(String(300))
    address: Mapped[str | None] = mapped_column(String(500))
    province: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(100))
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    extra_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    task: Mapped[Task] = relationship(back_populates="pois")
