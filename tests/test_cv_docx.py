"""cv_docx: pure tailoring logic (Task 2) + calibration/generation (Tasks 3-4)."""
from __future__ import annotations

import pytest

ATTESTED = [
    {"keyword_norm": "graphql", "display": "GraphQL",
     "category_target": "Backend / Frontend",
     "project_targets": ["UniVeranstaltungen"]},
    {"keyword_norm": "security", "display": "Security",
     "category_target": "Data / DevOps", "project_targets": []},
]


def test_order_for_jd_stable():
    from jobhunt.cv_docx import order_for_jd
    items = ["LangChain", "RAG", "FAISS"]
    assert order_for_jd(items, {"faiss", "rag"}) == ["RAG", "FAISS", "LangChain"]
    assert order_for_jd(items, set()) == items


def test_merged_skills_body_inserts_attested_and_leads_jd():
    from jobhunt.cv_docx import merged_skills_body
    body = "FastAPI · REST · React"
    out = merged_skills_body(body, ATTESTED, "Backend / Frontend", {"graphql", "react"})
    # attested GraphQL inserted; JD-relevant (react, graphql) lead, original order otherwise
    assert out == "React · GraphQL · FastAPI · REST"


def test_merged_skills_body_no_duplicate_insert():
    from jobhunt.cv_docx import merged_skills_body
    out = merged_skills_body("GraphQL · REST", ATTESTED, "Backend / Frontend", set())
    assert out.count("GraphQL") == 1


def test_stack_addition_only_when_jd_asks():
    from jobhunt.cv_docx import stack_addition
    assert stack_addition("UniVeranstaltungen", ATTESTED, {"graphql"}) == ["GraphQL"]
    assert stack_addition("UniVeranstaltungen", ATTESTED, {"python"}) == []
    assert stack_addition("DocAI", ATTESTED, {"graphql"}) == []


def test_render_summary_and_em_dash_guard():
    from jobhunt.cv_docx import render_summary
    assert render_summary("Engineer with {skills}.", ["RAG", "GraphQL"]) == \
        "Engineer with RAG, GraphQL."
    with pytest.raises(ValueError):
        render_summary("Engineer — with {skills}.", ["RAG"])


def test_top_skills_for_jd_ordered_max3():
    from jobhunt.cv_docx import top_skills_for
    jd = ["ai", "graphql", "python", "rag", "rest"]
    out = top_skills_for(jd, matched=["ai", "python", "rag", "rest"], attested=ATTESTED)
    assert out == ["ai", "GraphQL", "python"]  # first 3 in JD order, display-cased


def test_slug():
    from jobhunt.cv_docx import slug
    assert slug("GitLab, Inc.") == "GitLab_Inc"
    assert slug("") == "CV"


def make_cv_docx(path):
    """Fixture mirroring the real masters' layout, incl. multi-run
    paragraphs (bold labels) so run-level editing is genuinely exercised."""
    from docx import Document
    doc = Document()
    doc.add_paragraph("Ziad Ahmed Abdalla")
    doc.add_paragraph("Professional Profile")
    doc.add_paragraph("AI engineer who ships products end-to-end.")
    doc.add_paragraph("Key Projects")
    proj = doc.add_paragraph()
    proj.add_run("UniVeranstaltungen - Events Platform   ").bold = True
    proj.add_run("(React · TypeScript · Node)")
    doc.add_paragraph("•  100+ components (JWT RBAC) shipped")
    doc.add_paragraph("Technical Skills")
    line = doc.add_paragraph()
    line.add_run("Backend / Frontend:").bold = True
    line.add_run("   FastAPI · REST · React")
    doc.add_paragraph("Data / DevOps:   PostgreSQL · Docker")
    doc.add_paragraph("Education")
    doc.add_paragraph("German University in Cairo")
    doc.save(str(path))


def test_calibrate_docx(tmp_path):
    from jobhunt.cv_docx import calibrate_docx, file_sha256
    f = tmp_path / "cv.docx"
    make_cv_docx(f)
    cal = calibrate_docx(f)
    assert cal["sha256"] == file_sha256(f)
    assert cal["summary"] == "AI engineer who ships products end-to-end."
    assert [line["label"] for line in cal["skills_lines"]] == \
        ["Backend / Frontend", "Data / DevOps"]
    assert cal["projects"][0]["name"] == "UniVeranstaltungen - Events Platform"
    assert cal["projects"][0]["stack"] == "React · TypeScript · Node"
    # the bullet with parentheses must NOT be a project
    assert len(cal["projects"]) == 1


def test_calibrate_docx_missing_sections_raises(tmp_path):
    from docx import Document

    from jobhunt.cv_docx import calibrate_docx

    f = tmp_path / "bad.docx"
    d = Document()
    d.add_paragraph("Just a name")
    d.save(str(f))
    with pytest.raises(ValueError, match="summary"):
        calibrate_docx(f)
