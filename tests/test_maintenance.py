"""
Tests de la purge RGPD des comptes archivés (maintenance_service).
Engine SQLite dédié par test → commit réel + isolation parfaite.
"""
import datetime
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.db import Base
import backend.models.project  # noqa: F401 — enregistre la table projects sur Base
from backend.models.user import User
from backend.services.maintenance_service import purge_archived_users


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(email: str, archived_days_ago: int | None = None) -> User:
    u = User(id=uuid.uuid4(), email=email, password_hash="x", is_confirmed=True)
    if archived_days_ago is not None:
        u.archived_at = datetime.datetime.now() - datetime.timedelta(days=archived_days_ago)
    return u


def test_purge_supprime_uniquement_les_comptes_expires(db):
    db.add_all([
        _user("active@pmo.bj"),                       # jamais archivé
        _user("recent@pmo.bj", archived_days_ago=30),  # archivé < 90 j
        _user("old@pmo.bj", archived_days_ago=120),    # archivé > 90 j → purgé
    ])
    db.commit()

    result = purge_archived_users(db, retention_days=90)

    assert result == {"users": 1, "projects": 0, "collections": 0}
    emails = {e for (e,) in db.query(User.email).all()}
    assert emails == {"active@pmo.bj", "recent@pmo.bj"}


def test_purge_noop_si_rien_a_purger(db):
    db.add(_user("a@pmo.bj"))
    db.add(_user("b@pmo.bj", archived_days_ago=10))
    db.commit()

    assert purge_archived_users(db, retention_days=90) == {"users": 0, "projects": 0, "collections": 0}


def test_purge_respecte_la_retention_personnalisee(db):
    db.add(_user("c@pmo.bj", archived_days_ago=40))
    db.commit()

    # Avec une rétention de 30 j, le compte archivé depuis 40 j doit partir
    result = purge_archived_users(db, retention_days=30)
    assert result["users"] == 1
    assert db.query(User).count() == 0
