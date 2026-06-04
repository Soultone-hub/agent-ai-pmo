"""
Configuration centrale de pytest pour toute la suite de tests.
Utilise une base SQLite en mémoire pour ne pas toucher la vraie DB PostgreSQL.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.db import Base, get_db
from backend.main import app

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"

# Monkeypatch UUID bind processor for SQLite to avoid "AttributeError: 'str' object has no attribute 'hex'"
from sqlalchemy.types import UUID
import uuid
original_bind_processor = UUID.bind_processor

def patched_bind_processor(self, dialect):
    proc = original_bind_processor(self, dialect)
    if proc is None:
        return proc
    def process(value):
        if isinstance(value, str):
            try:
                value = uuid.UUID(value)
            except ValueError:
                pass
        return proc(value)
    return process

UUID.bind_processor = patched_bind_processor

# ─── Base de données de test (SQLite en mémoire) ─────────────────────────────
TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Même connexion pour tous les threads
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    """Remplace la dépendance get_db par la DB de test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Crée toutes les tables avant les tests, les supprime après."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(scope="function")
def db_session():
    """Fournit une session de DB propre (rollback après chaque test)."""
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def client():
    """Client HTTP de test avec la DB de test injectée."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def auth_headers(client):
    """
    Crée un utilisateur de test, se connecte et retourne les headers JWT.
    Utilisé par tous les tests nécessitant une authentification.
    """
    # Inscription
    client.post("/api/auth/register", json={
        "first_name": "Test",
        "last_name": "User",
        "email": "test@pmo.bj",
        "password": "TestPassword123!"
    })

    # Connexion
    response = client.post("/api/auth/login", json={
        "email": "test@pmo.bj",
        "password": "TestPassword123!"
    })

    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
