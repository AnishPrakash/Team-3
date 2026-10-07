from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, JSON, Column

class WidgetStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

class Widget(SQLModel, table=True):
    __tablename__ = "widget"

    id: str = Field(primary_key=True)
    appdev_key: str = Field(unique=True, index=True)
    display_name: str
    description: Optional[str] = None
    category: str
    flutter_classes: List[str] = Field(default=[], sa_column=Column(JSON))
    
    is_free: bool = Field(default=False)
    free_quantity: Optional[int] = None
    
    status: WidgetStatus = Field(default=WidgetStatus.ACTIVE)
    internal_notes: Optional[str] = None
    version: int = Field(default=1)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    archived_at: Optional[datetime] = None