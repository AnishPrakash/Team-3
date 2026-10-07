from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

# -------------------------------------------------------------------
# Response Schemas (Outgoing Data)
# -------------------------------------------------------------------

class WidgetPublicResponse(BaseModel):
    """Data returned to regular workshop participants (organizer notes stripped)."""
    id: str = Field(description="Unique string slug identifier")
    appdev_key: str = Field(description="Identifier matched by Flutter IDE")
    display_name: str
    description: Optional[str] = None
    category: str
    flutter_classes: List[str] = Field(default_factory=list)
    is_free: bool = False
    free_quantity: Optional[int] = None


class WidgetAdminResponse(WidgetPublicResponse):
    """Data returned to workshop organizers (includes sensitive/lifecycle fields)."""
    status: str
    internal_notes: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None


# -------------------------------------------------------------------
# Request Schemas (Incoming Data)
# -------------------------------------------------------------------

class WidgetCreateRequest(BaseModel):
    """Payload sent by an organizer to create a new widget."""
    id: str = Field(
        pattern=r"^[a-z][a-z0-9_]{1,39}$",
        description="Lowercase slug starting with a letter, 2-40 chars (e.g., 'icon_pack')"
    )
    appdev_key: str = Field(
        min_length=1,
        description="Unique string identifier expected by the AppDev IDE"
    )
    display_name: str = Field(min_length=1)
    description: Optional[str] = None
    category: str = Field(min_length=1)
    flutter_classes: List[str] = Field(default_factory=list)
    is_free: bool = False
    free_quantity: Optional[int] = Field(default=None, ge=0)
    internal_notes: Optional[str] = None


class WidgetUpdateRequest(BaseModel):
    """Payload sent by an organizer to modify widget metadata."""
    display_name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, min_length=1)
    flutter_classes: Optional[List[str]] = None
    is_free: Optional[bool] = None
    free_quantity: Optional[int] = Field(default=None, ge=0)
    internal_notes: Optional[str] = None
    
    # Optional for general updates, required for optimistic locking
    expected_version: Optional[int] = Field(
        default=None,
        ge=1, 
        description="The version number currently held by the organizer client"
    )