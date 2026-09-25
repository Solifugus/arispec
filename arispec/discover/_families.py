# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Row families (design §7 Phase 4).

§6.3 says a signature "replaces variable spans with typed placeholders while
preserving STABLE LITERALS". The word **stable** is doing all the work, and
ONE LINE CANNOT DECIDE IT.

The first version upstream took every word as a literal, which is the obvious
reading and is wrong in the direction that destroys the result: a member name
is a word, so ``00147454 REYES, YUKI 03/19/2026 947.08`` yielded the signature
``<IDENTIFIER> REYES YUKI <DATE> <MONEY>`` and **every detail row became its
own family** -- 39 families in a report with four. Nothing errored; the profile
was simply a list of every line.

So stability is decided BY THE GROUP, in two passes:

1. group lines by SHAPE -- the kind sequence alone, no literals. Every detail
   row shares one shape by construction.
2. within a group, at each word position, count the distinct words. One word
   holding at least ``minimum_support`` of the group is a LITERAL there;
   anything else is ``<TEXT>``.

That makes ``ACCT`` in a column heading a literal (it is in every member of its
group) and ``REYES`` variable text (it is in a few members of a large one),
from the same rule, with no list of "words that are probably labels".
"""

from __future__ import annotations

from collections import defaultdict

from ._options import options_from
from ._spans import shape, spans

__all__ = ["families"]


def _word_positions(rows, lines) -> dict:
    """For one shape group, the distinct words seen at each word position."""
    tally = defaultdict(lambda: defaultdict(int))
    for ln in lines:
        for i, sp in enumerate(spans(rows[ln - 1].text)):
            if sp.kind == "word":
                tally[i][sp.text.upper()] += 1
    return tally


def _family_signature(rows, lines, o) -> str:
    """The group's signature: dominant words kept, variable ones blanked.

    A SHAPE GROUP OF ONE IS LEFT ALONE rather than having every word blanked: a
    single occurrence is no evidence of variability either, and blanking it
    would throw away the literal a section heading is made of. It is reported
    with ``count: 1`` so a caller can see the distinction.
    """
    n = len(lines)
    wp = _word_positions(rows, lines)
    parts = []
    for i, sp in enumerate(spans(rows[lines[0] - 1].text)):
        if sp.kind != "word":
            parts.append(f"<{sp.kind.upper()}>")
            continue
        if n == 1:
            parts.append(sp.text.upper())
            continue
        seen = wp.get(i, {})
        dom, domn = ("", 0)
        for w, c in seen.items():
            if c > domn:
                dom, domn = w, c
        parts.append(dom if domn / n >= o.minimum_support else "<TEXT>")
    return " ".join(parts) if parts else shape(rows[lines[0] - 1].text)


def families(rows, exclude_lines=(), options=None) -> list:
    """Lines grouped into families, with the MINORITY GROUPS RETAINED.

    "Retain minority clusters rather than forcing all lines into a dominant
    family" is §7's rule, and it is what keeps a totals row -- one line per
    section against dozens of detail rows, and shaped almost exactly like one
    -- from being absorbed into the family it sits under.
    """
    o = options_from(options)
    exclude = set(exclude_lines)
    by_shape = defaultdict(list)

    for r in rows:
        if r.physical_line in exclude or r.blank:
            continue
        # INDENT IS PART OF THE GROUP KEY, and §6.3 already asks for it
        # ("preserve useful features such as indentation"). Without it a column
        # heading `ACCT MEMBER NAME POSTED AMOUNT` and a remark note
        # `reconciled against the general ledger` have the SAME shape -- five
        # words -- so they merge, no word is dominant in the merged group, and
        # both come back as `<TEXT> <TEXT> <TEXT> <TEXT> <TEXT>`: two families
        # lost and the anchor `ACCT` destroyed. Indent is stable within a
        # source and is exactly what separates them.
        by_shape[f"{r.indent}|{shape(r.text)}"].append(r.physical_line)

    out = []
    for sh, lines in by_shape.items():
        out.append({"signature": _family_signature(rows, lines, o),
                    "shape": sh, "count": len(lines),
                    "examples": lines[:3], "lines": lines})
    out.sort(key=lambda f: (-f["count"], f["shape"]))
    return out
