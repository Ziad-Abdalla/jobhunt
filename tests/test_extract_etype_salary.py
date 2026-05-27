"""Tests for employment type and salary extraction from description text."""

from jobhunt.extract import extract


class TestEmploymentTypeExtraction:
    def test_fulltime_from_description(self):
        e = extract("This is a full-time position. We offer competitive pay.")
        assert e.employment_type == "Full-time"

    def test_parttime_from_description(self):
        e = extract("Part-time role, 20 hours per week.")
        assert e.employment_type == "Part-time"

    def test_contract_from_description(self):
        e = extract("This is a 6-month contract position.")
        assert e.employment_type == "Contract"

    def test_freelance_is_contract(self):
        e = extract("Freelance opportunity for experienced designers.")
        assert e.employment_type == "Contract"

    def test_internship_from_description(self):
        e = extract("Summer internship program for students.")
        assert e.employment_type == "Internship"

    def test_unknown_when_not_mentioned(self):
        e = extract("We are looking for a software engineer.")
        assert e.employment_type == "unknown"

    def test_german_vollzeit(self):
        e = extract("Vollzeit-Stelle in unserem Berliner Büro.")
        assert e.employment_type == "Full-time"


class TestSalaryExtraction:
    def test_usd_range(self):
        e = extract("Salary: $120,000 - $180,000 per year.")
        assert e.salary_min == 120000
        assert e.salary_max == 180000
        assert e.salary_currency == "USD"

    def test_k_notation(self):
        e = extract("Compensation: $120k-$180k annually.")
        assert e.salary_min == 120000
        assert e.salary_max == 180000

    def test_gbp_range(self):
        e = extract("Salary range: £45,000 to £55,000.")
        assert e.salary_min == 45000
        assert e.salary_max == 55000
        assert e.salary_currency == "GBP"

    def test_eur_range(self):
        e = extract("Base salary: €60,000 – €80,000.")
        assert e.salary_min == 60000
        assert e.salary_max == 80000
        assert e.salary_currency == "EUR"

    def test_no_salary_when_absent(self):
        e = extract("We offer competitive compensation and benefits.")
        assert e.salary_min is None
        assert e.salary_max is None

    def test_ignores_tiny_numbers(self):
        e = extract("Salary: $5 - $10 per hour.")
        assert e.salary_min is None

    def test_salary_near_context_keyword(self):
        e = extract(
            "About the role: build great things. "
            "Compensation range: $150,000 - $200,000 annually."
        )
        assert e.salary_min == 150000
        assert e.salary_max == 200000


class TestRemoteFromLocation:
    def test_remote_in_location(self):
        e = extract("", title="Remote - Software Engineer")
        assert e.remote == "remote"

    def test_anywhere_in_location(self):
        e = extract("", title="Engineer - Anywhere")
        assert e.remote == "remote"
