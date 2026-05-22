"""CV ingestion and semantic matching.

Parses an uploaded CV (PDF/DOCX/TXT), runs it through the same keyword extractor
used for job descriptions, computes a sentence-transformer embedding, and stores
the result as a single-row profile. Each job in the DB then gets a cosine-similarity
score against that embedding.

`sentence-transformers` is an OPTIONAL dependency. Everything except `embed_text`,
`upload_cv`, and `match_all_jobs` works without it.
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
_INSTALL_HINT = (
    'CV matching requires sentence-transformers. '
    'Install with: uv pip install -e ".[match]"'
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_cv(filename: str, content: bytes) -> str:
    """Extract plain text from a CV file by extension.

    Supports .pdf (pypdf), .docx (python-docx), and .txt (utf-8). Raises
    ValueError for anything else.
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                # A single bad page shouldn't kill the whole upload.
                continue
        return "\n".join(parts).strip()

    if ext == ".docx":
        import docx  # python-docx

        document = docx.Document(io.BytesIO(content))
        parts = [p.text for p in document.paragraphs if p.text]
        # Tables often hold skills lists in modern CVs.
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        parts.append(cell.text)
        return "\n".join(parts).strip()

    if ext == ".txt":
        return content.decode("utf-8", errors="replace").strip()

    raise ValueError(f"Unsupported CV file type: {ext!r}. Use .pdf, .docx, or .txt.")


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


def _load_model() -> Any:
    global _EMBED_MODEL
    if _EMBED_MODEL is not None:
        return _EMBED_MODEL
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(_INSTALL_HINT) from exc
    _EMBED_MODEL = SentenceTransformer(_EMBED_MODEL_NAME)
    return _EMBED_MODEL


def embed_text(text: str) -> tuple[list[float], str]:
    """Encode `text` with the cached sentence-transformer model.

    Returns (embedding, model_name). Truncates input to ~5000 chars so we don't
    feed the tokenizer a whole novel.
    """
    model = _load_model()
    snippet = (text or "")[:5000]
    vec = model.encode(snippet, convert_to_numpy=False, show_progress_bar=False)
    # `vec` may be a torch.Tensor or list-like; normalize to plain floats.
    try:
        values = vec.tolist()  # torch.Tensor / numpy.ndarray
    except AttributeError:
        values = list(vec)
    return [float(x) for x in values], _EMBED_MODEL_NAME


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


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
# Upload / orchestration
# ---------------------------------------------------------------------------


def upload_cv(filename: str, content: bytes) -> dict:
    """Parse a CV file, extract structured fields, embed it, and upsert id=1."""
    text = parse_cv(filename, content)
    extracted = extract(text)
    embedding, model_name = embed_text(text)

    with db_session() as s:
        # Delete any existing row, then insert with id=1.
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
    }


# ---------------------------------------------------------------------------
# Job matching
# ---------------------------------------------------------------------------


def match_all_jobs() -> int:
    """Recompute cv_match for every job in the DB. Returns the count updated."""
    with db_session() as s:
        profile = s.get(CVProfile, 1)
        if profile is None or not profile.embedding:
            return 0
        cv_vec = list(profile.embedding)

    # Load job ids+text outside any write transaction so we don't hold a lock
    # while the embedding model churns.
    with db_session() as s:
        rows = s.execute(select(Job.id, Job.title, Job.description)).all()

    updated = 0
    batch: list[tuple[int, float]] = []
    for job_id, title, description in rows:
        body = f"{title or ''}\n{(description or '')[:3000]}"
        job_vec, _ = embed_text(body)
        score = cosine(cv_vec, job_vec)
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

        if profile is None:
            return {
                "loaded": False,
                "filename": "",
                "uploaded_at": None,
                "model": "",
                "skills": [],
                "languages": [],
                "matched_jobs": matched_count,
            }

        uploaded_at_iso = (
            profile.uploaded_at.isoformat() if profile.uploaded_at is not None else None
        )
        return {
            "loaded": True,
            "filename": profile.filename,
            "uploaded_at": uploaded_at_iso,
            "model": profile.model,
            "skills": list(profile.detected_skills or []),
            "languages": list(profile.detected_languages or []),
            "matched_jobs": matched_count,
        }
