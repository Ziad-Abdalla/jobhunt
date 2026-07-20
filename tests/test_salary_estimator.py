"""Egypt/GCC salary-estimator regions (P3). Multipliers express local-currency
annual amounts relative to the USD baseline (existing convention)."""

from __future__ import annotations

from jobhunt.salary_estimator import estimate_salary, infer_region


class TestMenaRegions:
    def test_cairo_is_egypt(self):
        assert infer_region("Cairo, Egypt") == "egypt"

    def test_arabic_cairo_is_egypt(self):
        assert infer_region("القاهرة") == "egypt"

    def test_alexandria_is_egypt(self):
        assert infer_region("Alexandria, Egypt") == "egypt"

    def test_dubai_is_gcc(self):
        assert infer_region("Dubai, UAE") == "gcc"

    def test_riyadh_is_gcc(self):
        assert infer_region("Riyadh, Saudi Arabia") == "gcc"

    def test_egypt_estimate_is_egp(self):
        est = estimate_salary("entry", "Cairo, Egypt")
        assert est.currency == "EGP"
        # Local-currency annual: entry baseline 65-100k USD × 4.0 ⇒ 260k-400k EGP.
        assert 200_000 <= est.min_salary <= 500_000

    def test_gcc_estimate_is_aed(self):
        est = estimate_salary("mid", "Dubai, UAE")
        assert est.currency == "AED"

    def test_london_still_uk(self):
        assert infer_region("London, UK") == "uk"
