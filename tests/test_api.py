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
