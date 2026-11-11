import re
from dataclasses import dataclass, field

from app.services.normalize import detect_language, normalize_whitespace, normalize_width

CORE_SECURITY_TERMS = (
    "security",
    "cybersecurity",
    "cyber security",
    "cyber",
    "infosec",
    "information security",
    "セキュリティ",
    "サイバー",
    "情報セキュリティ",
    "サイバーセキュリティ",
)

# Canonical tag -> keywords (English + Japanese).
TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "appsec": ("appsec", "application security", "アプリケーションセキュリティ"),
    "cloud-security": ("cloud security", "クラウドセキュリティ"),
    "devsecops": ("devsecops", "dev sec ops", "セキュリティ開発"),
    "grc": ("grc", "governance", "ガバナンス"),
    "iam": ("iam", "identity and access", "アイデンティティ", "アクセス管理"),
    "incident-response": ("incident response", "incident handling", "インシデント対応"),
    "isms": ("isms", "iso 27001", "iso27001"),
    "network-security": (
        "network security",
        "ネットワークセキュリティ",
        "firewall",
        "ファイアウォール",
    ),
    "penetration-testing": (
        "penetration test",
        "penetration testing",
        "pentest",
        "ペネトレーションテスト",
        "脆弱性診断",
    ),
    "product-security": ("product security", "プロダクトセキュリティ"),
    "red-team": ("red team", "レッドチーム"),
    "blue-team": ("blue team", "ブルーチーム"),
    "security-engineering": (
        "security engineer",
        "cybersecurity engineer",
        "security engineering",
        "セキュリティエンジニア",
        "セキュリティ設計",
    ),
    "security-operations": (
        "security operations",
        "セキュリティ運用",
        "セキュリティ監視",
    ),
    "soc": ("soc", "security operations center"),
    "threat-intelligence": ("threat intelligence", "脅威インテリジェンス", "脅威情報"),
    "vulnerability-management": ("vulnerability management", "脆弱性管理"),
    "ciso": ("ciso", "chief information security officer"),
    "audit": ("audit", "監査", "内部監査"),
    "forensics": ("forensics", "フォレンジック", "フォレンジクス"),
    "cryptography": ("cryptography", "暗号"),
    "zero-trust": ("zero trust", "ゼロトラスト"),
    "sast-dast": ("sast", "dast", "静的解析", "動的解析"),
    "waf": ("waf", "web application firewall"),
    "edr-xdr": ("edr", "xdr"),
    "pki": ("pki", "公開鍵基盤"),
    "malware": ("malware", "マルウェア"),
}

NEGATIVE_TERMS = (
    "security guard",
    "security officer",
    "警備員",
    "警備",
    "防犯",
    "security camera",
    "防犯カメラ",
    "food security",
    "social security",
    "身辺警護",
    "交通誘導",
)

# Title-first, ordered: management wins over engineering for "Security Manager".
ROLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "management",
        (
            "ciso",
            "chief information security officer",
            "security manager",
            "head of security",
            "director of security",
            "security director",
            "vp security",
            "manager",
            "セキュリティマネージャー",
            "セキュリティ部長",
            "責任者",
            "部長",
            "マネージャー",
        ),
    ),
    (
        "sales",
        (
            "sales engineer",
            "sales representative",
            "sales manager",
            "account executive",
            "account manager",
            "pre-sales",
            "presales",
            "セールスエンジニア",
            "営業",
        ),
    ),
    (
        "consulting",
        ("consultant", "consulting", "advisory", "コンサルタント", "コンサルティング", "コンサル"),
    ),
    (
        "grc",
        (
            "grc",
            "governance",
            "compliance",
            "isms",
            "iso 27001",
            "iso27001",
            "auditor",
            "audit",
            "risk analyst",
            "risk manager",
            "risk management",
            "監査",
            "内部統制",
            "コンプライアンス",
            "リスク管理",
        ),
    ),
    (
        "operations",
        (
            "soc",
            "csirt",
            "incident response",
            "incident handler",
            "threat intelligence",
            "threat hunter",
            "security operations",
            "blue team",
            "red team",
            "siem",
            "security analyst",
            "cybersecurity analyst",
            "information security analyst",
            "security administrator",
            "incident responder",
            "malware analyst",
            "forensics",
            "forensic",
            "監視",
            "インシデント対応",
            "脅威インテリジェンス",
            "セキュリティ運用",
            "セキュリティアナリスト",
            "セキュリティ管理者",
        ),
    ),
    (
        "engineering",
        (
            "security engineer",
            "cybersecurity engineer",
            "appsec",
            "application security",
            "product security",
            "cloud security",
            "devsecops",
            "security architect",
            "iam engineer",
            "penetration tester",
            "penetration testing",
            "pentest",
            "vulnerability",
            "security specialist",
            "it security",
            "セキュリティエンジニア",
            "脆弱性診断",
            "セキュリティ設計",
            "セキュリティスペシャリスト",
            "情報セキュリティ",
        ),
    ),
)

# Conservative description fallback: only technical families.
DESCRIPTION_ROLE_FALLBACK: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
    (category, keywords)
    for category, keywords in ROLE_KEYWORDS
    if category in ("engineering", "operations", "grc")
)


def _contains(text: str, keyword: str) -> bool:
    """Word-boundary match for ASCII keywords; substring match for Japanese."""
    if not keyword:
        return False
    if keyword.isascii():
        pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return keyword in text


def _match_tags(text: str) -> set[str]:
    return {
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(_contains(text, keyword) for keyword in keywords)
    }


def _title_role(title: str) -> str | None:
    for category, keywords in ROLE_KEYWORDS:
        if any(_contains(title, keyword) for keyword in keywords):
            return category
    return None


def _description_role(description: str) -> str | None:
    for category, keywords in DESCRIPTION_ROLE_FALLBACK:
        if any(_contains(description, keyword) for keyword in keywords):
            return category
    return None


@dataclass(slots=True)
class Classification:
    score: float
    tags: list[str] = field(default_factory=list)
    role_category: str = "other"
    language: str = "unknown"
    reason: str = ""


def classify(
    title: str | None,
    description: str | None = None,
    source_tags: list[str] | tuple[str, ...] | None = None,
    source_is_security_category: bool = False,
) -> Classification:
    """Score a listing and derive tags, role family, and language.

    The score is a heuristic for ranking and filtering, not a hard gate: the
    caller stores every listing and lets the UI filter.
    """
    title_text = normalize_whitespace(normalize_width(title or "")).lower()
    description_text = normalize_whitespace(normalize_width(description or "")).lower()
    combined = f"{title_text} {description_text}".strip()

    language = detect_language(title, description)

    title_tags = _match_tags(title_text)
    all_tags = _match_tags(combined)
    if language in ("ja", "bilingual"):
        all_tags.add("japanese")

    score = 0.0
    reasons: list[str] = []

    if source_is_security_category:
        score += 40
        reasons.append("security category")

    if any(_contains(title_text, term) for term in CORE_SECURITY_TERMS):
        score += 30
        reasons.append("security title")

    if title_tags:
        score += 20
        reasons.append("domain title")

    if len(all_tags) >= 3:
        score += 15
        reasons.append("domain description")

    if source_tags:
        score += 10
        reasons.append("source tags")

    if any(_contains(title_text, term) for term in NEGATIVE_TERMS):
        score -= 40
        reasons.append("negative title")

    score = max(0.0, min(100.0, score))

    role_category = (
        _title_role(title_text) or _description_role(description_text) or "other"
    )

    return Classification(
        score=score,
        tags=sorted(all_tags),
        role_category=role_category,
        language=language,
        reason=", ".join(reasons),
    )
