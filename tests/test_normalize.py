from app.services.normalize import (
    canonical_url,
    detect_employment_type,
    detect_language,
    detect_location_scope,
    detect_overseas_eligible,
    detect_remote,
    fingerprint,
    normalize_width,
    parse_salary,
    strip_html,
)


def test_strip_html():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert strip_html("") == ""


def test_normalize_width():
    assert normalize_width("ＳＯＣ　Ａｎａｌｙｓｔ") == "SOC Analyst"


def test_parse_salary_millions():
    parts = parse_salary("¥8M ~ ¥17M")
    assert (parts.min, parts.max, parts.period) == (8_000_000, 17_000_000, "unknown")


def test_parse_salary_million_words():
    parts = parse_salary("8 million yen")
    assert parts.min == 8_000_000
    assert parts.max == 8_000_000


def test_parse_salary_hourly():
    parts = parse_salary("¥2,000 – ¥2,300 / Hour")
    assert (parts.min, parts.max, parts.period) == (2000, 2300, "hourly")


def test_parse_salary_japanese_man():
    parts = parse_salary("年収800万～1200万")
    assert (parts.min, parts.max, parts.period) == (8_000_000, 12_000_000, "annual")


def test_parse_salary_empty():
    parts = parse_salary(None)
    assert parts.min is None
    assert parts.max is None
    assert parts.period == "unknown"


def test_detect_remote():
    assert detect_remote("Fully remote") == "remote"
    assert detect_remote("ハイブリッド勤務") == "hybrid"
    assert detect_remote("フルリモート") == "remote"
    assert detect_remote("出社必須") == "onsite"
    assert detect_remote("No remote work available") == "onsite"
    assert detect_remote("") == "unknown"


def test_detect_employment_type():
    assert detect_employment_type("正社員") == "full_time"
    assert detect_employment_type("Contract") == "contract"
    assert detect_employment_type("Part Time") == "part_time"
    assert detect_employment_type("Internship") == "internship"
    assert detect_employment_type("FULL_TIME") == "full_time"
    assert detect_employment_type("PART_TIME") == "part_time"
    assert detect_employment_type("CONTRACTOR") == "contract"
    assert detect_employment_type("") == "unknown"


def test_detect_language():
    assert detect_language("Security Engineer", "Build secure systems") == "en"
    assert detect_language("セキュリティエンジニア", "情報セキュリティを担当") == "ja"
    assert (
        detect_language("Security Engineer", "セキュリティエンジニアとして勤務")
        == "bilingual"
    )
    assert detect_language("", "") == "unknown"


def test_detect_location_scope():
    assert detect_location_scope("Tokyo", "hybrid") == "japan_hybrid"
    assert detect_location_scope("Japan", "remote") == "japan_remote"
    assert (
        detect_location_scope("Worldwide", "remote", "Work from anywhere")
        == "international_remote"
    )
    assert detect_location_scope(None, "onsite") == "unknown"


def test_detect_overseas_eligible():
    assert detect_overseas_eligible("Applications from overseas are welcome") is True
    assert detect_overseas_eligible("海外からの応募可") is True
    assert detect_overseas_eligible("日本在住の方") is False
    assert detect_overseas_eligible("No info") is None


def test_canonical_url_and_fingerprint():
    url = "HTTPS://Example.com//jobs/1?utm_source=x&ref=y#frag"
    assert canonical_url(url) == "https://example.com/jobs/1"
    assert canonical_url(url, allowed_query_params=("ref",)) == (
        "https://example.com/jobs/1?ref=y"
    )
    assert fingerprint("michael_page", url) == fingerprint(
        "michael_page", "https://example.com/jobs/1"
    )
