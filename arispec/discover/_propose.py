# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``infer`` -- the Phase 1 entry point."""

from __future__ import annotations

from ._infer import infer_fields, spec_text
from ._options import options_from
from ._profile import profile_corpus
from ._validate import anchor_stability, validate

__all__ = ["Proposal", "infer"]


class Proposal(dict):
    """A proposal, or a refusal. ``ok`` says which.

    A dict so it serialises without ceremony -- a review that cannot be
    written down cannot be reproduced.
    """

    def __bool__(self):
        raise TypeError(
            "a Proposal has no truth value -- a proposal with open questions "
            "is not a failure. Test it with ['ok'].")


def infer(sources, options=None) -> Proposal:
    """Propose a specification for the dominant repeating row family.

    ``holdout: n`` reserves the **last** n sources from inference and scores
    them separately. Reserved from the end rather than at random, because the
    same ordered corpus must give the same proposal: a random split would make
    the result depend on a seed nobody passed. A caller wanting a different
    split orders the corpus differently, which is a decision they can see.

    What holdout is *for* is not reassurance. A specification inferred from a
    corpus and scored on that same corpus is scored on the data that shaped
    it, and the two numbers only part company when something has been fitted
    to the training set -- which is exactly when a reader needs to know.
    """
    o = options_from(options)
    sources = list(sources)
    train, held = sources, []
    if o.holdout > 0:
        if o.holdout >= len(sources):
            raise ValueError(
                f"discover.infer: holdout of {o.holdout} leaves nothing to "
                f"infer from ({len(sources)} sources)")
        train, held = sources[:-o.holdout], sources[-o.holdout:]

    corpus = profile_corpus(train, o)
    best, candidates = None, []

    for p in corpus["profiles"]:
        content = sum(1 for r in p["grid"]
                      if not r.blank and r.physical_line not in set(p["furniture"]["lines"]))
        for fm in p["families"]:
            # The candidate must be DOMINANT within its own source, not merely
            # recurring across the corpus.
            #
            # MEASURED: requiring recurrence alone, `infer` proposed a
            # specification for the NULL corpus. The family it chose was
            # `<MONEY> <DATE>` -- ONE LINE in its source -- appearing in 11 of
            # 12 structureless sources by pure chance, because a two-token
            # shape recurs whenever tokens are drawn at random. It cleared
            # minimum_support and was the largest shared family, so it won.
            #
            # The share separates them by a wide margin: the real corpus's
            # detail family holds 55% of its source's content lines, the null
            # corpus's best holds 1.5%. The default sits between, with room on
            # both sides, and is an OPTION rather than a constant so a report
            # whose detail rows are a genuinely small minority can say so.
            share = fm["count"] / content if content else 0
            if share < o.minimum_family_share:
                continue
            shared = sum(1 for q in corpus["profiles"]
                         for g in q["families"] if g["signature"] == fm["signature"])
            if shared / corpus["sources"] < o.minimum_support:
                continue
            cand = {"family": fm, "profile": p, "shared": shared, "share": share}
            candidates.append(cand)
            if best is None or fm["count"] > best["family"]["count"]:
                best = cand

    if best is None:
        # A REFUSAL, not an empty proposal. Nothing recurs across the corpus,
        # so there is nothing a specification could be written against -- which
        # is the right answer on a corpus with no structure in it.
        return Proposal(
            ok=False, spec="", fields=[], questions=[], alternatives=[],
            trained_on=len(train), holdout=None, corpus=corpus,
            why=(f"no row family is both DOMINANT within a source (at least "
                 f"{int(o.minimum_family_share * 100)}% of its content lines) "
                 f"and present in at least {int(o.minimum_support * 100)}% of "
                 f"the {corpus['sources']} sources, so there is no repeating "
                 f"structure to write a specification against"))

    # The candidates NOT chosen, deduplicated: a review can only name an
    # alternative that was recorded.
    alternatives, seen = [], set()
    for c in candidates:
        sig = c["family"]["signature"]
        if sig == best["family"]["signature"] or sig in seen:
            continue
        seen.add(sig)
        alternatives.append({
            "kind": "row_family", "signature": sig,
            "lines": c["family"]["count"], "share": c["share"],
            "sources": c["shared"],
            "why_not": (f"it clears both thresholds but holds "
                        f"{c['family']['count']} lines against the chosen "
                        f"family's {best['family']['count']}")})

    inferred = infer_fields(best["profile"]["grid"], best["family"],
                            best["profile"]["furniture"]["lines"], o)
    spec = spec_text(best["family"], inferred, o)

    stability = anchor_stability(train, best["family"]["signature"], o,
                                 corpus["profiles"])
    scored = validate(train, spec, o)
    held_score = validate(held, spec, o) if held else None

    return Proposal(
        ok=True, why="", spec=spec,
        family=best["family"]["signature"],
        family_lines=best["family"]["count"], family_share=best["share"],
        family_sources=best["shared"],
        fields=inferred["fields"], questions=inferred["questions"],
        heading=inferred["heading"], columns=inferred["columns"],
        alternatives=alternatives,
        validation=scored, anchor_stability=stability,
        holdout=held_score, trained_on=len(train), corpus=corpus)
