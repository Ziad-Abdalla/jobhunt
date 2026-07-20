"""P6 safety gate: PII locality is STRUCTURAL.

The scrape/extract pipeline must never be able to touch applicant PII.
This gate greps the pipeline sources for any import of `cowork_models`
(the module holding ApplicantProfile + Application). It is deliberately a
dumb text scan: if a legitimate need ever arises, the fix is to move the
logic out of the pipeline, not to weaken this test.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "jobhunt"

# The pipeline: everything that runs during a scrape/refresh pass.
_PIPELINE_FILES = [
    SRC / "refresh.py",
    SRC / "extract.py",
    SRC / "dedup.py",
    SRC / "apply_target.py",
    SRC / "scoring.py",
    SRC / "salary_estimator.py",
    # cv_tailor is imported by the PII-side cowork_export; guard it as a
    # shared module so a future cowork_models reference in it can't ship green.
    SRC / "cv_tailor.py",
    *sorted((SRC / "scrapers").glob("*.py")),
]

_FORBIDDEN = re.compile(r"\bcowork_models\b|\bApplicantProfile\b|\bApplication\b(?!Error)")


def test_pipeline_never_imports_pii_models() -> None:
    offenders: list[str] = []
    for path in _PIPELINE_FILES:
        assert path.exists(), f"pipeline file moved? {path}"
        text = path.read_text(encoding="utf-8")
        for m in _FORBIDDEN.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            offenders.append(f"{path.name}:{line_no}: {m.group(0)}")
    assert not offenders, (
        "PII locality violated — the scrape pipeline references the "
        f"applicant-PII models: {offenders}"
    )


def test_cowork_models_module_exists() -> None:
    # The guard is only meaningful if the module it guards exists and holds
    # the PII models (they must NOT live in models.py, which the pipeline
    # legitimately imports for Job).
    from jobhunt import cowork_models, models

    assert hasattr(cowork_models, "ApplicantProfile")
    assert hasattr(cowork_models, "Application")
    assert not hasattr(models, "ApplicantProfile")
