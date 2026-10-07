from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import Session

from app import repository
from app.models import Widget, WidgetStatus
from app.schemas import WidgetCreateRequest, WidgetUpdateRequest
from app.errors import (
    WidgetNotFoundError,
    WidgetArchivedError,
    WidgetDuplicateError,
    VersionConflictError,
)

def create_widget(session: Session, req: WidgetCreateRequest, actor: str) -> Widget:
    # Check duplicate ID
    if repository.get_by_id(session, req.id):
        raise WidgetDuplicateError(field="id", value=req.id)
    
    # Check duplicate appdev_key
    if repository.get_by_appdev_key(session, req.appdev_key):
        raise WidgetDuplicateError(field="appdev_key", value=req.appdev_key)

    widget = Widget(
        id=req.id,
        appdev_key=req.appdev_key,
        display_name=req.display_name,
        description=req.description,
        category=req.category,
        flutter_classes=req.flutter_classes,
        is_free=req.is_free,
        free_quantity=req.free_quantity,
        internal_notes=f"Created by {actor}",
    )
    return repository.save(session, widget)

def get_widget(session: Session, widget_id: str) -> Widget:
    widget = repository.get_by_id(session, widget_id)
    if not widget:
        raise WidgetNotFoundError(widget_id)
    return widget

def require_active_widget(session: Session, widget_id: str) -> Widget:
    widget = get_widget(session, widget_id)
    if widget.status == WidgetStatus.ARCHIVED:
        raise WidgetArchivedError(widget_id)
    return widget

def update_widget(session: Session, widget_id: str, req: WidgetUpdateRequest, actor: str) -> Widget:
    widget = require_active_widget(session, widget_id)

    if req.expected_version is not None and widget.version != req.expected_version:
        raise VersionConflictError(current_version=widget.version, expected_version=req.expected_version)

    update_data = req.model_dump(exclude_unset=True, exclude={"expected_version"})
    for key, value in update_data.items():
        setattr(widget, key, value)

    widget.version += 1
    widget.updated_at = datetime.now(timezone.utc)
    widget.internal_notes = f"Updated by {actor}"

    return repository.save(session, widget)

def archive_widget(session: Session, widget_id: str, actor: str) -> Widget:
    widget = require_active_widget(session, widget_id)

    widget.status = WidgetStatus.ARCHIVED
    widget.archived_at = datetime.now(timezone.utc)
    widget.updated_at = datetime.now(timezone.utc)
    widget.internal_notes = f"Archived by {actor}"

    return repository.save(session, widget)

def list_widgets(session: Session, include_archived: bool = False) -> List[Widget]:
    return repository.list_widgets(session, include_archived=include_archived)

list_active_widgets = list_widgets