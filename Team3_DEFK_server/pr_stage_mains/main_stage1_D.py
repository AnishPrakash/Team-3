"""TEMP local app (PR 1: Module D only). Module A will own the real entrypoint."""

from fastapi import FastAPI

from app.core.errors import register_error_handlers
from app.modules.catalog.router import router as catalog_router

app = FastAPI(title="Flutter Wars backend — Team 3 local (Module D)")
register_error_handlers(app)
app.include_router(catalog_router)  # Module D: GET /widgets, /widgets/{id}
