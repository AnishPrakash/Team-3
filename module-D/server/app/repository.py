from typing import Optional, List
from sqlmodel import Session, select
from app.models import Widget, WidgetStatus


def get_by_id(session: Session, widget_id: str) -> Optional[Widget]:
    """Fetch a single widget by its primary key string ID."""
    return session.get(Widget, widget_id)


def get_by_appdev_key(session: Session, appdev_key: str) -> Optional[Widget]:
    """Fetch a single widget by its unique AppDev matching key."""
    statement = select(Widget).where(Widget.appdev_key == appdev_key)
    return session.exec(statement).first()


def list_widgets(session: Session, include_archived: bool = False) -> List[Widget]:
    """Fetch all widgets. Filters out ARCHIVED items unless include_archived is True."""
    statement = select(Widget)
    if not include_archived:
        statement = statement.where(Widget.status == WidgetStatus.ACTIVE)
    return session.exec(statement).all()


def save(session: Session, widget: Widget) -> Widget:
    """Add or update a widget record in the session and flush to generate DB state."""
    session.add(widget)
    session.flush()  # Flushes changes to DB without committing caller's transaction
    return widget