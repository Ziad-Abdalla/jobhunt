"""P9+P10: CV tailoring keyword-gap analysis + ATS linter."""

from __future__ import annotations

from jobhunt.cv_tailor import ats_lint, jd_keywords, render_markdown, tailor


class _Job:
    def __init__(self, title, skills, languages, description=""):
        self.id = 1
        self.title = title
        self.skills = skills
        self.languages = languages
        self.description = description
        self.company = "Acme"
        self.location = "Cairo, Egypt"


class TestJdKeywords:
    def test_pulls_skills_languages_title(self):
        job = _Job("Senior Django Backend Engineer", ["docker", "postgres"], ["python"])
        kw = jd_keywords(job)
        assert "docker" in kw and "postgres" in kw and "python" in kw
        assert "django" in kw  # from the title
        assert kw == sorted(set(kw))  # deduped + stable

    def test_general_terms_for_nontech_roles(self):
        # A non-tech job (the /local + Egypt persona) still gets real keyword
        # guidance from the generic vocabulary.
        job = _Job(
            "Warehouse Assistant",
            [], [],
            description="Forklift license required. Inventory management, "
                        "packaging, and delivery. Good communication and teamwork.",
        )
        kw = jd_keywords(job)
        for term in ("forklift", "warehouse", "inventory", "packaging",
                     "delivery", "communication", "teamwork"):
            assert term in kw, term


class TestAtsLint:
    def _codes(self, text):
        return {f["code"]: f["level"] for f in ats_lint(text)}

    def test_clean_cv_passes_core_checks(self):
        cv = (
            "Jane Doe\njane@example.com | +20 100 123 4567\n\n"
            "EXPERIENCE\nBackend engineer at Acme, built Django services.\n\n"
            "EDUCATION\nBSc Computer Science.\n\n"
            "SKILLS\nPython, Django, Docker, PostgreSQL.\n"
        )
        codes = self._codes(cv)
        assert codes["contact_email"] == "ok"
        assert codes["contact_phone"] == "ok"
        assert codes["sections"] == "ok"

    def test_missing_contact_flagged(self):
        codes = self._codes("EXPERIENCE\nstuff\nEDUCATION\nmore\nSKILLS\nx")
        assert codes["contact_email"] == "bad"

    def test_missing_sections_flagged(self):
        codes = self._codes("jane@example.com\n+20 100 123 4567\njust a blurb")
        assert codes["sections"] in ("warn", "bad")

    def test_multicolumn_tabs_flagged(self):
        cv = "jane@example.com\n+20 100 000\nEXPERIENCE\n" + \
             "\n".join("Left col\t\t\tRight col value here" for _ in range(6)) + \
             "\nEDUCATION x\nSKILLS y"
        codes = self._codes(cv)
        assert codes.get("layout") in ("warn", "bad")

    def test_too_short_flagged(self):
        codes = self._codes("jane@example.com +20100 EXPERIENCE EDUCATION SKILLS")
        assert codes["length"] in ("warn", "bad")

    def test_phone_not_fooled_by_date_or_salary_ranges(self):
        # Employment date ranges + salary bands must NOT count as a phone.
        cv = ("jane@x.com\nEXPERIENCE 2019-2023 earned 50,000-80,000 EGP\n"
              "EDUCATION 2015-2019\nSKILLS python " + "w " * 80)
        assert self._codes(cv)["contact_phone"] == "warn"
        # A real phone is still detected.
        cv2 = cv.replace("jane@x.com", "jane@x.com +20 100 123 4567")
        assert self._codes(cv2)["contact_phone"] == "ok"

    def test_bad_encoding_flagged(self):
        cv = "jane@example.com\n+20 100\nEXPERIENCE\ncaf� bad\nEDUCATION\nSKILLS " + "w " * 80
        codes = self._codes(cv)
        assert codes.get("encoding") == "warn"


class TestTailor:
    def test_matched_missing_and_coverage(self):
        job = _Job("Django Engineer", ["docker", "postgres", "redis"], ["python"])
        r = tailor(job, cv_skills=["docker", "django"], cv_languages=["python"],
                   cv_text="Python Django Docker developer. " * 20)
        assert "docker" in r.matched and "python" in r.matched
        assert "redis" in r.missing and "postgres" in r.missing
        # 3 of 5 JD keywords present (python, docker, django) → 60%.
        assert 55 <= r.coverage_pct <= 65

    def test_suggested_line_leads_with_matched(self):
        job = _Job("Engineer", ["docker", "kafka"], ["python"])
        r = tailor(job, cv_skills=["docker"], cv_languages=["python"], cv_text="x " * 100)
        # matched keywords appear before the "add if you have it" section.
        line = r.suggested_skills_line.lower()
        assert line.index("docker") < line.index("kafka")

    def test_empty_cv(self):
        job = _Job("Engineer", ["docker"], ["python"])
        r = tailor(job, cv_skills=[], cv_languages=[], cv_text="")
        assert r.coverage_pct == 0
        assert set(r.missing) >= {"docker", "python"}

    def test_single_char_lang_not_prose_matched(self):
        # A JD demanding "r" must not be credited by a stray "r" in CV prose;
        # only the extracted skills set counts it.
        job = _Job("Data Scientist", [], ["r"])
        r1 = tailor(job, cv_skills=[], cv_languages=[],
                    cv_text="Strong R&D background and research skills. " * 10)
        assert "r" in r1.missing  # prose "R&D" doesn't credit it
        r2 = tailor(job, cv_skills=[], cv_languages=["r"], cv_text="x " * 50)
        assert "r" in r2.matched  # the skills set does

    def test_cplusplus_matched_in_prose(self):
        job = _Job("C++ Engineer", [], ["c++"])
        r = tailor(job, cv_skills=[], cv_languages=[],
                   cv_text="Built systems in C++ for 5 years. " * 10)
        assert "c++" in r.matched  # symbol-tail token now matches prose

    def test_empty_jd_no_crash(self):
        job = _Job("Mystery Role", [], [])
        r = tailor(job, cv_skills=["docker"], cv_languages=["python"], cv_text="x " * 50)
        assert r.coverage_pct == 0
        assert r.matched == [] and r.missing == []


class TestRender:
    def test_markdown_has_sections_and_no_fabrication(self):
        job = _Job("Django Engineer", ["docker", "postgres"], ["python"])
        r = tailor(job, cv_skills=["docker"], cv_languages=["python"], cv_text="Python dev " * 40)
        md = render_markdown(r, job, applicant_name="Jane Doe")
        assert "Django Engineer" in md
        assert "Jane Doe" in md
        assert "postgres" in md  # missing keyword surfaced
        assert "coverage" in md.lower()
        # Scaffold uses blanks, never invents achievements.
        assert "___" in md or "[" in md
