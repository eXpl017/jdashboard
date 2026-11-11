from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app import repository
from app.models import Job


def test_upsert_inserts_new_job(session, make_job) -> None:
    job, created = repository.upsert_job(session, make_job(fingerprint="fp-1"))

    assert created is True
    assert repository.get_job(session, job.id) is not None
    jobs, total = repository.query_jobs(session, days=3)
    assert total == 1
    assert jobs[0].id == job.id


def test_upsert_is_idempotent_and_preserves_first_seen(session, make_job) -> None:
    job, created = repository.upsert_job(
        session, make_job(fingerprint="fp-1", title="Old title")
    )
    assert created is True
    first_seen = job.first_seen_at

    updated, created_again = repository.upsert_job(
        session, make_job(fingerprint="fp-1", title="New title")
    )

    assert created_again is False
    assert updated.id == job.id
    assert updated.title == "New title"
    assert updated.first_seen_at == first_seen
    count = session.execute(select(func.count()).select_from(Job)).scalar_one()
    assert count == 1


def test_default_query_is_technical_and_japan_only(session, make_job) -> None:
    technical = repository.upsert_job(session, make_job(fingerprint="fp-tech"))[0]
    repository.upsert_job(
        session, make_job(fingerprint="fp-grc", role_category="grc")
    )
    repository.upsert_job(
        session,
        make_job(fingerprint="fp-intl", location_scope="international_remote"),
    )

    jobs, total = repository.query_jobs(session)

    assert total == 1
    assert [job.id for job in jobs] == [technical.id]


def test_language_filter_matches_bilingual(session, make_job) -> None:
    english = repository.upsert_job(session, make_job(fingerprint="fp-en", language="en"))[0]
    japanese = repository.upsert_job(session, make_job(fingerprint="fp-ja", language="ja"))[0]
    bilingual = repository.upsert_job(
        session, make_job(fingerprint="fp-bi", language="bilingual")
    )[0]

    jobs, total = repository.query_jobs(session, language="en")
    assert total == 2
    assert {job.id for job in jobs} == {english.id, bilingual.id}

    jobs, total = repository.query_jobs(session, language="ja")
    assert total == 2
    assert {job.id for job in jobs} == {japanese.id, bilingual.id}


def test_tag_filter(session, make_job) -> None:
    soc = repository.upsert_job(
        session,
        make_job(fingerprint="fp-soc", security_tags=["soc", "incident-response"]),
    )[0]
    repository.upsert_job(
        session, make_job(fingerprint="fp-appsec", security_tags=["appsec"])
    )

    jobs, total = repository.query_jobs(session, tag="soc")

    assert total == 1
    assert jobs[0].id == soc.id


def test_visa_filter(session, make_job) -> None:
    overseas = repository.upsert_job(
        session, make_job(fingerprint="fp-os", overseas_eligible=1)
    )[0]
    sponsored = repository.upsert_job(
        session, make_job(fingerprint="fp-sp", visa_sponsorship="Yes")
    )[0]
    repository.upsert_job(session, make_job(fingerprint="fp-none"))

    jobs, total = repository.query_jobs(session, visa="either")

    assert total == 2
    assert {job.id for job in jobs} == {overseas.id, sponsored.id}


def test_days_filter_and_include_active(session, make_job) -> None:
    old = make_job(
        fingerprint="fp-old",
        posted_at=datetime.now(UTC) - timedelta(days=10),
    )
    repository.upsert_job(session, old)
    fresh = repository.upsert_job(session, make_job(fingerprint="fp-fresh"))[0]

    jobs, total = repository.query_jobs(session, days=3)
    assert total == 1
    assert jobs[0].id == fresh.id

    _, total = repository.query_jobs(session, days=3, include_active=True)
    assert total == 2


def test_query_filters_by_source_and_text(session, make_job) -> None:
    michael = repository.upsert_job(
        session,
        make_job(fingerprint="fp-mp", source="michael_page", title="SOC Analyst"),
    )[0]
    repository.upsert_job(
        session,
        make_job(
            fingerprint="fp-daijob",
            source="daijob",
            title="セキュリティエンジニア",
        ),
    )

    jobs, total = repository.query_jobs(session, source="michael_page")
    assert total == 1
    assert jobs[0].id == michael.id

    jobs, total = repository.query_jobs(session, q="SOC")
    assert total == 1
    assert jobs[0].id == michael.id


def test_stats_counts(session, make_job) -> None:
    repository.upsert_job(
        session,
        make_job(
            fingerprint="fp-1",
            source="michael_page",
            role_category="engineering",
            overseas_eligible=1,
        ),
    )
    repository.upsert_job(
        session, make_job(fingerprint="fp-2", source="daijob", role_category="grc")
    )

    stats = repository.get_stats(session)

    assert stats["total_jobs"] == 2
    assert stats["by_source"] == {"daijob": 1, "michael_page": 1}
    assert stats["by_role_category"] == {"engineering": 1, "grc": 1}
    assert stats["relocation_friendly"] == 1
    assert stats["last_run"] is None


def test_run_and_source_result_records(session) -> None:
    run = repository.create_run(session, trigger="manual", window_days=3)
    assert run.status == "running"

    result = repository.create_source_result(
        session, run_id=run.id, source="michael_page"
    )
    repository.finish_source_result(
        session, result.id, status="success", found=10, new=2
    )
    repository.finish_run(
        session, run.id, status="success", total_found=10, total_new=2
    )

    stats = repository.get_stats(session)
    assert stats["last_run"] is not None
    assert stats["last_run"].id == run.id
    assert stats["last_run"].status == "success"
