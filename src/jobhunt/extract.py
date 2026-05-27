"""Pure extractors that derive structured fields from a free-text job description.

Everything here is regex/keyword based. No external calls, no LLMs. Cheap and predictable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Keep this list focused — false positives are worse than false negatives for filtering.
# Multi-word phrases must come before single tokens that overlap them.
SKILLS: tuple[tuple[str, str], ...] = (
    # phrase, canonical tag
    ("machine learning", "ml"),
    ("deep learning", "ml"),
    ("computer vision", "cv"),
    ("natural language processing", "nlp"),
    ("large language models", "llm"),
    ("data engineering", "data-eng"),
    ("react native", "react-native"),
    ("next.js", "nextjs"),
    ("node.js", "nodejs"),
    ("ruby on rails", "rails"),
    ("amazon web services", "aws"),
    ("google cloud", "gcp"),
    ("ci/cd", "ci-cd"),
    ("infrastructure as code", "iac"),
)

# Single-token skills (matched as word boundaries).
SKILL_TOKENS: tuple[str, ...] = (
    "react", "vue", "svelte", "angular", "redux",
    "django", "flask", "fastapi", "spring", "rails", "laravel", "express",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "sqlite", "snowflake", "bigquery",
    "kafka", "rabbitmq", "elasticsearch",
    "docker", "kubernetes", "terraform", "ansible",
    "aws", "gcp", "azure",
    "graphql", "rest", "grpc",
    "linux", "git",
)

# Languages are tracked separately so the filter can target them specifically.
LANGUAGE_TOKENS: tuple[str, ...] = (
    "python", "javascript", "typescript", "java", "kotlin", "swift",
    "go", "golang", "rust", "c++", "c#", "ruby", "php", "scala",
    "r", "matlab", "haskell", "elixir", "erlang", "perl", "lua", "dart",
    "solidity", "sql", "bash", "shell",
)

_LEVEL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(
        r"\bintern(?:ship)?\b|\bpraktik(?:um|ant)\b|\bwerkstudent(?:in)?\b"
        r"|\bco-?op\b|\bplacement\s+(?:year|student)\b"
        r"|\bausbildung\b|\bazubi\b",
        re.I,
    ), "intern"),
    (re.compile(
        r"\bnew[- ]?grad(?:uate)?\b|\bgraduate\b|\bentry[- ]?level\b"
        r"|\bberufseinstieg\b|\bberufseinsteiger\b"
        r"|\bassociate\s+(?:software|developer|engineer)\b"
        r"|\btrainee\b|\bapprentice(?:ship)?\b"
        r"|\b(?:0|zero)\s*(?:[-–—~]|to)\s*(?:1|one)\s*years?\b"
        r"|\bno\s+experience\s+(?:required|needed|necessary)\b",
        re.I,
    ), "entry"),
    (re.compile(r"\bjunior\b|\bjr\.?\b", re.I), "junior"),
    (re.compile(r"\bstaff\b", re.I), "staff"),
    (re.compile(r"\bprincipal\b", re.I), "principal"),
    (re.compile(r"\bdistinguished\b|\bfellow\b", re.I), "principal"),
    (re.compile(r"\bsenior\b|\bsr\.?\b", re.I), "senior"),
    (re.compile(r"\blead\b", re.I), "lead"),
    (re.compile(r"\bmid[- ]?level\b", re.I), "mid"),
)

_REMOTE_STRONG = re.compile(
    r"\bfully[- ]remote\b|\b100%\s*remote\b|\bremote[- ]first\b"
    r"|\bwork[- ]?from[- ]?home\b|\bwfh\b|\bremote[- ]friendly\b"
    r"|\bremote[- ]eligible\b|\bremote[- ]ok\b",
    re.I,
)
_REMOTE_WEAK = re.compile(r"\bremote\b", re.I)
_HYBRID_RE = re.compile(r"\bhybrid\b", re.I)
_ONSITE_RE = re.compile(r"\bon[- ]?site\b|\bin[- ]office\b|\bin person\b", re.I)

_DEGREE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bph\.?d\b|\bdoctorate\b", re.I), "phd"),
    (re.compile(r"\bmaster'?s?\b|\bm\.?sc\b|\bm\.?s\b\.?", re.I), "masters"),
    (re.compile(r"\bbachelor'?s?\b|\bb\.?sc\b|\bb\.?s\b\.?", re.I), "bachelors"),
    (re.compile(r"\bno degree required\b|\bdegree not required\b", re.I), "none"),
)

_YOE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(\d+)\s*\+?\s*(?:to|-)\s*\d+\s*years?", re.I),  # "3-5 years" → 3
    re.compile(r"(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:experience|exp)", re.I),
    re.compile(r"minimum\s+of\s+(\d+)\s*years?", re.I),
    re.compile(r"at least\s+(\d+)\s*years?", re.I),
)

# Employment type patterns — searched in description text.
_ETYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(
        r"\bfull[- ]?time\b|\bpermanent\s+(?:position|role|employment)\b"
        r"|\bpermanent\b|\bfull[- ]?zeit\b|\bvollzeit\b",
        re.I,
    ), "Full-time"),
    (re.compile(r"\bpart[- ]?time\b|\bteilzeit\b", re.I), "Part-time"),
    (re.compile(
        r"\bcontract(?:or)?\s+(?:position|role)\b|\bcontract\b"
        r"|\bfreelance\b|\btemporary\b|\bfixed[- ]?term\b",
        re.I,
    ), "Contract"),
    (re.compile(
        r"\binternship\b|\bintern\s+(?:position|role)\b"
        r"|\bpraktikum\b|\bwerkstudent\b",
        re.I,
    ), "Internship"),
)

# Salary patterns — match "$120,000 - $180,000", "$120k-180k", "€50.000-70.000",
# "£45,000 to £55,000", "USD 100,000 – 150,000".
_CURRENCY_SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY", "₹": "INR"}
_SALARY_RE = re.compile(
    r"(?:(?P<cur1>[€£$¥₹])\s*)"                     # currency symbol before number
    r"(?P<min>\d[\d,._]*[kK]?)"                       # min salary
    r"\s*(?:[-–—~]|to)\s*"                            # separator
    r"(?:[€£$¥₹]\s*)?"                               # optional second currency symbol
    r"(?P<max>\d[\d,._]*[kK]?)"                       # max salary
    r"(?:\s*(?P<cur2>[A-Z]{3}))?"                     # optional trailing currency code
)
_SALARY_CONTEXT_RE = re.compile(
    r"(?:salary|compensation|pay|annual|base|range|offer)\b",
    re.I,
)

# Location-based remote inference.
_LOCATION_REMOTE_RE = re.compile(
    r"\bremote\b|\banywhere\b|\bdistributed\b|\bwork from home\b|\bwfh\b"
    r"|\bworldwide\b|\bglobal\b",
    re.I,
)


def _parse_salary_number(raw: str) -> int | None:
    """Parse '120,000', '120k', '120.000' (EU) into an integer."""
    s = raw.strip().replace(",", "").replace(".", "").replace("_", "")
    if s.lower().endswith("k"):
        try:
            return int(float(s[:-1]) * 1000)
        except ValueError:
            return None
    try:
        val = int(s)
        if val < 1000:
            val *= 1000
        return val
    except ValueError:
        return None


@dataclass(slots=True, frozen=True)
class Extracted:
    skills: list[str]
    languages: list[str]
    level: str
    remote: str
    degree: str
    min_years: int | None
    employment_type: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str


def _find_matches(text: str, tokens: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    lower = text.lower()
    for tok in tokens:
        # Use word boundaries except for tokens containing chars regex treats specially.
        pattern = re.escape(tok)
        if re.search(rf"(?<![\w]){pattern}(?![\w])", lower):
            out.append(tok)
    return out


def extract(text: str, *, title: str = "") -> Extracted:
    haystack = f"{title}\n{text}"

    languages = _find_matches(haystack, LANGUAGE_TOKENS)
    # Normalize golang → go.
    if "golang" in languages and "go" not in languages:
        languages.append("go")
    languages = sorted({l for l in languages if l != "golang"})

    skills: set[str] = set()
    lower = haystack.lower()
    for phrase, tag in SKILLS:
        if phrase in lower:
            skills.add(tag)
    for tok in _find_matches(haystack, SKILL_TOKENS):
        skills.add(tok)
    # postgres/postgresql collapse
    if "postgresql" in skills:
        skills.discard("postgresql")
        skills.add("postgres")

    level = "unknown"
    for pat, lvl in _LEVEL_PATTERNS:
        if pat.search(haystack):
            level = lvl
            break

    # Remote detection: strong patterns match anywhere, weak "remote" only in
    # title + first 300 chars to avoid false positives from "remote debugging" etc.
    remote = "unknown"
    if _REMOTE_STRONG.search(haystack):
        remote = "remote"
    elif _HYBRID_RE.search(haystack):
        remote = "hybrid"
    elif _ONSITE_RE.search(haystack):
        remote = "onsite"
    elif _REMOTE_WEAK.search(f"{title}\n{text[:300]}"):
        remote = "remote"

    degree = "unknown"
    for pat, deg in _DEGREE_PATTERNS:
        if pat.search(haystack):
            degree = deg
            break

    min_years: int | None = None
    for pat in _YOE_PATTERNS:
        m = pat.search(haystack)
        if m:
            try:
                min_years = int(m.group(1))
                break
            except (ValueError, IndexError):
                continue

    # Employment type from description text.
    employment_type = "unknown"
    for pat, etype in _ETYPE_PATTERNS:
        if pat.search(haystack):
            employment_type = etype
            break

    # Salary from description text — only near compensation-related context.
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency = ""
    for m in _SALARY_RE.finditer(haystack):
        start = max(0, m.start() - 120)
        context = haystack[start:m.start()]
        if _SALARY_CONTEXT_RE.search(context) or m.start() < 500:
            raw_min = _parse_salary_number(m.group("min"))
            raw_max = _parse_salary_number(m.group("max"))
            if raw_min and raw_max and 15000 <= raw_max <= 1_000_000:
                salary_min = raw_min
                salary_max = raw_max
                sym = m.group("cur1") or ""
                salary_currency = (
                    _CURRENCY_SYMBOLS.get(sym, "")
                    or m.group("cur2")
                    or "USD"
                )
                break

    # Improve remote detection using location field when description is silent.
    if remote == "unknown" and title:
        if _LOCATION_REMOTE_RE.search(title):
            remote = "remote"

    return Extracted(
        skills=sorted(skills),
        languages=languages,
        level=level,
        remote=remote,
        degree=degree,
        min_years=min_years,
        employment_type=employment_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
    )
