"""CV ingestion and semantic matching.

Parses an uploaded CV (PDF/DOCX/TXT), runs it through the same keyword extractor
used for job descriptions, computes a sentence-transformer embedding when
``sentence-transformers`` is installed, and stores the result as a single-row
profile.

If ``sentence-transformers`` is *not* installed the upload still works — we
fall back to a fast keyword-overlap score driven by the same skills /
languages list ``extract.py`` already uses. The user gets a usable CV match
without a 500 MB ML download. Installing ``jobhunt-app[match]`` later upgrades
the score to semantic cosine similarity transparently.
"""

from __future__ import annotations

import io
import math
import os
from typing import Any

from sqlalchemy import select, update

from .db import db_session
from .extract import extract
from .models import CVProfile, Job

# Lazy module-level cache for the sentence-transformer model.
_EMBED_MODEL: Any | None = None
_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
_KEYWORD_MODEL_NAME = "keyword-overlap-v1"


def has_semantic_model() -> bool:
    """True when sentence-transformers can be imported."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_cv(filename: str, content: bytes) -> str:
    """Extract plain text from a CV file by extension.

    Supports .pdf (pypdf), .docx (python-docx), and .txt (utf-8). Raises
    ValueError on unsupported types, empty files, or upstream parser
    failure (so the route converts these to a 400 with a clear message
    instead of bubbling a 500).
    """
    if not content:
        raise ValueError("CV file is empty.")
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            parts: list[str] = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    # A single bad page shouldn't kill the whole upload.
                    continue
            text = "\n".join(parts).strip()
        except Exception as exc:  # noqa: BLE001
            # pypdf raises EmptyFileError, PdfReadError, etc. — all map to
            # "we can't read this file", not "the server is broken".
            raise ValueError(
                f"Couldn't read PDF: {type(exc).__name__}. "
                "Is it a real PDF (not just renamed)?"
            ) from exc
        if not text:
            raise ValueError(
                "PDF contained no extractable text. "
                "Image-only PDFs (e.g. scanned CVs) need OCR — try exporting as DOCX or TXT."
            )
        return text

    if ext == ".docx":
        try:
            import docx  # python-docx

            document = docx.Document(io.BytesIO(content))
            parts = [p.text for p in document.paragraphs if p.text]
            # Tables often hold skills lists in modern CVs.
            for table in document.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text:
                            parts.append(cell.text)
            text = "\n".join(parts).strip()
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"Couldn't read DOCX: {type(exc).__name__}. "
                "Is it a real .docx (not .doc, not renamed)?"
            ) from exc
        if not text:
            raise ValueError("DOCX contained no extractable text.")
        return text

    if ext == ".txt":
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            raise ValueError("TXT file contained no text.")
        return text

    raise ValueError(f"Unsupported CV file type: {ext!r}. Use .pdf, .docx, or .txt.")


# ---------------------------------------------------------------------------
# Embedding (semantic — optional)
# ---------------------------------------------------------------------------


def _load_model() -> Any:
    global _EMBED_MODEL
    if _EMBED_MODEL is not None:
        return _EMBED_MODEL
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    _EMBED_MODEL = SentenceTransformer(_EMBED_MODEL_NAME)
    return _EMBED_MODEL


def embed_text(text: str) -> tuple[list[float], str]:
    """Encode ``text`` with the sentence-transformer model. Caller must ensure
    ``has_semantic_model()`` is True first."""
    model = _load_model()
    snippet = (text or "")[:5000]
    vec = model.encode(snippet, convert_to_numpy=False, show_progress_bar=False)
    try:
        values = vec.tolist()  # torch.Tensor / numpy.ndarray
    except AttributeError:
        values = list(vec)
    return [float(x) for x in values], _EMBED_MODEL_NAME


def cosine(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity. Returns 0.0 on empty / zero-norm inputs."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


# ---------------------------------------------------------------------------
# Keyword fallback (always available)
# ---------------------------------------------------------------------------


def keyword_score(cv_skills: list[str], cv_languages: list[str],
                  job_skills: list[str], job_languages: list[str]) -> float:
    """Jaccard-ish overlap of CV vs job skills+languages, in [0, 1].

    Weighted so language matches count slightly more than tool/skill matches —
    a Python role for a Python CV should rank above a generic "has React"
    overlap. Returns 0.0 if the CV has nothing detectable, which mirrors the
    embedding path (no signal → 0 score).
    """
    cv_skill_set = {s.lower() for s in cv_skills if s}
    cv_lang_set = {s.lower() for s in cv_languages if s}
    job_skill_set = {s.lower() for s in job_skills if s}
    job_lang_set = {s.lower() for s in job_languages if s}

    if not cv_skill_set and not cv_lang_set:
        return 0.0
    if not job_skill_set and not job_lang_set:
        return 0.0

    lang_overlap = len(cv_lang_set & job_lang_set)
    skill_overlap = len(cv_skill_set & job_skill_set)
    job_demand = max(1, len(job_lang_set) * 2 + len(job_skill_set))
    raw = (lang_overlap * 2 + skill_overlap) / job_demand
    # Map [0, 1+] into a slightly compressed [0, 1] so single-skill matches
    # don't immediately score 1.0.
    return min(1.0, raw * 0.85)


# ---------------------------------------------------------------------------
# Upload / orchestration
# ---------------------------------------------------------------------------


def upload_cv(filename: str, content: bytes) -> dict:
    """Parse a CV, extract structured fields, optionally embed, and upsert id=1.

    Never raises on a missing optional ML dependency — falls back to keyword
    scoring so the user never sees a "please install sentence-transformers"
    error in the browser.
    """
    text = parse_cv(filename, content)
    extracted = extract(text)

    embedding: list[float] = []
    model_name = _KEYWORD_MODEL_NAME
    if has_semantic_model():
        try:
            embedding, model_name = embed_text(text)
        except Exception:
            # Fall back to keyword mode if the model fails to load (offline,
            # disk full, corrupted download …). The upload still succeeds.
            embedding = []
            model_name = _KEYWORD_MODEL_NAME

    with db_session() as s:
        existing = s.get(CVProfile, 1)
        if existing is not None:
            s.delete(existing)
            s.flush()
        profile = CVProfile(
            id=1,
            filename=filename,
            text=text,
            embedding=embedding,
            model=model_name,
            detected_skills=list(extracted.skills),
            detected_languages=list(extracted.languages),
        )
        s.add(profile)

    return {
        "filename": filename,
        "skills": list(extracted.skills),
        "languages": list(extracted.languages),
        "text_chars": len(text),
        "embedding_dim": len(embedding),
        "mode": "semantic" if embedding else "keyword",
    }


# ---------------------------------------------------------------------------
# Job matching
# ---------------------------------------------------------------------------


def match_all_jobs() -> int:
    """Recompute cv_match for every job in the DB. Returns the count updated.

    Uses semantic embeddings when the CV was uploaded with sentence-transformers
    installed; otherwise falls back to keyword overlap. Either way, every job
    gets a score in [0, 1].
    """
    with db_session() as s:
        profile = s.get(CVProfile, 1)
        if profile is None:
            return 0
        cv_vec = list(profile.embedding or [])
        cv_skills = list(profile.detected_skills or [])
        cv_languages = list(profile.detected_languages or [])

    use_semantic = bool(cv_vec) and has_semantic_model()

    with db_session() as s:
        if use_semantic:
            rows = s.execute(select(Job.id, Job.title, Job.description)).all()
        else:
            rows = s.execute(select(Job.id, Job.skills, Job.languages)).all()

    updated = 0
    batch: list[tuple[int, float]] = []
    for row in rows:
        if use_semantic:
            job_id, title, description = row
            body = f"{title or ''}\n{(description or '')[:3000]}"
            try:
                job_vec, _ = embed_text(body)
            except Exception:
                # Single-job embedding failure shouldn't kill the whole pass.
                continue
            score = cosine(cv_vec, job_vec)
        else:
            job_id, skills, languages = row
            score = keyword_score(
                cv_skills, cv_languages,
                list(skills or []), list(languages or []),
            )
        batch.append((job_id, score))
        if len(batch) >= 100:
            _flush_match_batch(batch)
            updated += len(batch)
            batch = []
    if batch:
        _flush_match_batch(batch)
        updated += len(batch)
    return updated


def _flush_match_batch(batch: list[tuple[int, float]]) -> None:
    with db_session() as s:
        for job_id, score in batch:
            s.execute(update(Job).where(Job.id == job_id).values(cv_match=score))


# ---------------------------------------------------------------------------
# Clear / status
# ---------------------------------------------------------------------------


def clear_cv() -> None:
    """Wipe the stored CV and null out cv_match on every job."""
    with db_session() as s:
        existing = s.get(CVProfile, 1)
        if existing is not None:
            s.delete(existing)
        s.execute(update(Job).values(cv_match=None))


def cv_status() -> dict:
    """Snapshot of the loaded CV plus how many jobs currently carry a match score."""
    with db_session() as s:
        profile = s.get(CVProfile, 1)
        matched = s.execute(
            select(Job.id).where(Job.cv_match.is_not(None))
        ).all()
        matched_count = len(matched)

        semantic_available = has_semantic_model()

        if profile is None:
            return {
                "loaded": False,
                "filename": "",
                "uploaded_at": None,
                "model": "",
                "skills": [],
                "languages": [],
                "matched_jobs": matched_count,
                "mode": "semantic" if semantic_available else "keyword",
                "semantic_available": semantic_available,
            }

        uploaded_at_iso = (
            profile.uploaded_at.isoformat() if profile.uploaded_at is not None else None
        )
        cv_mode = "semantic" if profile.embedding else "keyword"
        return {
            "loaded": True,
            "filename": profile.filename,
            "uploaded_at": uploaded_at_iso,
            "model": profile.model,
            "skills": list(profile.detected_skills or []),
            "languages": list(profile.detected_languages or []),
            "matched_jobs": matched_count,
            "mode": cv_mode,
            "semantic_available": semantic_available,
        }
