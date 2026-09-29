# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Tests for discovery Phase 1 -- proposing a specification.

Scored against the corpus's **planted** answer key, which is what makes these
measurements rather than assertions. A coverage percentage cannot substitute:
a specification can claim every line and extract the wrong number, and the
headline test below is exactly that case.
"""

import json
import unittest
from decimal import Decimal
from pathlib import Path

import arispec
from arispec import discover

D = Path(__file__).parent / "fixtures" / "discover"
TRUTH = json.loads((D / "truth.json").read_text())
RECS = TRUTH["sources"][:8]
SOURCES = [{"id": r["id"], "text": (D / Path(r["file"]).name).read_text()}
           for r in RECS]


def planted_amounts(rec):
    return [Decimal(a["amount_cents"]) / 100
            for b in rec["branches"] for a in b["accounts"]]


def planted_accounts(rec):
    return {a["account"] for b in rec["branches"] for a in b["accounts"]}


class TestTheProposal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = discover.infer(SOURCES)

    def test_it_picks_the_dominant_repeating_family(self):
        self.assertTrue(self.p["ok"], self.p["why"])
        self.assertEqual("<IDENTIFIER> <TEXT> <TEXT> <DATE> <MONEY>", self.p["family"])
        self.assertEqual(8, self.p["family_sources"])
        self.assertGreater(self.p["family_share"], 0.15)

    def test_field_names_come_from_the_column_heading(self):
        names = [f["name"] for f in self.p["fields"]]
        self.assertEqual(["posted", "amount"], names)
        self.assertTrue(self.p["heading"].strip())

    def test_the_generated_spec_carries_its_evidence(self):
        # A person maintains this afterwards WITHOUT this library, so the
        # reasoning cannot live in a report that gets thrown away.
        self.assertIn("' the only money column on the row", self.p["spec"])
        self.assertIn("field amount: first money as money", self.p["spec"])
        self.assertIn("' Detail family:", self.p["spec"])

    def test_the_generated_spec_is_valid_input_to_the_parser(self):
        r = arispec.parse(SOURCES[0]["text"], self.p["spec"])
        self.assertTrue(r.ok, r.message)

    def test_it_recovers_every_planted_amount(self):
        # THE STRONG ORACLE. `first money` is anchor-relative and survives the
        # corpus's nine drift axes.
        hit = miss = 0
        for rec, s in zip(RECS, SOURCES):
            got = [r["amount"] for r in arispec.parse(s["text"], self.p["spec"]).value["rows"]]
            for w in planted_amounts(rec):
                hit += 1 if w in got else 0
                miss += 0 if w in got else 1
        self.assertEqual(230, hit + miss, "the corpus plants 230 detail rows")
        self.assertEqual(0, miss, "an anchor-relative locator lost a planted value")

    def test_the_validation_counts_every_row(self):
        v = self.p["validation"]
        self.assertEqual(1.0, v["source_coverage"])
        self.assertEqual(230, v["rows"])
        self.assertEqual(0.0, v["unknown_rate"])


class TestWhatItWillNotReach(unittest.TestCase):
    """The honest half: a report's limits are the report's, and saying so is
    the profile."""

    @classmethod
    def setUpClass(cls):
        cls.p = discover.infer(SOURCES)

    def test_unreachable_columns_become_questions_with_options(self):
        # A detail row carries no literal anchors, so first/last reaches the
        # money and the date and nothing else.
        fields = {q["field"] for q in self.p["questions"]}
        self.assertEqual({"acct_no", "member_name"}, fields)
        for q in self.p["questions"]:
            self.assertTrue(q["options"], "a question with no options is a complaint")
            self.assertIn("anchor-relative", q["why"])
            self.assertTrue(q["example"], "a question should show what it is about")

    def test_identifier_is_not_reachable_by_first_or_last(self):
        # `first integer` on `00147454` answers 147454 -- LEADING ZEROS GONE,
        # and a number where the source had a code.
        self.assertNotIn("identifier",
                         [f["type"] for f in self.p["fields"]])
        r = arispec.parse("  00147454  REYES, YUKI\n",
                          "section r:\n    rows:\n        field a: first integer\n")
        self.assertEqual([147454], r.value["rows"]["a"])   # the value a code is not

    def test_no_positional_rule_is_proposed_by_default(self):
        self.assertEqual([], [f for f in self.p["fields"] if f["positional"]])
        self.assertFalse(discover.Options().allow_fixed_columns)


class TestThePositionalTrap(unittest.TestCase):
    """`allow_fixed_columns` produces a specification that scores perfectly
    and is wrong a third of the time."""

    @classmethod
    def setUpClass(cls):
        cls.p = discover.infer(SOURCES, {"allow_fixed_columns": True})

    def test_it_now_proposes_columns(self):
        locs = {f["name"]: f["locator"] for f in self.p["fields"]}
        self.assertEqual("columns 4-11", locs["acct_no"])
        self.assertTrue(any(f["positional"] for f in self.p["fields"]))
        self.assertIn("breaks if the report drifts",
                      [f["why"] for f in self.p["fields"] if f["positional"]][0])

    def test_and_the_scorecard_says_it_is_perfect(self):
        v = self.p["validation"]
        self.assertEqual(1.0, v["source_coverage"])
        self.assertEqual(0.0, v["unknown_rate"])
        self.assertEqual(230, v["rows"])

    def test_while_a_third_of_the_values_are_wrong(self):
        hit = miss = 0
        for rec, s in zip(RECS, SOURCES):
            got = {str(r["acct_no"])
                   for r in arispec.parse(s["text"], self.p["spec"]).value["rows"]}
            want = planted_accounts(rec)
            hit += len(want & got)
            miss += len(want - got)
        self.assertEqual(230, hit + miss)
        self.assertEqual(147, hit, "the measured recovery of columns 4-11")
        self.assertEqual(83, miss)

    def test_and_the_leading_zeros_are_gone(self):
        # An account number that reads back shorter is exactly the
        # ordinary-looking wrong value this library exists to refuse.
        got = arispec.parse(SOURCES[0]["text"], self.p["spec"]).value["rows"][0]["acct_no"]
        self.assertEqual("147454", str(got))
        self.assertIn("00147454", planted_accounts(RECS[0]))

    def test_only_anchor_stability_catches_it(self):
        # It needs no answer key: it asks whether the family's column
        # structure is the same in every source.
        st = self.p["anchor_stability"]
        self.assertEqual(7, st["layouts"], "7 distinct layouts across 8 sources")
        self.assertEqual(8, st["sources"])
        self.assertLess(st["stability"], 0.5)


class TestGutters(unittest.TestCase):
    def test_a_column_is_bounded_by_whitespace_on_every_row(self):
        # Not by the extent of the values that happened to be in it: taking
        # each span's min..max across the family returned `147454` for an
        # account column starting at 2, and a name as `YES, YUKI`.
        rows = discover.grid("x",
            "  00147454    REYES, YUKI           947.08\n"
            "  00149767    DELACROIX, FRANCOIS  1180.00\n")
        cols = discover.gutters(rows, [1, 2])
        self.assertEqual(2, cols[0]["cp_start"], "the column starts where the data does")
        widest = max(len("REYES, YUKI"), len("DELACROIX, FRANCOIS"))
        self.assertGreaterEqual(cols[1]["cp_end"] - cols[1]["cp_start"] + 1, widest)

    def test_a_single_space_is_not_a_gutter(self):
        # `REYES, YUKI` has one inside a single value, and its position MOVES
        # with the surname's length -- which is why the all-rows test settles
        # it, and why a surname and forename become ONE field.
        rows = discover.grid("x",
            "  00147454    REYES, YUKI           947.08\n"
            "  00149767    DELACROIX, FRANCOIS  1180.00\n")
        cols = discover.gutters(rows, [1, 2])
        self.assertEqual(3, len(cols), "the name split into two columns")


class TestRefusal(unittest.TestCase):
    def test_the_null_corpus_gets_no_proposal(self):
        # THE NULL CORPUS CAUGHT PHASE 1 TOO. Requiring recurrence alone,
        # infer proposed a spec for structureless text: a `<MONEY> <DATE>`
        # family of ONE LINE, recurring in 11 of 12 sources by chance, because
        # a two-token shape recurs whenever tokens are drawn at random.
        nulls = [{"id": f.stem, "text": f.read_text()}
                 for f in sorted((D / "null").glob("*.rpt"))]
        p = discover.infer(nulls)
        self.assertFalse(p["ok"])
        self.assertEqual("", p["spec"])
        self.assertIn("DOMINANT", p["why"])
        self.assertIn("no repeating structure", p["why"])

    def test_dominance_is_what_separates_them(self):
        # The real corpus's detail family holds over half its source's content
        # lines; the null corpus's best holds a fiftieth. The default sits
        # between, with room on both sides.
        real = discover.infer(SOURCES)
        self.assertGreater(real["family_share"], 0.40)

    def test_a_proposal_has_no_truth_value(self):
        # A proposal with open questions is not a failure.
        with self.assertRaises(TypeError):
            bool(discover.infer(SOURCES))


class TestHoldout(unittest.TestCase):
    def test_it_reserves_the_last_sources_and_scores_them_apart(self):
        # A spec inferred from a corpus and scored on that same corpus is
        # scored on the data that shaped it. The two numbers only part company
        # when something has been fitted to the training set -- which is
        # exactly when a reader needs to know.
        p = discover.infer(SOURCES, {"holdout": 3})
        self.assertEqual(5, p["trained_on"])
        self.assertEqual(3, p["holdout"]["sources"])
        self.assertEqual(1.0, p["holdout"]["source_coverage"])
        self.assertEqual(230, p["validation"]["rows"] + p["holdout"]["rows"])

    def test_the_same_ordered_corpus_gives_the_same_split(self):
        # Reserved from the end, not at random: a random split would make the
        # result depend on a seed nobody passed.
        a = discover.infer(SOURCES, {"holdout": 3})
        b = discover.infer(SOURCES, {"holdout": 3})
        self.assertEqual(a["spec"], b["spec"])

    def test_a_holdout_that_leaves_nothing_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            discover.infer(SOURCES[:2], {"holdout": 2})
        self.assertIn("leaves nothing to infer from", str(cm.exception))


class TestValidate(unittest.TestCase):
    def test_a_measure_with_nothing_behind_it_is_none_not_zero(self):
        # Nothing parsed means nothing was measured, and a 0 there reads as a
        # specification that explained none of the text -- a different claim,
        # and one a reader would act on.
        v = discover.validate([], "section r:\n    field a: right of \"x\"\n")
        self.assertIsNone(v["content_coverage"])
        self.assertIsNone(v["collision_rate"])

    def test_a_spec_that_will_not_read_is_a_failure_not_a_crash(self):
        v = discover.validate(SOURCES[:1], "section r:\n    field a: right of \"x\" as munny\n")
        self.assertEqual(0.0, v["source_coverage"])
        self.assertEqual(1, len(v["failures"]))
        self.assertIn("munny", v["failures"][0]["why"])

    def test_the_fractions_carry_their_own_definition(self):
        v = discover.validate(SOURCES[:2], discover.infer(SOURCES)["spec"])
        self.assertIn("pooled over every source", v["content_coverage_is"])
        self.assertIn("value claims", v["collision_rate_is"])

    def test_scores_are_pooled_not_averaged(self):
        # So a short source that happens to be fully explained cannot offset a
        # long one that is not.
        spec = discover.infer(SOURCES)["spec"]
        one = discover.validate(SOURCES[:1], spec)
        two = discover.validate(SOURCES[:2], spec)
        self.assertEqual(two["content_chars"],
                         one["content_chars"] + discover.validate(SOURCES[1:2], spec)["content_chars"])


if __name__ == "__main__":
    unittest.main()
