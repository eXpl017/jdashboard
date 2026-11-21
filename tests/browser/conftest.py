from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import models  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _seed(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session: Session = SessionLocal()
    now = datetime.now(UTC)

    def add(**kwargs) -> None:
        defaults = {
            "fingerprint": kwargs.get("fingerprint") or f"fp-{len(session.new) + 1}",
            "source": "japan_dev",
            "url": "https://example.com/job",
            "title": "Job",
            "company": "Example Co",
            "location": "Tokyo, Japan",
            "remote_type": "onsite",
            "employment_type": "full_time",
            "posted_at": now - timedelta(days=1),
            "first_seen_at": now - timedelta(days=1),
            "last_seen_at": now,
            "role_category": "engineering",
            "language": "en",
            "location_scope": "japan_onsite",
            "security_score": 80.0,
            "security_tags": ["security-engineering"],
            "date_confidence": "high",
            "is_active": True,
        }
        defaults.update(kwargs)
        session.add(models.Job(**defaults))

    # Visible by default: technical (engineering/operations), japan scope, recent
    add(
        fingerprint="fp-eng",
        source="japan_dev",
        url="https://example.com/jobs/eng",
        title="Cloud Security Engineer",
        company="Kabu Security",
        location="Tokyo, Japan",
        remote_type="hybrid",
        location_scope="japan_hybrid",
        role_category="engineering",
        language="bilingual",
        visa_sponsorship=1,
        overseas_eligible=0,
        security_tags=["cloud-security", "security-engineering"],
        salary_min=8_000_000,
        salary_max=12_000_000,
        salary_currency="JPY",
        salary_text="¥8,000,000 - ¥12,000,000 / year",
        description_text="Build and secure cloud infrastructure in Japan.",
    )
    add(
        fingerprint="fp-ops",
        source="tokyo_dev",
        url="https://example.com/jobs/ops",
        title="SOC Analyst",
        company="Tokyo Monitoring",
        location="Osaka, Japan",
        remote_type="onsite",
        location_scope="japan_onsite",
        role_category="operations",
        language="ja",
        visa_sponsorship=0,
        overseas_eligible=None,
        security_tags=["soc", "incident-response"],
        description_text="Monitor alerts and respond to incidents.",
    )
    add(
        fingerprint="fp-remote-jp",
        source="daijob",
        url="https://example.com/jobs/remote-jp",
        title="Application Security Engineer",
        company="Remote JP Inc",
        location="Japan (Remote)",
        remote_type="remote",
        location_scope="japan_remote",
        role_category="engineering",
        language="en",
        visa_sponsorship=1,
        overseas_eligible=1,
        security_tags=["appsec"],
        description_text="Remote role for candidates in Japan.",
    )

    # Hidden from default view but present via filters
    add(
        fingerprint="fp-grc",
        source="michael_page",
        url="https://example.com/jobs/grc",
        title="GRC Specialist",
        company="Governance Ltd",
        location="Tokyo, Japan",
        remote_type="onsite",
        location_scope="japan_onsite",
        role_category="grc",
        language="en",
        security_tags=["grc"],
        description_text="Governance, risk, and compliance.",
    )
    add(
        fingerprint="fp-consulting",
        source="robert_half",
        url="https://example.com/jobs/consulting",
        title="Security Consultant",
        company="Consulting House",
        location="Tokyo, Japan",
        remote_type="hybrid",
        location_scope="japan_hybrid",
        role_category="consulting",
        language="bilingual",
        security_tags=["consulting"],
        description_text="Client-facing security consulting.",
    )
    add(
        fingerprint="fp-management",
        source="japan_dev",
        url="https://example.com/jobs/management",
        title="Security Manager",
        company="ManageSec",
        location="Tokyo, Japan",
        remote_type="onsite",
        location_scope="japan_onsite",
        role_category="management",
        language="ja",
        security_tags=["management"],
        description_text="Lead a security team.",
    )
    add(
        fingerprint="fp-international",
        source="tokyo_dev",
        url="https://example.com/jobs/international",
        title="Security Engineer (Global Remote)",
        company="Worldwide Co",
        location="Remote (Global)",
        remote_type="remote",
        location_scope="international_remote",
        role_category="engineering",
        language="en",
        visa_sponsorship=0,
        overseas_eligible=1,
        security_tags=["security-engineering"],
        description_text="Work from anywhere in the world.",
    )
    add(
        fingerprint="fp-unknown-lang",
        source="daijob",
        url="https://example.com/jobs/unknown-lang",
        title="セキュリティエンジニア",
        company="Nihon Corp",
        location="Tokyo, Japan",
        remote_type="onsite",
        location_scope="japan_onsite",
        role_category="engineering",
        language="unknown",
        security_tags=["security-engineering"],
        description_text="日本語の求人。",
        posted_at=now - timedelta(days=10),
        first_seen_at=now - timedelta(days=10),
    )

    try:
        session.commit()
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="session")
def browser_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    db_dir = tmp_path_factory.mktemp("browser-db")
    db_path = db_dir / "jobs.db"
    _seed(db_path)

    port = _free_port()
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env.setdefault("LOG_LEVEL", "WARNING")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    last_error: Exception | None = None
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"uvicorn exited early with code {proc.returncode}")
            try:
                resp = httpx.get(f"{base_url}/health", timeout=0.5)
                if resp.status_code == 200:
                    break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            time.sleep(0.1)
        else:
            raise RuntimeError(f"Server did not become healthy: {last_error}")

        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.fixture(scope="session")
def base_url(browser_server: str) -> str:
    """Override pytest-playwright's base_url to use the throwaway server."""
    return browser_server
