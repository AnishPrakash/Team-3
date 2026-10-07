from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel, Session, create_engine

from app.models import Widget  # Ensures table metadata is registered
from app.router import router as catalog_router, get_db

# Local SQLite database engine for development
DATABASE_URL = "sqlite:///./catalog.db"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)


def get_db_override():
    """Provides an active database session for local dev requests."""
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Automatically creates database tables on startup."""
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Flutter Wars - Module D (Widget Catalog)",
    lifespan=lifespan,
)

# Wire the local database session into router dependency
app.dependency_overrides[get_db] = get_db_override

# Register endpoints
app.include_router(catalog_router)


@app.get("/")
def root():
    return {"message": "Module D Widget Catalog Service is running!"}