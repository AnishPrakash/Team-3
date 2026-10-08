"""TEMP local app (PR 2: Modules D, E, F). Module A will own the real entrypoint."""

from fastapi import FastAPI

from app.core.errors import register_error_handlers
from app.modules.catalog.router import router as catalog_router
from app.modules.inventory.router import router as inventory_router
from app.modules.ledger.router import router as ledger_router

app = FastAPI(title="Flutter Wars backend — Team 3 local (Modules D, E, F)")
register_error_handlers(app)
app.include_router(catalog_router)  # Module D: GET /widgets, /widgets/{id}
app.include_router(ledger_router)  # Module E: GET /wallet, /wallet/ledger
app.include_router(inventory_router)  # Module F: GET /inventory
