# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Tests for arispec.discover -- Phase 0, profiling.

The headline tests measure against a **planted answer key**: `truth.json` was
written by the program that wrote the reports, from the values it planted,
never read back out of the text it printed. So furniture is scored as
precision AND recall by line number rather than reported as a coverage figure.

The unit tests below them each name a measured defect. Every one of those
produced a *plausible profile* rather than an error, which is why the rules
that prevent them are not obvious and must not be simplified back.
"""

import json
import unittest
from pathlib import Path

from arispec import discover

D = Path(__file__).parent / "fixtures" / "discover"
TRUTH = json.loads((D / "truth.json").read_text())


def source_text(rec):
    return (D / Path(rec["file"]).name).read_text()


class TestFurnitureAgainstThePlantedKey(unittest.TestCase):
    """The acceptance criterion, not a smoke test."""

    @classmethod
    def setUpClass(cls):
        cls.multi, cls.single = [], []
        for rec in TRUTH["sources"]:
            p = discover.profile(source_text(rec))
            (cls.multi if rec["pages"] >= 2 else cls.single).append((rec, p))

    def test_the_corpus_is_the_one_that_can_measure_this(self):
        # Three sources cannot calibrate support; 24 over nine drift axes can.
        self.assertEqual(len(TRUTH["sources"]), 24)
        self.assertEqual(len(self.multi), 20)
        self.assertEqual(len(self.single), 4)

    def test_precision_and_recall_are_both_one(self):
        tp = fp = fn = 0
        for rec, p in self.multi:
            want = set(rec["furniture_lines"])
            got = set(p["furniture"]["lines"])
            tp += len(want & got)
            fp += len(got - want)
            fn += len(want - got)
            self.assertEqual(want, got, f'{rec["id"]}: furniture disagrees')
        self.assertEqual(190, tp, "the key plants 190 furniture lines")
        self.assertEqual(0, fp, "claimed a line that is not furniture")
        self.assertEqual(0, fn, "missed a line that is")

    def test_a_single_page_source_refuses_with_a_reason(self):
        # ONE PAGE IS NOT EVIDENCE OF FURNITURE. A single-page report's header
        # is indistinguishable from its first heading -- the same lines, in the
        # same place, appearing once -- so calling it furniture would strip a
        # line section inference needs, and calling it content would be equally
        # arbitrary. The honest answer names what is missing.
        for rec, p in self.single:
            self.assertTrue(p["furniture"]["why"], f'{rec["id"]} guessed silently')
            self.assertIn("at least two pages", p["furniture"]["why"])

    def test_a_form_feed_is_furniture_by_definition(self):
        # Not by inference: it is a page break character, nothing else it could
        # be, and no support threshold applies. Missing this cost exactly one
        # line per break on every paginated source -- 8 of 9 found, which reads
        # like a rounding error and is actually a whole category.
        for rec, p in self.multi:
            rows = discover.grid(rec["id"], source_text(rec))
            for r in rows:
                if r.form_feed:
                    self.assertIn(r.physical_line, p["furniture"]["lines"])


class TestAFeedThatSharesItsLine(unittest.TestCase):
    """The fifth upstream finding, and the corpus cannot see it.

    Every source in `discover/` puts its form feed on an otherwise blank line,
    so the corpus is blind to a feed that shares a line with the header --
    which `ari_spec_language.md` §2 documents as normal and which the teller
    fixture actually does. Same shape of blindness as an all-ASCII corpus
    hiding a byte offset.
    """

    @classmethod
    def setUpClass(cls):
        text = (Path(__file__).parent / "fixtures"
                / "teller_totals_generated.rpt").read_text()
        cls.rows = discover.grid("g", text)

    def test_the_fixture_really_does_share_the_line(self):
        first = [r for r in self.rows if r.form_feed][0]
        self.assertEqual(1, first.physical_line)
        self.assertTrue(first.text.strip(), "the premise is gone; this test is moot")

    def test_a_four_page_document_has_four_pages(self):
        # gBASIC adds one to every feed line, giving FIVE starts here -- the
        # second a blank line under page one's header.
        ps = discover.page_starts(self.rows)
        self.assertEqual([1, 67, 133, 199], ps["starts"])
        self.assertEqual("form feeds", ps["evidence"])

    def test_the_header_block_is_found(self):
        # Before the fix, offset 0 compared the header against four blanks,
        # agreed 1 in 5, and the entire block was lost: furniture came back as
        # the four feed lines alone.
        f = discover.furniture(self.rows)
        self.assertEqual(4, f["pages"])
        self.assertEqual([1, 2, 67, 68, 133, 134, 199, 200], f["lines"])
        self.assertEqual([0, 1], [o["offset"] for o in f["offsets"]])

    def test_and_it_agrees_with_the_spec_a_person_wrote(self):
        # The hand-written ARI spec for this file is `break: formfeed` and
        # `drop: 2`. Discovery now derives the same rule from the bytes: two
        # furniture lines per page, four pages, eight lines. Independent
        # corroboration beats any coverage figure.
        f = discover.furniture(self.rows)
        self.assertEqual(2, len(f["offsets"]), "drop: 2 says two lines per page")
        self.assertEqual(2 * f["pages"], len(f["lines"]))


class TestTheNullCorpus(unittest.TestCase):
    """Structureless noise. The right answer is nothing."""

    def test_no_furniture_is_claimed_anywhere(self):
        # This is what caught the defect that accepted a single recurring line
        # shape as a page period: it invented pages in 14 of 18 single-page
        # sources and claimed 18 furniture lines here. Nothing else in the
        # suite could have found it.
        total = 0
        for f in sorted((D / "null").glob("*.rpt")):
            p = discover.profile(f.read_text())
            total += len(p["furniture"]["lines"])
            self.assertEqual([], p["furniture"]["lines"], f"{f.name} invented furniture")
        self.assertEqual(0, total)

    def test_and_a_period_is_not_invented(self):
        for f in sorted((D / "null").glob("*.rpt")):
            ps = discover.page_starts(discover.grid(f.stem, f.read_text()))
            self.assertEqual([1], ps["starts"], f"{f.name} invented pages")
            self.assertEqual("none", ps["evidence"])


class TestTwoIndexSpaces(unittest.TestCase):
    """The one adversarial case the design requires BEFORE Phase 1.

    Every other fixture is pure ASCII, where codepoints and bytes coincide --
    so the corpus cannot catch a mixed-up offset without this file. The defect
    it guards has shipped twice upstream: offsets accumulated with a codepoint
    length, reported as a byte offset, invisible on an ASCII fixture, and on
    the first line carrying an accented name every later field shifts one place
    left and the value is an ordinary-looking shorter string.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = (D / "adversarial" / "non_ascii.rpt").read_text()
        cls.rows = discover.grid("non_ascii", cls.text)

    def test_the_fixture_actually_diverges(self):
        # A fixture that cannot tell the two spaces apart proves nothing, so
        # assert the premise before asserting the behaviour.
        diverged = [r for r in self.rows if r.byte_length != r.cp_length]
        self.assertTrue(diverged, "the non-ASCII fixture is ASCII")

    def test_byte_offsets_index_the_real_file(self):
        raw = self.text.encode("utf-8")
        for r in self.rows:
            got = raw[r.byte_start:r.byte_start + r.byte_length].decode("utf-8")
            self.assertEqual(r.text, got.replace("\f", ""),
                             f"line {r.physical_line} byte span is wrong")

    def test_codepoint_offsets_index_the_line_arispec_will_see(self):
        for r in self.rows:
            for s in discover.spans(r.text):
                self.assertEqual(s.text, r.text[s.cp_start:s.cp_end],
                                 f"line {r.physical_line} cp span is wrong")

    def test_and_the_two_disagree_where_they_must(self):
        pairs = [(s.cp_start, s.byte_start)
                 for r in self.rows for s in discover.spans(r.text)]
        self.assertTrue(any(cp != by for cp, by in pairs),
                        "no span's two offsets differ -- the split is untested")


class TestFamilies(unittest.TestCase):
    def test_a_member_name_does_not_make_its_own_family(self):
        # THE defect. Taking every word as a literal is the obvious reading and
        # is wrong in the direction that destroys the result: a member name is
        # a word, so each detail row became its own family -- 39 families in a
        # report with four. Nothing errored; the profile was a list of lines.
        rec = TRUTH["sources"][0]
        p = discover.profile(source_text(rec))
        self.assertLess(len(p["families"]), 12,
                        "families exploded -- stability is decided by the GROUP")
        detail = max(p["families"], key=lambda f: f["count"])
        self.assertEqual(rec["families"]["detail"], detail["count"])
        self.assertEqual("<IDENTIFIER> <TEXT> <TEXT> <DATE> <MONEY>",
                         detail["signature"])

    def test_a_stable_literal_survives_so_it_can_become_an_anchor(self):
        # `ACCT` is in every member of its group, so it is a literal there;
        # `REYES` is in a few members of a large one, so it is <TEXT>. Same
        # rule, no list of "words that are probably labels".
        p = discover.profile(source_text(TRUTH["sources"][0]))
        sigs = [f["signature"] for f in p["families"]]
        self.assertTrue(any(s.startswith("ACCT ") for s in sigs), sigs)
        self.assertTrue(any("<TEXT>" in s for s in sigs))

    def test_minority_families_are_retained(self):
        # A totals row is one line per section against dozens of detail rows
        # and is shaped almost exactly like one. Forcing all lines into a
        # dominant family loses it.
        rec = TRUTH["sources"][0]
        p = discover.profile(source_text(rec))
        counts = sorted(f["count"] for f in p["families"])
        self.assertIn(rec["families"]["total"], counts)
        self.assertGreater(len(p["families"]), 4)

    def test_indent_is_part_of_the_group_key(self):
        # Without it a column heading `ACCT MEMBER NAME POSTED AMOUNT` and a
        # five-word remark note have the same shape, so they merge, no word is
        # dominant in the merged group, and both come back as five <TEXT>
        # placeholders: two families lost and the anchor destroyed.
        rows = discover.grid("x", "  ACCT MEMBER NAME POSTED AMOUNT\n"
                                  "reconciled against the general ledger\n")
        fams = discover.families(rows)
        self.assertEqual(2, len(fams))
        self.assertTrue(any(f["signature"].startswith("ACCT") for f in fams))


class TestSpansAndSignatures(unittest.TestCase):
    def test_ambiguity_is_recorded_not_resolved(self):
        # 20260916 is plausibly a date, an identifier and an integer. The
        # losers travel with the winner, because a premature choice here cannot
        # be revisited by anything downstream.
        got = discover.spans("REF 20260916 END")
        digits = [s for s in got if s.text == "20260916"]
        self.assertEqual(1, len(digits))
        self.assertTrue(digits[0].alternatives, "the competing hypothesis was discarded")

    def test_a_money_span_keeps_its_sign(self):
        # Most specific first, rejecting overlaps -- the same rule the money
        # recognizer applies, for the same reason.
        got = [s for s in discover.spans("TOTAL   $6,000.25-") if s.kind == "money"]
        self.assertEqual(["$6,000.25-"], [s.text for s in got])

    def test_a_date_is_not_split_into_an_identifier(self):
        # Checked AFTER money and date, so the "16" in "16-OCT-2026" is never a
        # separate identifier.
        kinds = {s.kind for s in discover.spans("POSTED 16-OCT-2026")}
        self.assertIn("date", kinds)
        self.assertNotIn("identifier", kinds)

    def test_a_rule_line_may_have_gaps_in_it(self):
        # A column rule under a table heading is several runs separated by
        # spaces. Requiring one unbroken run profiled every such line as
        # <OTHER> -- four per source, silently, in a category whose name says
        # the tool does not know.
        self.assertEqual("<RULE>", discover.shape("----------  --------   -----"))
        self.assertEqual("<RULE>", discover.signature("========================"))
        self.assertEqual("<BLANK>", discover.shape("    "))

    def test_a_line_of_spaces_and_one_dash_is_not_a_rule(self):
        self.assertNotEqual("<RULE>", discover.shape("   -   "))

    def test_signature_keeps_literals_and_shape_does_not(self):
        line = "  BRANCH 142  RIVERSIDE"
        self.assertEqual("BRANCH <NUMBER> RIVERSIDE", discover.signature(line))
        self.assertEqual("<WORD> <NUMBER> <WORD>", discover.shape(line))

    def test_signature_drops_exact_columns(self):
        # "Exact columns are evidence, not identity" -- a signature keyed to
        # columns makes every indent variant a different family, which is the
        # drift the tool exists to survive.
        self.assertEqual(discover.signature("BRANCH 1 X"),
                         discover.signature("        BRANCH 1 X"))

    def test_page_number_and_separator_are_not_token_kinds(self):
        # Both are conclusions about a line's ROLE, not a token's shape, and a
        # recognizer deciding them would be doing inference inside the
        # measurement layer.
        self.assertNotIn("page_number", discover.token_kinds())
        self.assertNotIn("separator", discover.token_kinds())


class TestGrid(unittest.TestCase):
    def test_a_form_feed_is_a_line_not_a_character_to_strip(self):
        # It is the strongest page evidence a print-image report carries, and
        # removing it in normalisation would throw away the one signal that
        # makes pagination unambiguous.
        rows = discover.grid("x", "a\n\fHEADER\nb\n")
        self.assertEqual([False, True, False], [r.form_feed for r in rows])
        self.assertEqual("HEADER", rows[1].text)      # the \f is not in the text
        # page_guess attributes the form-feed line to the page it ENDS, which
        # is what page_starts assumes too (a page starts at ff + 1).
        self.assertEqual([1, 1, 2], [r.page_guess for r in rows])

    def test_a_trailing_newline_is_not_a_line(self):
        self.assertEqual(2, len(discover.grid("x", "a\nb\n")))
        self.assertEqual(2, len(discover.grid("x", "a\nb")))


class TestOptions(unittest.TestCase):
    def test_an_unknown_option_is_refused_and_names_the_known_set(self):
        with self.assertRaises(ValueError) as cm:
            discover.profile("a\n", {"minimum_suport": 0.9})
        self.assertIn("is not an option", str(cm.exception))
        self.assertIn("minimum_support", str(cm.exception))

    def test_the_default_support_is_the_documented_one(self):
        self.assertEqual(0.80, discover.Options().minimum_support)


class TestCorpusProfile(unittest.TestCase):
    def test_a_signature_carries_how_many_sources_have_it(self):
        # Variation between files is what separates a true constant from an
        # accidental one, so support is counted in SOURCES, not in lines.
        sources = [{"id": r["id"], "text": source_text(r)}
                   for r in TRUTH["sources"][:12]]
        c = discover.profile_corpus(sources)
        self.assertEqual(12, c["sources"])
        self.assertTrue(c["shared"])
        for e in c["shared"]:
            self.assertGreaterEqual(e["support"], 0.80)
            self.assertLessEqual(e["sources"], 12)

    def test_a_small_corpus_says_its_threshold_cannot_be_calibrated(self):
        # Ten is where a tenth of a point of support is one source. Saying so
        # beats reporting a figure that can only take a few values.
        c = discover.profile_corpus([{"id": "a", "text": "X 1\n"},
                                     {"id": "b", "text": "X 2\n"}])
        self.assertIn("cannot be calibrated", c["warning"])

    def test_an_empty_corpus_is_refused(self):
        with self.assertRaises(ValueError):
            discover.profile_corpus([])

    def test_profiling_is_not_repeated_when_the_caller_has_it(self):
        # Profiling is the expensive half; re-profiling would be the same
        # answer at several times the cost.
        sources = [{"id": "a", "text": "X 1\n"}]
        first = discover.profile_corpus(sources)
        again = discover.profile_corpus(sources, profiles_in=first["profiles"])
        self.assertIs(first["profiles"][0], again["profiles"][0])


class TestTheBoundary(unittest.TestCase):
    def test_arispec_does_not_import_discovery(self):
        # The architectural rule: the deterministic parser must stay free of
        # clustering and inference, so a caller with a known specification pays
        # none of it. `import arispec` must not drag this in.
        import subprocess
        import sys
        out = subprocess.run(
            [sys.executable, "-c",
             "import arispec, sys; print('arispec.discover' in sys.modules)"],
            capture_output=True, text=True, cwd=str(Path(__file__).parent.parent))
        self.assertEqual("False", out.stdout.strip(), out.stderr)


if __name__ == "__main__":
    unittest.main()
