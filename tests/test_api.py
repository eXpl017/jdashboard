from app import repository


def test_list_jobs_empty(client) -> None:
    response = client.get("/api/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_jobs_uses_default_filters(client, session, make_job) -> None:
    technical = repository.upsert_job(session, make_job(fingerprint="fp-tech"))[0]
    repository.upsert_job(session, make_job(fingerprint="fp-grc", role_category="grc"))
    repository.upsert_job(
        session,
        make_job(fingerprint="fp-intl", location_scope="international_remote"),
    )
    session.commit()

    response = client.get("/api/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == technical.id
    assert body["items"][0]["role_category"] == "engineering"
    assert body["items"][0]["language"] == "en"


def test_list_jobs_can_widen_role_and_location_scope(client, session, make_job) -> None:
    repository.upsert_job(session, make_job(fingerprint="fp-tech"))
    repository.upsert_job(session, make_job(fingerprint="fp-grc", role_category="grc"))
    repository.upsert_job(
        session,
        make_job(fingerprint="fp-intl", location_scope="international_remote"),
    )
    session.commit()

    response = client.get("/api/jobs", params={"role": "all", "location_scope": "all"})

    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_get_job_ok(client, session, make_job) -> None:
    job = repository.upsert_job(session, make_job(fingerprint="fp-1"))[0]
    session.commit()

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Security Engineer"
    assert body["posted_at"].endswith("Z")


def test_get_job_missing_returns_404(client) -> None:
    response = client.get("/api/jobs/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_stats_endpoint(client, session, make_job) -> None:
    repository.upsert_job(
        session, make_job(fingerprint="fp-1", source="michael_page")
    )
    session.commit()

    response = client.get("/api/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["total_jobs"] == 1
    assert body["by_source"] == {"michael_page": 1}
    assert body["last_run"] is None


def test_list_jobs_include_source_name(client, session, make_job) -> None:
    repository.upsert_job(
        session, make_job(fingerprint="fp-1", source="michael_page")
    )[0]
    session.commit()

    response = client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json()["items"][0]["source_name"] == "Michael Page Japan"


def test_sources_endpoint_returns_registered_sources(client) -> None:
    response = client.get("/api/sources")

    assert response.status_code == 200
    body = response.json()
    assert [source["id"] for source in body["sources"]] == [
        "michael_page",
        "japan_dev",
        "tokyo_dev",
        "daijob",
        "robert_half",
    ]
    assert body["sources"][0]["name"] == "Michael Page Japan"
    assert body["sources"][0]["enabled"] is True
    assert body["sources"][0]["last_status"] == "never"
    assert body["sources"][0]["last_success_at"] is None
    assert body["sources"][0]["last_error"] is None


def test_sources_endpoint_reflects_latest_run(client, session) -> None:
    run = repository.create_run(session, trigger="manual", window_days=3)
    result = repository.create_source_result(session, run_id=run.id, source="daijob")
    repository.finish_source_result(
        session, result.id, status="error", errors=1, error_message="blocked"
    )
    repository.finish_run(session, run.id, status="failed", total_errors=1)

    response = client.get("/api/sources")

    assert response.status_code == 200
    body = response.json()
    daijob = next(source for source in body["sources"] if source["id"] == "daijob")
    assert daijob["last_status"] == "error"
    assert daijob["last_error"] == "blocked"


def test_stats_endpoint_respects_filters_and_window(client, session, make_job) -> None:
    repository.upsert_job(
        session, make_job(fingerprint="fp-tech", source="michael_page")
    )
    repository.upsert_job(
        session, make_job(fingerprint="fp-grc", source="daijob", role_category="grc")
    )
    session.commit()

    response = client.get(
        "/api/stats", params={"role": "all", "location_scope": "all", "days": 0}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_jobs"] == 2
    assert body["by_tag"] == {"security-engineering": 2}


def test_stats_endpoint_tags_and_relocation(client, session, make_job) -> None:
    repository.upsert_job(
        session, make_job(fingerprint="fp-1", source="michael_page", security_tags=["soc"])
    )
    repository.upsert_job(
        session,
        make_job(fingerprint="fp-2", source="michael_page", security_tags=["soc"]),
    )
    session.commit()

    response = client.get("/api/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["by_tag"] == {"soc": 2}
    assert body["total_jobs"] == 2
    assert body["relocation_friendly"] == 0
