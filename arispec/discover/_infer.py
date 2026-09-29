# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Phase 1: propose a specification, and say what it could not reach.

Phase 0 measures. This is where the tool starts *guessing*, and the whole
design of it is about making the guesses inspectable:

* every field carries **why** it got the locator it got, as a comment in the
  generated spec, because a person has to maintain that spec afterwards
  without this library;
* what cannot be located anchor-relatively becomes a **question with its
  options**, not a column;
* candidates that were considered and rejected are reported as alternatives.
"""

from __future__ import annotations

from collections import defaultdict

from ._options import options_from
from ._spans import shape, spans

__all__ = ["columns_of", "gutters", "infer_fields", "spec_text"]


def gutters(rows, lines) -> list:
    """The columns of a fixed-width family, bounded by its GUTTERS.

    Not by the extent of the values that happened to be in it. The first
    version upstream took each span's min..max across the family, and that is
    wrong twice over, both silently:

    * ``columns 4-11`` on an account column starting at 2 returned ``147454``
      -- the leading zeros gone, a number where the source had a code;
    * a member name came back ``YES, YUKI``, because the widest observed
      surname still did not reach the column's real right edge.

    A column is bounded by whitespace present on **every** row of the family,
    which is what a person reads by eye and what the report generator actually
    emitted.

    **A run of one space is not a gutter.** ``REYES, YUKI`` has one inside a
    single value, and the position of that space *moves* with the surname's
    length, which is precisely why the all-rows test settles it. That also
    merges spans correctly with no rule about merging: a surname and forename
    one space apart fall in one column and become one field, while an account
    and a name four spaces apart stay two.
    """
    texts = [rows[ln - 1].text for ln in lines]
    width = max((len(t) for t in texts), default=0)

    # A position is a gutter if EVERY row has a space there, or ends before it.
    is_gap = [all(i >= len(t) or t[i] == " " for t in texts) for i in range(width)]

    cols, start, i = [], -1, 0
    while i <= width:
        gap = is_gap[i] if i < width else True
        run = 0
        if gap:
            j = i
            while j < width and is_gap[j]:
                run += 1
                j += 1
        if gap and run >= 2:
            if start >= 0:
                cols.append({"cp_start": start, "cp_end": i - 1})
                start = -1
            i += run
        else:
            if i < width and start < 0:
                start = i
            i += 1
    if start >= 0:
        cols.append({"cp_start": start, "cp_end": width - 1})
    return cols


def columns_of(cols, cp: int) -> int:
    for i, c in enumerate(cols):
        if c["cp_start"] <= cp <= c["cp_end"]:
            return i
    return -1


def _kind_locator(kind: str) -> str:
    """Which kinds ``first``/``last`` can reach at all.

    ``identifier`` is deliberately absent. ``first integer`` on ``00147454``
    answers 147454 -- **leading zeros gone**, and a number where the source had
    a code. An account number that reads back shorter is exactly the
    ordinary-looking wrong value this library exists to refuse.
    """
    return kind if kind in ("money", "date") else ""


def _heading_for(rows, fam, furniture_lines) -> str:
    """The heading line for a family: the nearest line above its first member
    that is a line of words and is not part of this family.

    A heading is **all words**. A line carrying money or a date is a data row,
    not a caption for one.
    """
    furniture = set(furniture_lines)
    ln = fam["lines"][0] - 1
    seen = 0
    while ln >= 1 and seen <= 3:
        r = rows[ln - 1]
        if ln not in furniture and not r.blank and shape(r.text) != fam["shape"].split("|", 1)[-1]:
            from ._spans import _is_rule
            if not _is_rule(r.text.strip()):
                if all(sp.kind == "word" for sp in spans(r.text)):
                    return r.text
                return ""
        ln -= 1
        seen += 1
    return ""


def _name_from_heading(heading: str, cp_start: int, cp_length: int) -> str:
    """Name a field from the heading word that OVERLAPS its column range.

    Overlap, not order. Matching the nth heading word to the nth field assumes
    both have the same count, and a two-word heading over a one-value column
    breaks that immediately.
    """
    if not heading:
        return ""
    lo, hi = cp_start, cp_start + cp_length
    parts = [sp.text.lower() for sp in spans(heading)
             if sp.cp_start < hi and lo < sp.cp_end]
    return "_".join(parts)


def _safe_name(name: str, used, idx: int) -> str:
    base = (name or f"field_{idx + 1}").replace(" ", "_")
    return f"{base}_{idx + 1}" if base in used else base


def infer_fields(rows, fam, furniture_lines=(), options=None) -> dict:
    """The fields of one family: ONE COLUMN IS ONE FIELD, with its evidence."""
    o = options_from(options)
    heading = _heading_for(rows, fam, furniture_lines)
    cols = gutters(rows, fam["lines"])

    # What kind lives in each column, decided across the WHOLE family rather
    # than from one row: a column that is money on most rows and text on one is
    # not a money column, it is a column with a problem in it.
    kinds, consistency = [], []
    for ci in range(len(cols)):
        tally = defaultdict(int)
        for ln in fam["lines"]:
            here = [sp.kind for sp in spans(rows[ln - 1].text)
                    if columns_of(cols, sp.cp_start) == ci]
            tally[here[0] if len(here) == 1 else "text"] += 1
        top_kind, top_n = max(tally.items(), key=lambda kv: kv[1])
        kinds.append(top_kind)
        consistency.append(top_n / len(fam["lines"]))

    # How many columns carry each kind decides whether first/last is unambiguous.
    counts = defaultdict(int)
    for k in kinds:
        counts[k] += 1

    fields, questions, used, seen = [], [], [], defaultdict(int)
    for ci, col in enumerate(cols):
        k = kinds[ci]
        seen[k] += 1
        nth = seen[k]
        name = _safe_name(_name_from_heading(heading, col["cp_start"],
                                             col["cp_end"] - col["cp_start"] + 1),
                          used, ci)
        used.append(name)
        sample = rows[fam["lines"][0] - 1].text[col["cp_start"]:col["cp_end"] + 1].strip()

        ty = _kind_locator(k)
        loc = why = ""
        positional = False
        if ty:
            if counts[k] == 1:
                loc, why = f"first {ty}", f"the only {ty} column on the row"
            elif nth == 1:
                loc, why = f"first {ty}", f"the first of {counts[k]} {ty} columns"
            elif nth == counts[k]:
                loc, why = f"last {ty}", f"the last of {counts[k]} {ty} columns"

        if not loc:
            if o.allow_fixed_columns:
                loc = f"columns {col['cp_start']}-{col['cp_end']}"
                why = (f"no anchor-relative locator reaches a {k} column, so this "
                       "is POSITIONAL and breaks if the report drifts")
                positional = True
            else:
                # A QUESTION, not a column. A positional rule here recovered
                # 147 of 230 planted values with source_coverage 1.0 and an
                # unknown_rate of 0 -- every extracted value an ordinary-looking
                # account number from the wrong column, because the corpus
                # varies its table indent and a `columns` rule cannot follow.
                questions.append({
                    "field": name, "kind": k,
                    "cp_start": col["cp_start"],
                    "cp_length": col["cp_end"] - col["cp_start"] + 1,
                    "example": sample,
                    "why": (f"a {k} column at {col['cp_start']}-{col['cp_end']} "
                            "that no anchor-relative rule can reach: the row "
                            "carries no literal to anchor to, and first/last "
                            "reaches only money and date."),
                    "options": ["enable allow_fixed_columns and accept a positional rule",
                                "supply an anchor this adapter cannot see",
                                "leave the field out"]})
                continue

        as_type = f" as {k}" if k in ("money", "date") else ""
        fields.append({"name": name, "locator": loc, "type": k,
                       "as_type": as_type, "positional": positional,
                       "cp_start": col["cp_start"],
                       "cp_length": col["cp_end"] - col["cp_start"] + 1,
                       "example": sample, "consistency": consistency[ci],
                       "why": why})

    return {"fields": fields, "questions": questions, "heading": heading,
            "columns": cols}


_FIRST_SPAN = {"<IDENTIFIER>": r"[0-9]{5,}", "<MONEY>": r"[0-9,]+\.[0-9]{2}",
               "<DATE>": "[0-9]", "<NUMBER>": "[0-9]"}


def _start_regex(fam) -> str:
    """A ``starts(...)`` pattern built from what the family's first span IS,
    rather than from the literal text of one row."""
    sig = fam["signature"]
    for prefix, rx in _FIRST_SPAN.items():
        if sig.startswith(prefix):
            return "^[ ]*" + rx
    first = sig.split(" ", 1)[0]
    if first.startswith("<"):
        return "^[ ]*[A-Za-z]"
    return "^[ ]*" + "".join("\\" + c if c in ".^$*+?()[]{}|\\/" else c
                             for c in first)


def spec_text(fam, inferred, options=None) -> str:
    """The generated specification, with its evidence in the comments.

    A person has to maintain this afterwards **without** this library, so the
    reasoning cannot live in a report that gets thrown away.
    """
    options_from(options)
    out = ["' Generated by arispec.discover.",
           f"' Detail family: {fam['signature']}",
           f"'   {fam['count']} lines, examples at "
           + ", ".join(str(x) for x in fam["examples"])]
    out.append("' Field names taken from the column heading above it."
               if inferred["heading"] else
               "' NO column heading was found: field names are positional.")
    out.append("section report:")
    out.append(f"    section rows repeats starts(/{_start_regex(fam)}/):")
    for f in inferred["fields"]:
        out.append(f"        ' {f['why']}")
        out.append(f"        field {f['name']}: {f['locator']}{f['as_type']}")
    return "\n".join(out)
