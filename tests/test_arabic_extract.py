"""Arabic-awareness tests for the extract layer (P3).

Wuzzuf brings Arabic-language postings; the English keyword tables never match
them, and downstream defaults then guess mid/Full-time — silently excluding
Egypt jobs from the junior/intern filters. These tests pin the Arabic tables
and the don't-guess behaviour.
"""

from __future__ import annotations

from jobhunt.extract import _normalize_digits, extract, is_arabic_dominant


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


class TestNormalizeDigits:
    def test_arabic_indic_digits(self):
        assert _normalize_digits("خبرة ٣ سنوات") == "خبرة 3 سنوات"

    def test_extended_arabic_indic_digits(self):
        assert _normalize_digits("۵ سال") == "5 سال"

    def test_ascii_untouched(self):
        assert _normalize_digits("3-5 years") == "3-5 years"
