from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import get_session
from app.main import app

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest.fixture()
def session() -> Iterator[Session]:
    models.Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        models.Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(session: Session) -> Iterator[TestClient]:
    def override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
def make_job() -> Callable[..., models.Job]:
    counter = {"value": 0}

    def _make_job(**overrides) -> models.Job:
        counter["value"] += 1
        number = counter["value"]
        now = datetime.now(UTC)
        defaults: dict = {
            "fingerprint": f"fingerprint-{number}",
            "source": "michael_page",
            "url": f"https://example.com/jobs/{number}",
            "title": "Security Engineer",
            "company": "Acme Corp",
            "location": "Tokyo",
            "remote_type": "hybrid",
            "employment_type": "full_time",
            "posted_at": now - timedelta(days=1),
            "first_seen_at": now,
            "last_seen_at": now,
            "role_category": "engineering",
            "language": "en",
            "location_scope": "japan_hybrid",
            "security_score": 80.0,
            "security_tags": ["security-engineering"],
            "date_confidence": "high",
        }
        defaults.update(overrides)
        return models.Job(**defaults)

    return _make_job
