import sys
from pathlib import Path
import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

# Force the server root directory into sys.path
server_dir = Path(__file__).resolve().parent.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from main import app
from app.router import get_db

@pytest.fixture(name="session")
def session_fixture():
    """Creates a shared in-memory database session with initialized table schemas."""
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Overrides app get_db dependency to use test session."""
    def get_db_override():
        return session

    app.dependency_overrides[get_db] = get_db_override
    from fastapi.testclient import TestClient
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()