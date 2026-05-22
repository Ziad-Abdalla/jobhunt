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
    (re.compile(r"\bintern(?:ship)?\b", re.I), "intern"),
    (re.compile(r"\bnew[- ]?grad\b|\bgraduate\b|\bentry[- ]?level\b", re.I), "entry"),
    (re.compile(r"\bjunior\b|\bjr\.?\b", re.I), "junior"),
    (re.compile(r"\bstaff\b", re.I), "staff"),
    (re.compile(r"\bprincipal\b", re.I), "principal"),
    (re.compile(r"\bdistinguished\b|\bfellow\b", re.I), "principal"),
    (re.compile(r"\bsenior\b|\bsr\.?\b", re.I), "senior"),
    (re.compile(r"\blead\b", re.I), "lead"),
    (re.compile(r"\bmid[- ]?level\b", re.I), "mid"),
)

_REMOTE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfully[- ]remote\b|\b100%\s*remote\b|\bremote[- ]first\b", re.I), "remote"),
    (re.compile(r"\bhybrid\b", re.I), "hybrid"),
    (re.compile(r"\bon[- ]?site\b|\bin[- ]office\b|\bin person\b", re.I), "onsite"),
    (re.compile(r"\bremote\b", re.I), "remote"),
)

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


@dataclass(slots=True, frozen=True)
class Extracted:
    skills: list[str]
    languages: list[str]
    level: str
    remote: str
    degree: str
    min_years: int | None


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

    remote = "unknown"
    for pat, mode in _REMOTE_PATTERNS:
        if pat.search(haystack):
            remote = mode
            break

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

    return Extracted(
        skills=sorted(skills),
        languages=languages,
        level=level,
        remote=remote,
        degree=degree,
        min_years=min_years,
    )
