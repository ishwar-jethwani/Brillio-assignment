"""
Test suite for the Transcript Intelligence pipeline.

Stdlib `unittest` only — same zero-dependency philosophy as the pipeline.

Run:
    python -m unittest -v              # from this directory
    python test_pipeline.py            # equivalent

The tests mix two styles:
  * Unit tests on pure functions with *synthetic* inputs (classification,
    theme scoring, sentiment mapping) — these pin the logic regardless of the
    dataset.
  * Integration / invariant tests over the real `dataset/` (counts add up,
    blast-radius >= primary, every record is well-formed) — these catch
    regressions in the end-to-end run.
"""

import unittest

import pipeline as P


# --------------------------------------------------------------------------- #
# Helpers to build synthetic call dicts
# --------------------------------------------------------------------------- #
def make_call(title="", emails=None, topics=None, sentences=None,
              overall_sentiment="mixed-positive", key_moments=None):
    return {
        "id": "TEST",
        "title": title,
        "start_time": None,
        "duration_min": 10,
        "emails": emails or [],
        "topics": topics or [],
        "summary": "",
        "action_items": [],
        "overall_sentiment": overall_sentiment,
        "sentiment_score": 3.0,
        "key_moments": key_moments or [],
        "sentences": sentences or [],
    }


# --------------------------------------------------------------------------- #
# 1. Call-type classification
# --------------------------------------------------------------------------- #
class TestCallTypeClassification(unittest.TestCase):
    def test_support_case_title_is_support(self):
        call = make_call(
            title="Support Case #1234 - Acme Widget Failure",
            emails=["agent@aegiscloud.com", "user@acme.com"],
        )
        self.assertEqual(P.classify_call_type(call), "support")

    def test_external_when_customer_domain_present(self):
        call = make_call(
            title="Aegis / Acme - Renewal Discussion",
            emails=["am@aegiscloud.com", "buyer@acme.com"],
        )
        self.assertEqual(P.classify_call_type(call), "external")

    def test_internal_when_all_company_domain(self):
        call = make_call(
            title="Weekly Engineering Standup",
            emails=["a@aegiscloud.com", "b@aegiscloud.com"],
        )
        self.assertEqual(P.classify_call_type(call), "internal")

    def test_support_title_wins_even_with_only_company_emails(self):
        # The ticket pattern is authoritative regardless of who is in the room.
        call = make_call(
            title="Support Case #9 - Internal repro",
            emails=["a@aegiscloud.com"],
        )
        self.assertEqual(P.classify_call_type(call), "support")


# --------------------------------------------------------------------------- #
# 2. Theme categorisation (weighted scoring)
# --------------------------------------------------------------------------- #
class TestThemeCategorisation(unittest.TestCase):
    def test_outage_call_is_outage(self):
        call = make_call(
            title="Detect Outage - Remediation Plan Review",
            topics=["outage remediation", "incident response"],
        )
        primary, _ = P.categorise_themes(call)
        self.assertEqual(primary, "Outage & Incident Response")

    def test_renewal_mentioning_outage_is_renewal_not_outage(self):
        # The whole point of weighted scoring: the title + dominant topic win,
        # so a trailing "outage" mention must NOT hijack the primary theme.
        call = make_call(
            title="Aegis / Quantum Edge - Renewal Concerns",
            topics=["renewal", "contract negotiation", "outage follow-up"],
        )
        primary, matches = P.categorise_themes(call)
        self.assertEqual(primary, "Renewal & Churn Risk")
        # ...but outage is still recorded as a secondary theme (blast radius).
        self.assertIn("Outage & Incident Response", matches)

    def test_compliance_call(self):
        call = make_call(
            title="Aegis / Redwood Clinical - ISO 27001 Preparation",
            topics=["iso 27001", "audit preparation", "compliance"],
        )
        primary, _ = P.categorise_themes(call)
        self.assertEqual(primary, "Compliance & Audit")

    def test_unmatched_call_degrades_gracefully(self):
        call = make_call(title="Random chat", topics=["weather", "lunch"])
        primary, matches = P.categorise_themes(call)
        self.assertEqual(primary, "Other / Uncategorised")
        self.assertEqual(matches, [])

    def test_title_outweighs_a_single_trailing_topic(self):
        # Title match (weight 3) should beat one trailing-topic match (weight 1).
        call = make_call(
            title="Aegis / Acme - Pricing Negotiation",
            topics=["account review", "renewal", "pricing"],
        )
        primary, _ = P.categorise_themes(call)
        # "pricing" is in the title (weight 3) -> Pricing & Billing wins over
        # the renewal/account-review topic hints.
        self.assertEqual(primary, "Pricing & Billing")


# --------------------------------------------------------------------------- #
# 3. Sentiment helpers
# --------------------------------------------------------------------------- #
class TestSentiment(unittest.TestCase):
    def test_sentiment_axis_ordering(self):
        axis = P.SENTIMENT_AXIS
        self.assertLess(axis["very-negative"], axis["negative"])
        self.assertLess(axis["negative"], axis["mixed-negative"])
        self.assertLess(axis["mixed-negative"], axis["mixed-positive"])
        self.assertLess(axis["mixed-positive"], axis["positive"])
        self.assertLess(axis["positive"], axis["very-positive"])

    def test_sentence_breakdown_counts_and_ratios(self):
        sentences = (
            [{"sentimentType": "positive"}] * 3
            + [{"sentimentType": "neutral"}] * 5
            + [{"sentimentType": "negative"}] * 2
        )
        b = P.sentence_sentiment_breakdown(make_call(sentences=sentences))
        self.assertEqual(b["positive"], 3)
        self.assertEqual(b["neutral"], 5)
        self.assertEqual(b["negative"], 2)
        self.assertAlmostEqual(b["negativity_ratio"], 0.2)
        self.assertAlmostEqual(b["positivity_ratio"], 0.3)

    def test_breakdown_handles_empty_transcript(self):
        b = P.sentence_sentiment_breakdown(make_call(sentences=[]))
        self.assertEqual(b["negativity_ratio"], 0.0)  # no divide-by-zero


# --------------------------------------------------------------------------- #
# 4. Enrichment of a single record
# --------------------------------------------------------------------------- #
class TestEnrich(unittest.TestCase):
    def test_enrich_sets_expected_fields(self):
        call = make_call(
            title="Support Case #5 - Acme login failures",
            emails=["agent@aegiscloud.com", "user@acme.com"],
            topics=["sso", "login failure"],
            key_moments=[{"type": "churn_signal"}, {"type": "feature_gap"}],
            overall_sentiment="very-negative",
        )
        r = P.enrich(call)
        self.assertEqual(r["call_type"], "support")
        self.assertEqual(r["customer"], "acme.com")
        self.assertTrue(r["churn_signal"])
        self.assertTrue(r["feature_gap"])
        self.assertEqual(r["sentiment_axis"], P.SENTIMENT_AXIS["very-negative"])


# --------------------------------------------------------------------------- #
# 5. Integration / invariants over the real dataset
# --------------------------------------------------------------------------- #
class TestDatasetIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls = P.load_transcripts()
        cls.records = [P.enrich(c) for c in cls.calls]
        cls.rollups = P.build_rollups(cls.records)

    def test_loads_100_calls(self):
        self.assertEqual(len(self.calls), 100)

    def test_every_call_has_a_known_type(self):
        valid = {"support", "external", "internal"}
        for r in self.records:
            self.assertIn(r["call_type"], valid)

    def test_call_type_counts_sum_to_total(self):
        by_type = self.rollups["totals"]["by_type"]
        self.assertEqual(sum(by_type.values()), len(self.records))

    def test_primary_theme_counts_sum_to_total(self):
        self.assertEqual(
            sum(self.rollups["theme_counts"].values()), len(self.records)
        )

    def test_blast_radius_at_least_primary_outage_calls(self):
        o = self.rollups["outage"]
        self.assertGreaterEqual(o["n_calls"], o["n_primary_calls"])

    def test_sentiment_scores_in_expected_range(self):
        for r in self.records:
            if r["sentiment_score"] is not None:
                self.assertGreaterEqual(r["sentiment_score"], 1.0)
                self.assertLessEqual(r["sentiment_score"], 5.0)

    def test_churn_percentages_are_valid(self):
        for s in self.rollups["sentiment_by_type"].values():
            self.assertGreaterEqual(s["pct_with_churn_signal"], 0.0)
            self.assertLessEqual(s["pct_with_churn_signal"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
