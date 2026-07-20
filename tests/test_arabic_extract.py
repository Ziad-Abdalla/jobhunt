"""Arabic-awareness tests for the extract layer (P3).

Wuzzuf brings Arabic-language postings; the English keyword tables never match
them, and downstream defaults then guess mid/Full-time — silently excluding
Egypt jobs from the junior/intern filters. These tests pin the Arabic tables
and the don't-guess behaviour.
"""

from __future__ import annotations

import pytest

from jobhunt.db import db_session, init_db
from jobhunt.extract import _normalize_digits, extract, is_arabic_dominant
from jobhunt.models import Job
from jobhunt.refresh import _persist
from jobhunt.scrapers.base import RawJob

_TEST_SOURCE = "test-arabic"


@pytest.fixture()
def clean_db():
    init_db()
    with db_session() as s:
        s.query(Job).filter(Job.source == _TEST_SOURCE).delete()
    yield
    with db_session() as s:
        s.query(Job).filter(Job.source == _TEST_SOURCE).delete()


def _raw(title, description, source_id="w1"):
    return RawJob(
        source=_TEST_SOURCE, source_id=source_id,
        url=f"https://example.com/{source_id}",
        company="Test Co", title=title, description=description,
        location="Cairo, Egypt",
    )


class TestArabicDominant:
    def test_pure_arabic_is_dominant(self):
        assert is_arabic_dominant("مطلوب محاسب حديث التخرج للعمل في القاهرة") is True

    def test_pure_english_is_not(self):
        assert is_arabic_dominant("Senior Software Engineer, Cairo office") is False

    def test_mixed_mostly_english_is_not(self):
        # One Arabic word inside an English JD must not flip the switch.
        assert is_arabic_dominant(
            "Software Engineer (القاهرة) — 5 years experience required, Python, AWS"
        ) is False

    def test_mixed_mostly_arabic_is_dominant(self):
        assert is_arabic_dominant("مطلوب مهندس برمجيات Python خبرة سنتين في القاهرة الكبرى") is True

    def test_empty_string_is_not(self):
        assert is_arabic_dominant("") is False

    def test_digits_and_punctuation_only_is_not(self):
        assert is_arabic_dominant("123 - 456!") is False


class TestArabicLevel:
    def test_fresh_grad_title_is_entry(self):
        assert extract("", title="مطلوب محاسب حديث التخرج").level == "entry"

    def test_no_experience_required_is_entry(self):
        assert extract("لا تشترط خبرة سابقة للتقديم", title="محاسب").level == "entry"

    def test_intern_title(self):
        assert extract("", title="متدرب موارد بشرية").level == "intern"

    def test_junior_title(self):
        assert extract("", title="مصمم جرافيك مبتدئ").level == "junior"

    def test_senior_title(self):
        assert extract("", title="محاسب خبير").level == "senior"

    def test_team_lead_title(self):
        assert extract("", title="قائد فريق المبيعات").level == "lead"

    def test_plain_arabic_title_stays_unknown(self):
        # No level keyword → unknown (the whole point: don't guess).
        assert extract("مطلوب للعمل في شركة كبرى براتب مجزي", title="محاسب").level == "unknown"


class TestArabicYoE:
    def test_khibra_n_sanawat(self):
        assert extract("مطلوب خبرة 3 سنوات في المبيعات", title="مندوب").min_years == 3

    def test_arabic_indic_digits(self):
        assert extract("خبرة ٥ سنوات على الأقل", title="محاسب").min_years == 5

    def test_n_sanawat_khibra(self):
        assert extract("يشترط 2 سنة خبرة في المجال", title="محاسب").min_years == 2


class TestArabicEmploymentType:
    def test_dawam_kamel_full_time(self):
        assert extract("مطلوب موظف دوام كامل", title="محاسب").employment_type == "Full-time"

    def test_dawam_juzei_part_time(self):
        assert extract("وظيفة دوام جزئي مسائي", title="كاشير").employment_type == "Part-time"

    def test_freelance_contract(self):
        assert extract("فرصة عمل حر عن طريق الإنترنت", title="مصمم").employment_type == "Contract"

    def test_training_program_internship(self):
        assert extract("انضم إلى برنامج تدريب الصيفي لدينا", title="طالب").employment_type == "Internship"

    def test_plain_arabic_stays_unknown(self):
        assert extract("مطلوب للتعيين فورا براتب مجزي", title="محاسب").employment_type == "unknown"


class TestArabicRemote:
    def test_an_boad_remote(self):
        assert extract("العمل عن بعد بالكامل", title="مطور").remote == "remote"

    def test_men_almanzel_remote(self):
        assert extract("فرصة عمل من المنزل", title="مدخل بيانات").remote == "remote"

    def test_hybrid(self):
        assert extract("نظام العمل هجين ثلاثة أيام بالمكتب", title="محاسب").remote == "hybrid"

    def test_onsite(self):
        assert extract("العمل حضوري من المقر الرئيسي", title="محاسب").remote == "onsite"


class TestNoGuessingOnArabic:
    def test_arabic_no_signal_stays_unknown(self, clean_db):
        raw = _raw("محاسب", "مطلوب للعمل في شركة كبرى براتب مجزي ومزايا عديدة " * 3)
        with db_session() as s:
            _persist(s, raw, company_override=None)
        with db_session() as s:
            job = s.query(Job).filter(Job.source == _TEST_SOURCE).one()
            assert job.level == "unknown"
            assert job.employment_type == "unknown"

    def test_arabic_with_signal_still_extracts(self, clean_db):
        raw = _raw("محاسب حديث التخرج", "وظيفة دوام كامل في القاهرة " * 5, source_id="w2")
        with db_session() as s:
            _persist(s, raw, company_override=None)
        with db_session() as s:
            job = s.query(Job).filter(Job.source == _TEST_SOURCE).one()
            assert job.level == "entry"
            assert job.employment_type == "Full-time"

    def test_english_defaults_unchanged(self, clean_db):
        raw = _raw("Software Engineer", "We are a great company doing great things. " * 3,
                   source_id="w3")
        with db_session() as s:
            _persist(s, raw, company_override=None)
        with db_session() as s:
            job = s.query(Job).filter(Job.source == _TEST_SOURCE).one()
            assert job.level == "mid"            # industry-convention default kept
            assert job.employment_type == "Full-time"


class TestNormalizeDigits:
    def test_arabic_indic_digits(self):
        assert _normalize_digits("خبرة ٣ سنوات") == "خبرة 3 سنوات"

    def test_extended_arabic_indic_digits(self):
        assert _normalize_digits("۵ سال") == "5 سال"

    def test_ascii_untouched(self):
        assert _normalize_digits("3-5 years") == "3-5 years"
