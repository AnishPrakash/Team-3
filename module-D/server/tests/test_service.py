import pytest
from sqlmodel import Session

from app.models import Widget, WidgetStatus
from app.schemas import WidgetCreateRequest, WidgetUpdateRequest
from app import service
from app.errors import (
    WidgetNotFoundError,
    WidgetArchivedError,
    WidgetDuplicateError,
    VersionConflictError,
)

def test_create_and_get_widget(session: Session):
    req = WidgetCreateRequest(
        id="icon_pack",
        appdev_key="flutter_icon_pack",
        display_name="Icon Pack",
        category="media",
        flutter_classes=["Icon", "IconButton"],
    )
    widget = service.create_widget(session, req, actor="admin@test.com")

    assert widget.id == "icon_pack"
    assert widget.appdev_key == "flutter_icon_pack"
    assert widget.status == WidgetStatus.ACTIVE
    assert widget.version == 1

    fetched = service.get_widget(session, "icon_pack")
    assert fetched.display_name == "Icon Pack"


def test_duplicate_widget_rejection(session: Session):
    req = WidgetCreateRequest(
        id="row",
        appdev_key="flutter_row",
        display_name="Row Layout",
        category="layout",
    )
    service.create_widget(session, req, actor="admin@test.com")

    with pytest.raises(WidgetDuplicateError) as exc_info:
        service.create_widget(session, req, actor="admin@test.com")
    assert exc_info.value.field == "id"


def test_optimistic_locking_conflict(session: Session):
    req = WidgetCreateRequest(
        id="column",
        appdev_key="flutter_column",
        display_name="Column Layout",
        category="layout",
    )
    service.create_widget(session, req, actor="admin@test.com")

    update_req = WidgetUpdateRequest(display_name="New Column", expected_version=99)
    with pytest.raises(VersionConflictError) as exc_info:
        service.update_widget(session, "column", update_req, actor="admin@test.com")
    assert exc_info.value.current_version == 1
    assert exc_info.value.expected_version == 99


def test_archived_widget_behavior(session: Session):
    req = WidgetCreateRequest(
        id="banner",
        appdev_key="flutter_banner",
        display_name="Banner",
        category="media",
    )
    service.create_widget(session, req, actor="admin@test.com")

    service.archive_widget(session, "banner", actor="admin@test.com")

    widget = service.get_widget(session, "banner")
    assert widget.status == WidgetStatus.ARCHIVED

    with pytest.raises(WidgetArchivedError):
        service.require_active_widget(session, "banner")