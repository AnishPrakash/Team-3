from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app import service, schemas
from app.errors import (
    WidgetNotFoundError,
    WidgetArchivedError,
    WidgetDuplicateError,
    FieldImmutableError,
    VersionConflictError,
)

# -------------------------------------------------------------------
# Temporary Authentication & Database Shims (Until Modules A & B merge)
# -------------------------------------------------------------------

def get_db():
    """Temporary database session dependency shim."""
    # Will be replaced by Module A's database session dependency
    raise NotImplementedError("Database dependency not wired yet.")


class DummyPrincipal:
    email: str = "organizer@gdg.org"
    is_organizer: bool = True


def require_organizer():
    """Temporary organizer auth check shim."""
    # Will be replaced by Module B / Module K auth dependencies
    return DummyPrincipal()


# -------------------------------------------------------------------
# Router Definition & Exception Mapping Helper
# -------------------------------------------------------------------

router = APIRouter(tags=["Widget Catalog"])


def handle_catalog_error(err: Exception) -> None:
    """Helper function to translate internal domain exceptions into FastAPI HTTPExceptions."""
    if isinstance(err, WidgetNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WIDGET_NOT_FOUND", "message": str(err)},
        )
    elif isinstance(err, WidgetArchivedError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WIDGET_ARCHIVED", "message": str(err)},
        )
    elif isinstance(err, WidgetDuplicateError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "WIDGET_DUPLICATE", "message": str(err)},
        )
    elif isinstance(err, FieldImmutableError):
        raise HTTPException(
            status_code=status.FIELD_IMMUTABLE if hasattr(status, "FIELD_IMMUTABLE") else status.HTTP_400_BAD_REQUEST,
            detail={"code": "FIELD_IMMUTABLE", "message": str(err)},
        )
    elif isinstance(err, VersionConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT", "message": str(err)},
        )
    raise err


# -------------------------------------------------------------------
# Participant Routes
# -------------------------------------------------------------------

@router.get("/widgets", response_model=List[schemas.WidgetPublicResponse])
def get_public_widgets(session: Session = Depends(get_db)):
    """Fetch all active widgets available in the workshop catalog."""
    return service.list_widgets(session, include_archived=False)


@router.get("/widgets/{widget_id}", response_model=schemas.WidgetPublicResponse)
def get_public_widget(widget_id: str, session: Session = Depends(get_db)):
    """Fetch metadata for a single active widget."""
    try:
        return service.require_active_widget(session, widget_id)
    except Exception as err:
        handle_catalog_error(err)


# -------------------------------------------------------------------
# Organizer / Admin Routes
# -------------------------------------------------------------------

@router.post(
    "/admin/widgets",
    response_model=schemas.WidgetAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_widget(
    payload: schemas.WidgetCreateRequest,
    session: Session = Depends(get_db),
    principal: DummyPrincipal = Depends(require_organizer),
):
    """Create a new widget in the catalog (Organizer only)."""
    try:
        return service.create_widget(session, payload, actor=principal.email)
    except Exception as err:
        handle_catalog_error(err)


@router.patch("/admin/widgets/{widget_id}", response_model=schemas.WidgetAdminResponse)
def update_widget(
    widget_id: str,
    payload: schemas.WidgetUpdateRequest,
    session: Session = Depends(get_db),
    principal: DummyPrincipal = Depends(require_organizer),
):
    """Update widget metadata with optimistic version checking (Organizer only)."""
    try:
        return service.update_widget(session, widget_id, payload, actor=principal.email)
    except Exception as err:
        handle_catalog_error(err)


@router.post("/admin/widgets/{widget_id}/archive", response_model=schemas.WidgetAdminResponse)
def archive_widget(
    widget_id: str,
    session: Session = Depends(get_db),
    principal: DummyPrincipal = Depends(require_organizer),
):
    """Archive a widget so it can no longer be listed or purchased (Organizer only)."""
    try:
        return service.archive_widget(session, widget_id, actor=principal.email)
    except Exception as err:
        handle_catalog_error(err)