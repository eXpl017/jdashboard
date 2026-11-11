import hashlib
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

JAPANESE_RANGES = (
    (0x3005, 0x3005),  # 々
    (0x3040, 0x30FF),  # hiragana + katakana
    (0x3400, 0x4DBF),  # CJK extension A
    (0x4E00, 0x9FFF),  # CJK unified ideographs
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
)

JAPAN_MARKERS = (
    "japan",
    "日本",
    "tokyo",
    "東京",
    "osaka",
    "大阪",
    "yokohama",
    "横浜",
    "nagoya",
    "名古屋",
    "fukuoka",
    "福岡",
    "kyoto",
    "京都",
    "全国",
    "在宅",
    "リモート",
)

INTERNATIONAL_MARKERS = (
    "worldwide",
    "anywhere in the world",
    "work from anywhere",
    "remote anywhere",
    "global remote",
    "globally remote",
    "remote worldwide",
    "世界中",
    "どこからでも",
    "海外から",
)

_AMOUNT = re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*(million|万|千|M|m|K|k)?")
_SUFFIX_MULTIPLIERS = {
    "million": 1_000_000,
    "万": 10_000,
    "千": 1_000,
    "m": 1_000_000,
    "k": 1_000,
}


@dataclass(slots=True)
class SalaryParts:
    min: int | None = None
    max: int | None = None
    currency: str = "JPY"
    period: str = "unknown"  # annual | monthly | hourly | unknown


def strip_html(html: str | None) -> str:
    """Return readable text from an HTML fragment."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    return normalize_whitespace(soup.get_text(" ", strip=True))


def normalize_whitespace(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_width(text: str | None) -> str:
    """Convert full-width characters to half-width equivalents for matching."""
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text)


def _to_amount(raw: str, suffix: str | None) -> float:
    value = float(raw.replace(",", ""))
    if suffix:
        return value * _SUFFIX_MULTIPLIERS.get(suffix.lower(), 1)
    return value


def parse_salary(text: str | None) -> SalaryParts:
    """Parse common English and Japanese salary strings.

    Values are returned in the source currency without annualizing. ``period``
    records whether the source quoted an hourly, monthly, or annual figure.
    """
    if not text:
        return SalaryParts()

    lowered = text.lower()
    period = "unknown"
    if any(
        token in lowered
        for token in ("/hour", "/ hour", "per hour", "hourly", "時給", "/h ")
    ):
        period = "hourly"
    elif any(
        token in lowered
        for token in ("/month", "/ month", "per month", "monthly", "月給")
    ):
        period = "monthly"
    elif any(
        token in lowered
        for token in ("/year", "per year", "annual", "per annum", "年収", "年薪")
    ):
        period = "annual"

    currency = "JPY"
    if "$" in text or "usd" in lowered:
        currency = "USD"
    elif "€" in text or "eur" in lowered:
        currency = "EUR"

    amounts: list[int] = []
    for match in _AMOUNT.finditer(text):
        raw, suffix = match.group(1), match.group(2)
        value = _to_amount(raw, suffix)
        # A bare small number is usually years of experience, not pay.
        if suffix is None and value < 1000:
            continue
        amounts.append(int(value))

    if not amounts:
        return SalaryParts(currency=currency, period=period)
    if len(amounts) == 1:
        return SalaryParts(
            min=amounts[0], max=amounts[0], currency=currency, period=period
        )
    return SalaryParts(
        min=amounts[0], max=amounts[1], currency=currency, period=period
    )


def detect_remote(text: str | None) -> str:
    """Return ``remote``, ``hybrid``, ``onsite``, or ``unknown``."""
    if not text:
        return "unknown"
    lowered = normalize_width(text).lower()
    if any(
        token in lowered
        for token in (
            "no remote",
            "not remote",
            "remote not allowed",
            "リモート不可",
            "在宅不可",
        )
    ):
        return "onsite"
    if any(
        token in lowered
        for token in ("hybrid", "partially remote", "part remote", "一部在宅", "ハイブリッド")
    ):
        return "hybrid"
    if any(
        token in lowered
        for token in (
            "fully remote",
            "full remote",
            "remote",
            "telecommute",
            "work from home",
            "wfh",
            "在宅",
            "リモート",
            "テレワーク",
        )
    ):
        return "remote"
    if any(token in lowered for token in ("onsite", "on-site", "no remote", "出社", "常駐")):
        return "onsite"
    return "unknown"


def detect_employment_type(text: str | None) -> str:
    """Return ``full_time``, ``contract``, ``part_time``, ``internship``, or ``unknown``."""
    if not text:
        return "unknown"
    lowered = normalize_width(text).lower()
    if any(
        token in lowered
        for token in (
            "part time",
            "part-time",
            "part_time",
            "parttime",
            "パート",
            "アルバイト",
        )
    ):
        return "part_time"
    if any(token in lowered for token in ("intern", "インターン")):
        return "internship"
    if any(
        token in lowered
        for token in (
            "contract",
            "contractor",
            "fixed term",
            "fixed-term",
            "契約社員",
            "業務委託",
            "派遣",
        )
    ):
        return "contract"
    if any(
        token in lowered
        for token in (
            "full time",
            "full-time",
            "full_time",
            "fulltime",
            "permanent",
            "regular employee",
            "正社員",
            "正職員",
        )
    ):
        return "full_time"
    return "unknown"


def _is_japanese(char: str) -> bool:
    codepoint = ord(char)
    return any(start <= codepoint <= end for start, end in JAPANESE_RANGES)


def detect_language(title: str | None, description: str | None = None) -> str:
    """Classify listing text as ``en``, ``ja``, ``bilingual``, or ``unknown``."""
    text = f"{title or ''} {description or ''}".strip()
    if not text:
        return "unknown"

    japanese = sum(1 for char in text if _is_japanese(char))
    latin = sum(1 for char in text if char.isascii() and char.isalpha())

    if japanese == 0:
        return "en" if latin else "unknown"
    if latin == 0:
        return "ja"

    ratio = japanese / (japanese + latin)
    if ratio >= 0.6:
        return "ja"
    if ratio >= 0.15:
        return "bilingual"
    return "en"


def detect_location_scope(
    location: str | None,
    remote_type: str | None,
    description: str | None = None,
) -> str:
    """Derive the normalized location scope from location and remote signals."""
    text = normalize_width(f"{location or ''} {description or ''}").lower()
    in_japan = any(marker in text for marker in JAPAN_MARKERS)
    international = any(marker in text for marker in INTERNATIONAL_MARKERS)

    if remote_type == "remote":
        if international and not in_japan:
            return "international_remote"
        if in_japan:
            return "japan_remote"
        return "unknown"
    if remote_type == "hybrid":
        return "japan_hybrid" if in_japan else "unknown"
    if remote_type == "onsite":
        return "japan_onsite" if in_japan else "unknown"

    if international and not in_japan:
        return "international_remote"
    if in_japan:
        return "japan_onsite"
    return "unknown"


def detect_overseas_eligible(text: str | None) -> bool | None:
    """Detect explicit overseas-application language, never visa sponsorship alone."""
    if not text:
        return None
    lowered = normalize_width(text).lower()

    restrictions = (
        "must reside in japan",
        "must be based in japan",
        "japan residents only",
        "japanese residents only",
        "日本在住",
        "国内在住",
        "日本国内から",
    )
    if any(phrase in lowered for phrase in restrictions):
        return False

    overseas = (
        "apply from abroad",
        "applications from overseas",
        "overseas applicants",
        "overseas candidates",
        "international applicants",
        "applications from outside japan",
        "海外からの応募",
        "海外応募",
        "海外から応募",
    )
    if any(phrase in lowered for phrase in overseas):
        return True
    return None


def canonical_url(url: str, allowed_query_params: tuple[str, ...] = ()) -> str:
    """Strip fragments, tracking parameters, duplicate slashes, and casing noise."""
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path) or "/"
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    kept = sorted((key, value) for key, value in query_pairs if key in allowed_query_params)
    return urlunsplit((scheme, netloc, path, urlencode(kept), ""))


def fingerprint(source: str, url: str) -> str:
    """Stable per-source identity: one row per source listing."""
    canonical = canonical_url(url)
    return hashlib.sha256(f"{source}:{canonical}".encode()).hexdigest()
