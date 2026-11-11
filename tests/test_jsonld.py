import json

from app.services.jsonld import extract_job_posting_jsonld


def test_extracts_single_job_posting():
    payload = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Security Engineer",
    }
    html = f'<script type="application/ld+json">{json.dumps(payload)}</script>'
    result = extract_job_posting_jsonld(html)
    assert result is not None
    assert result["title"] == "Security Engineer"


def test_extracts_job_posting_from_graph():
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "Acme"},
            {"@type": "JobPosting", "title": "SOC Analyst"},
        ],
    }
    html = f'<script type="application/ld+json">{json.dumps(payload)}</script>'
    result = extract_job_posting_jsonld(html)
    assert result is not None
    assert result["title"] == "SOC Analyst"


def test_extracts_job_posting_from_list():
    payload = [
        {"@type": "WebPage", "name": "Jobs"},
        {"@type": "JobPosting", "title": "AppSec Engineer"},
    ]
    html = f'<script type="application/ld+json">{json.dumps(payload)}</script>'
    result = extract_job_posting_jsonld(html)
    assert result is not None
    assert result["title"] == "AppSec Engineer"


def test_returns_none_when_missing():
    assert extract_job_posting_jsonld("<html><body>No JSON-LD</body></html>") is None
    assert extract_job_posting_jsonld("") is None
