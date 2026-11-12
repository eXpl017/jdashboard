from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_format_utc, return_type=str)]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fingerprint: str
    source: str
    source_name: str = ""
    source_job_id: str | None = None
    url: str
    title: str
    company: str | None = None
    location: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    salary_text: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "JPY"
    description_text: str | None = None
    description_html: str | None = None
    posted_at: UtcDateTime | None = None
    posted_at_raw: str | None = None
    source_updated_at: UtcDateTime | None = None
    expires_at: UtcDateTime | None = None
    first_seen_at: UtcDateTime
    last_seen_at: UtcDateTime
    is_active: bool = True
    security_score: float = 0.0
    security_tags: list[str] = Field(default_factory=list)
    role_category: str = "other"
    language: str = "unknown"
    location_scope: str = "unknown"
    overseas_eligible: int | None = None
    japanese_level: str | None = None
    visa_sponsorship: str | None = None
    date_confidence: str = "low"
    created_at: UtcDateTime
    updated_at: UtcDateTime
    is_new: bool = False


class JobListResponse(BaseModel):
    items: list[JobRead]
    total: int
    limit: int = 50
    offset: int = 0


class ScrapeRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: UtcDateTime
    finished_at: UtcDateTime | None = None
    status: str
    trigger: str
    window_days: int
    total_found: int = 0
    total_new: int = 0
    total_updated: int = 0
    total_errors: int = 0
    error_summary: str | None = None


class StatsResponse(BaseModel):
    total_jobs: int
    new_in_window: int
    by_source: dict[str, int]
    by_role_category: dict[str, int]
    by_tag: dict[str, int] = Field(default_factory=dict)
    relocation_friendly: int
    last_run: ScrapeRunRead | None = None


class SourceRead(BaseModel):
    id: str
    name: str
    url: str
    enabled: bool = True
    last_status: str = "never"
    last_success_at: UtcDateTime | None = None
    last_error: str | None = None


class SourceListResponse(BaseModel):
    sources: list[SourceRead]


class RefreshRequest(BaseModel):
    window_days: int = Field(default=3, ge=1, le=30)


class RefreshStartResponse(BaseModel):
    run_id: int
    status: str = "running"


class SourceProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = "pending"
    found: int = 0
    new: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_message: str | None = None


class RefreshStatusResponse(BaseModel):
    run_id: int | None = None
    status: str = "idle"
    started_at: UtcDateTime | None = None
    finished_at: UtcDateTime | None = None
    current_source: str | None = None
    sources: dict[str, SourceProgressRead] = Field(default_factory=dict)
