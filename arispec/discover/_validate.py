# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Scoring a candidate specification -- by running it, not by modelling it.

Every measure here is computed by executing the proposal with the same engine
that will execute it in production. Estimating a score from the inference
model that produced the proposal would be the tool grading its own homework.

The measure that matters most needs **no answer key**: a positional rule can
score a perfect coverage and a zero unknown rate while a third of its values
come from the wrong column. :func:`anchor_stability` is what catches that, by
asking whether the family's column structure is the same in every source.
"""

from __future__ import annotations

from collections import defaultdict

from .. import UNKNOWN, parse, trace
from ._families import families
from ._furniture import furniture
from ._grid import grid
from ._infer import gutters
from ._options import options_from

__all__ = ["anchor_stability", "validate"]


def _is_frame(d) -> bool:
    """A ``rows:`` block: equal-length columns of scalars.

    Checked structurally rather than by key name, because a section record
    whose children all repeat is also a dict of lists -- and counting *that*
    as a frame would turn a report's branches into rows.
    """
    if not d:
        return False
    vals = list(d.values())
    if not all(isinstance(v, list) for v in vals):
        return False
    if any(isinstance(x, dict) for v in vals for x in v):
        return False
    return len({len(v) for v in vals}) == 1


def _count_rows(value, key=None):
    """Rows, cells and unknown cells in a parsed value tree.

    Two record shapes reach here and both are ordinary. A ``rows:`` block is a
    frame -- columns of equal length. A generated spec instead writes
    ``section rows repeats starts(...)``, one section instance per line, which
    arrives as a list of records. gBASIC counts only the second, so a
    hand-written spec using ``rows:`` scores zero rows there; both are counted
    here.
    """
    rows = cells = unknown = 0
    if isinstance(value, dict):
        if _is_frame(value):
            cols = list(value.values())
            rows += len(cols[0])
            for col in cols:
                cells += len(col)
                unknown += sum(1 for x in col if x is UNKNOWN)
            return rows, cells, unknown
        if key == "rows":
            rows += 1
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                r, c, u = _count_rows(v, k)
                rows, cells, unknown = rows + r, cells + c, unknown + u
            else:
                cells += 1
                unknown += 1 if v is UNKNOWN else 0
    elif isinstance(value, list):
        for item in value:
            r, c, u = _count_rows(item, key)
            rows, cells, unknown = rows + r, cells + c, unknown + u
    return rows, cells, unknown


def validate(sources, spec: str, options=None) -> dict:
    """Run *spec* over *sources* and score it.

    Pooled rather than averaged, so a short source that happens to be fully
    explained cannot offset a long one that is not.
    """
    options_from(options)
    sources = list(sources)
    parsed_ok = rows_total = cells_total = cells_unknown = 0
    content_chars = claimed_chars = claims_total = collided = 0
    failures = []

    for s in sources:
        try:
            r = parse(s["text"], spec)
        except Exception as e:                      # noqa: BLE001
            failures.append({"id": s.get("id", "?"), "why": str(e)})
            continue
        if not r.ok:
            failures.append({"id": s.get("id", "?"), "why": r.message})
            continue
        parsed_ok += 1
        rows, cells, unknown = _count_rows(r.value)
        rows_total += rows
        cells_total += cells
        cells_unknown += unknown

        t = trace(s["text"], spec)
        if t.result.ok:
            content_chars += t.content_chars
            claimed_chars += t.claimed_chars
            claims_total += sum(1 for c in t.claims if c["kind"] == "field")
            collided += sum(1 for c in t.claims if c["kind"] == "field"
                            and any(c["path"] in col["paths"] for col in t.collisions))

    return {
        "source_coverage": parsed_ok / len(sources) if sources else 0,
        "sources": len(sources), "parsed": parsed_ok,
        "rows": rows_total, "cells": cells_total,
        "unknown_rate": cells_unknown / cells_total if cells_total else 0,
        "failures": failures,
        "content_chars": content_chars, "claimed_chars": claimed_chars,
        # `None`, never 0. Nothing parsed means nothing was measured, and a 0
        # there reads as a specification that explained none of the text -- a
        # different claim, and one a reader would act on.
        "content_coverage": claimed_chars / content_chars if content_chars else None,
        "content_coverage_is": (
            "non-blank characters on non-furniture lines claimed by a field "
            "rule or a section heading, pooled over every source that parsed, "
            "over all non-blank characters on those lines"),
        "claims": claims_total, "collisions_involved": collided,
        "collision_rate": collided / claims_total if claims_total else None,
        "collision_rate_is": (
            "value claims whose character extent overlaps another rule's "
            "claim, over all value claims, pooled over every source"),
    }


def anchor_stability(sources, family_signature: str, options=None,
                     profiles=None) -> dict:
    """Is this family's column structure the same in every source?

    **This is the measure that needs no answer key**, and it is the one that
    catches a positional rule pretending to work. A `columns` rule inferred
    from one source scores a perfect `source_coverage` and a zero
    `unknown_rate` on a corpus whose table indent drifts -- every value
    extracted, every value an ordinary-looking account number from the wrong
    column. Nothing in the parse can see that. This can: it asks whether the
    gutters land in the same places, and 7 distinct layouts across 8 sources
    is the answer that stops you shipping it.
    """
    o = options_from(options)
    layouts = defaultdict(int)
    per = []

    for i, s in enumerate(sources):
        if profiles is None:
            g = grid(s.get("id", str(i)), s["text"])
            fams = families(g, furniture(g, o)["lines"], o)
        else:
            g, fams = profiles[i]["grid"], profiles[i]["families"]

        found = next((f for f in fams if f["signature"] == family_signature), None)
        if found is None:
            per.append({"id": s.get("id", str(i)), "layout": "(family absent)"})
            continue
        key = ",".join(f"{c['cp_start']}-{c['cp_end']}"
                       for c in gutters(g, found["lines"]))
        per.append({"id": s.get("id", str(i)), "layout": key})
        layouts[key] += 1

    n = len(sources)
    top_key, top_n = max(layouts.items(), key=lambda kv: kv[1], default=("", 0))
    return {"stability": top_n / n if n else 0, "layouts": len(layouts),
            "dominant": top_key, "dominant_sources": top_n, "sources": n,
            "per_source": per}
