"""Module D table. Must mirror migrations/versions/0002_catalog.py exactly.

Original design by our teammate (fields, statuses, optimistic `version`); hardened for
PostgreSQL: bounded column sizes, JSONB, DB-side timestamps, CHECKs and triggers.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

WIDGET_ID_PATTERN = r"^[a-z][a-z0-9_]{1,39}$"  # same rule Module F uses for widget_id
MAX_FREE_QUANTITY = 10_000


class WidgetStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class Widget(SQLModel, table=True):
    __tablename__ = "widget"
    __table_args__ = (
        CheckConstraint("id ~ '^[a-z][a-z0-9_]{1,39}$'", name="ck_widget_id_format"),
        CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_widget_status"),
        CheckConstraint("(status = 'ARCHIVED') = (archived_at IS NOT NULL)", name="ck_widget_archived_at"),
        CheckConstraint(
            "free_quantity IS NULL OR (is_free AND free_quantity BETWEEN 0 AND 10000)",
            name="ck_widget_free_quantity",
        ),
        CheckConstraint("jsonb_typeof(flutter_classes) = 'array'", name="ck_widget_classes_array"),
        CheckConstraint("version >= 1", name="ck_widget_version_pos"),
        Index("ix_widget_status", "status"),
    )

    id: str = Field(sa_column=Column(String(40), primary_key=True))
    appdev_key: str = Field(sa_column=Column(String(80), nullable=False, unique=True))
    display_name: str = Field(sa_column=Column(String(60), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(String(500), nullable=True))
    category: str = Field(sa_column=Column(String(30), nullable=False))
    flutter_classes: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    )
    is_free: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default=text("false")))
    free_quantity: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    status: str = Field(
        default=WidgetStatus.ACTIVE.value, sa_column=Column(String(16), nullable=False, server_default="ACTIVE")
    )
    internal_notes: str | None = Field(default=None, sa_column=Column(String(1000), nullable=True))
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, server_default=text("1")))
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    archived_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    @property
    def archived(self) -> bool:
        return self.status == WidgetStatus.ARCHIVED.value
