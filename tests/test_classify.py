from app.services.classify import classify


def test_security_engineer_is_engineering():
    result = classify("Security Engineer", "AppSec and cloud security")
    assert result.role_category == "engineering"
    assert result.score >= 60
    assert "security-engineering" in result.tags


def test_security_category_prior_boosts_score():
    result = classify(
        "Security Engineer",
        "AppSec and cloud security",
        source_is_security_category=True,
    )
    assert result.score >= 90


def test_security_consultant_is_consulting():
    assert classify("Security Consultant").role_category == "consulting"


def test_ciso_is_management():
    assert classify("CISO").role_category == "management"


def test_soc_analyst_is_operations():
    result = classify("SOC Analyst", "Monitor alerts in the SOC")
    assert result.role_category == "operations"
    assert "soc" in result.tags


def test_information_security_analyst_is_operations():
    assert classify("Information Security Analyst").role_category == "operations"


def test_grc_analyst_is_grc():
    assert classify("GRC Analyst").role_category == "grc"


def test_japanese_engineer_title():
    result = classify("セキュリティエンジニア", "情報セキュリティを担当")
    assert result.role_category == "engineering"
    assert result.language == "ja"
    assert "japanese" in result.tags


def test_guard_is_demoted():
    result = classify("警備員", "ビル警備")
    assert result.role_category == "other"
    assert result.score == 0


def test_non_security_role_scores_low():
    result = classify("Marketing Manager", "Run campaigns")
    assert result.role_category == "management"
    assert result.score == 0
