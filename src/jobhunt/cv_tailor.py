"""CV tailoring + ATS-readiness linting (P9 + P10).

Deterministic keyword/regex only — no LLM, no external calls (project rule).
"Tailoring" here is keyword-gap analysis against a target job's demand plus
an ATS-parse-readiness lint, rendered as a fill-in guidance sheet the user
completes with their real experience. It never fabricates achievements —
honesty is non-negotiable for a job application — and keyword alignment is
exactly what ATS keyword-matching rewards.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .extract import LANGUAGE_TOKENS, SKILL_TOKENS

_TITLE_KEYWORDS = tuple(SKILL_TOKENS) + tuple(LANGUAGE_TOKENS) + (
    "django", "flask", "fastapi", "spring", "rails", "laravel", "node",
    "backend", "frontend", "fullstack", "devops", "data", "ml", "ai",
    "mobile", "android", "ios", "qa", "security", "cloud",
)

# Generic, universally-applicable job-skill terms — so tailoring works for
# non-tech + Egypt/blue-collar roles too, not just software. Multi-word
# phrases are matched as substrings; single words as word-boundary tokens.
_GENERAL_KEYWORDS: tuple[str, ...] = (
    # soft / cross-role
    "communication", "teamwork", "leadership", "negotiation", "presentation",
    "customer service", "problem solving", "time management", "organization",
    "attention to detail", "multitasking",
    # office / admin
    "excel", "microsoft office", "powerpoint", "word", "outlook", "sap",
    "data entry", "bookkeeping", "accounting", "invoicing", "reporting",
    "scheduling", "administration", "reception",
    # sales / marketing
    "sales", "marketing", "crm", "salesforce", "seo", "social media",
    "cold calling", "lead generation", "account management", "retail",
    # trades / local / logistics (the /local + Egypt persona)
    "driving", "driving license", "forklift", "warehouse", "inventory",
    "logistics", "delivery", "cleaning", "cooking", "hospitality", "catering",
    "security", "maintenance", "packaging", "shift work",
    # care / education / health
    "nursing", "caregiving", "childcare", "teaching", "tutoring", "first aid",
    # languages (natural, not programming)
    "english", "arabic", "french", "german", "fluent",
    # finance / analysis
    "analysis", "budgeting", "forecasting", "compliance", "procurement",
)

_STOPWORDS = frozenset({
    "the", "and", "for", "with", "you", "our", "will", "are", "have", "this",
    "that", "your", "job", "work", "team", "role", "must", "should", "able",
    "who", "all", "any", "from", "was", "were", "has", "had", "can", "may",
    "we", "us", "a", "an", "to", "of", "in", "on", "at", "is", "as", "be",
    "or", "by", "it", "if", "not", "but", "they", "their", "them", "his",
    "her", "she", "he", "candidate", "candidates", "experience", "years",
    "company", "position", "responsibilities", "requirements", "including",
})

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
_SECTION_RE = re.compile(
    r"\b(experience|employment|work history|education|skills|"
    r"projects|qualifications|summary|profile)\b",
    re.I,
)


def jd_keywords(job: Any) -> list[str]:
    """The target job's demand signal: extracted skills + languages + notable
    title tokens + generic role terms (so non-tech + Egypt/blue-collar jobs
    get real keyword guidance, not just software roles). Deduped, lowercased,
    stable-sorted."""
    kw: set[str] = set()
    for s in (job.skills or []):
        if s:
            kw.add(str(s).lower())
    for lang in (job.languages or []):
        if lang:
            kw.add(str(lang).lower())
    title = (job.title or "").lower()
    for tok in _TITLE_KEYWORDS:
        if re.search(rf"\b{re.escape(tok)}\b", title):
            kw.add(tok)
    # Generic terms present in the title OR description.
    haystack = f"{title}\n{(job.description or '').lower()}"
    for term in _GENERAL_KEYWORDS:
        if " " in term:
            if term in haystack:
                kw.add(term)
        elif re.search(rf"\b{re.escape(term)}\b", haystack):
            kw.add(term)
    return sorted(kw)


def ats_lint(cv_text: str) -> list[dict]:
    """Deterministic ATS-parse-readiness checks. Each finding:
    {level: ok|warn|bad, code, message}."""
    text = cv_text or ""
    findings: list[dict] = []

    def add(level: str, code: str, message: str) -> None:
        findings.append({"level": level, "code": code, "message": message})

    # Contact info — ATS builds the candidate record from these.
    if _EMAIL_RE.search(text):
        add("ok", "contact_email", "Email address found.")
    else:
        add("bad", "contact_email",
            "No email address detected — ATS may fail to create your record.")
    if _PHONE_RE.search(text):
        add("ok", "contact_phone", "Phone number found.")
    else:
        add("warn", "contact_phone", "No phone number detected.")

    # Section headers — ATS segments the resume by them.
    sections = {m.group(1).lower() for m in _SECTION_RE.finditer(text)}
    has_exp = bool(sections & {"experience", "employment", "work history"})
    has_edu = "education" in sections
    has_skills = "skills" in sections
    present = sum((has_exp, has_edu, has_skills))
    if present == 3:
        add("ok", "sections", "Experience, Education, and Skills sections all present.")
    elif present >= 1:
        add("warn", "sections",
            "Some standard sections missing — include clear Experience, "
            "Education, and Skills headings.")
    else:
        add("bad", "sections",
            "No standard section headings found — ATS relies on Experience / "
            "Education / Skills headers to parse your resume.")

    # Layout: heavy tab/pipe runs signal multi-column tables that ATS mangle.
    multicol = len(re.findall(r"\t{2,}|(?:\s\|\s.*){2,}", text))
    if multicol >= 4:
        add("warn", "layout",
            "Multi-column / table layout detected (tabs or pipes) — many ATS "
            "read columns out of order. Prefer a single-column layout.")
    else:
        add("ok", "layout", "No obvious multi-column table layout.")

    # Encoding: the replacement char means text was already garbled.
    if "�" in text:
        add("warn", "encoding",
            "Garbled characters (�) detected — re-export the CV so text "
            "is clean UTF-8.")

    # Length sanity.
    words = len(text.split())
    if words < 120:
        add("warn", "length",
            f"Only {words} words — most parseable resumes are 300–800 words.")
    elif words > 1200:
        add("warn", "length",
            f"{words} words — very long; ATS + recruiters skim. Consider trimming.")
    else:
        add("ok", "length", f"{words} words — a reasonable length.")

    return findings


@dataclass
class TailorReport:
    job_id: int
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    coverage_pct: int = 0
    suggested_skills_line: str = ""
    ats: list[dict] = field(default_factory=list)


def tailor(
    job: Any,
    cv_skills: list[str],
    cv_languages: list[str],
    cv_text: str,
) -> TailorReport:
    """Keyword-gap analysis of a CV against a target job."""
    demand = jd_keywords(job)
    have = {s.lower() for s in (cv_skills or []) if s}
    have |= {s.lower() for s in (cv_languages or []) if s}
    # Also credit keywords that literally appear in the CV prose.
    cv_low = (cv_text or "").lower()

    def in_cv(kw: str) -> bool:
        return kw in have or re.search(rf"\b{re.escape(kw)}\b", cv_low) is not None

    matched = [k for k in demand if in_cv(k)]
    missing = [k for k in demand if not in_cv(k)]
    coverage = round(100 * len(matched) / len(demand)) if demand else 0

    # Suggested skills line: JD-matched skills first (ATS keyword priority),
    # then the CV's other skills, then missing ones flagged to add-if-true.
    other = [s for s in sorted(have) if s not in matched]
    parts = list(matched) + other
    line = ", ".join(parts)
    if missing:
        line += "  —  add if you have it: " + ", ".join(missing)

    return TailorReport(
        job_id=getattr(job, "id", 0),
        matched=matched,
        missing=missing,
        coverage_pct=coverage,
        suggested_skills_line=line,
        ats=ats_lint(cv_text),
    )


def render_markdown(report: TailorReport, job: Any, applicant_name: str = "") -> str:
    """A downloadable tailoring sheet. Guides a real edit — the summary
    scaffold uses blanks, never invented achievements."""
    name = applicant_name or "Your Name"
    lines = [
        f"# Tailoring sheet — {job.title} @ {getattr(job, 'company', '')}",
        "",
        f"**Keyword coverage:** {report.coverage_pct}% "
        f"({len(report.matched)} of {len(report.matched) + len(report.missing)} "
        "target keywords already in your CV)",
        "",
        "## Keywords this job asks for",
        "",
        f"- **Already in your CV:** {', '.join(report.matched) or '(none)'}",
        f"- **Missing — add if you genuinely have them:** "
        f"{', '.join(report.missing) or '(none)'}",
        "",
        "## Suggested Skills line (ATS reads keywords — lead with the matches)",
        "",
        f"> {report.suggested_skills_line or '(add your skills)'}",
        "",
        "## Professional summary scaffold (fill the blanks with real results)",
        "",
        f"> {name} — {job.title} with ___ years building "
        f"{', '.join(report.matched[:3]) or '[your core stack]'}. "
        "Delivered ___ [quantified achievement], improving ___ by ___%. "
        "Seeking to ___ at " + getattr(job, "company", "the company") + ".",
        "",
        "## ATS readiness",
        "",
    ]
    for f in report.ats:
        mark = {"ok": "✓", "warn": "!", "bad": "✗"}.get(f["level"], "-")
        lines.append(f"- {mark} {f['message']}")
    lines += [
        "",
        "_Generated by jobhunt — keyword alignment only. Never add a skill or "
        "achievement you can't back up in an interview._",
    ]
    return "\n".join(lines)
