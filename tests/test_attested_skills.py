"""AttestedSkill model + profile columns (2026-07-25 CV auto-tailoring)."""
from __future__ import annotations

from jobhunt.db import db_session, init_db


def test_attested_skill_roundtrip():
    from jobhunt.cowork_models import AttestedSkill

    init_db()
    with db_session() as s:
        s.add(AttestedSkill(
            keyword_norm="graphql", display="GraphQL",
            category_target="Backend / Frontend",
            project_targets=["UniVeranstaltungen"],
        ))
    with db_session() as s:
        row = s.query(AttestedSkill).filter_by(keyword_norm="graphql").one()
        assert row.display == "GraphQL"
        assert row.project_targets == ["UniVeranstaltungen"]


def test_profile_tailoring_columns_default_empty():
    from jobhunt.cowork_models import ApplicantProfile

    init_db()
    with db_session() as s:
        p = s.get(ApplicantProfile, 1) or ApplicantProfile(id=1)
        s.add(p)
    with db_session() as s:
        p = s.get(ApplicantProfile, 1)
        assert p.cv_docx_egypt == "" and p.cv_docx_remote == ""
        assert p.summary_template == "" and p.cv_anchors == ""
