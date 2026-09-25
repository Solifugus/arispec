# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Page furniture (design §7 Phase 3).

> "A line is not furniture merely because it repeats. A repeated section
> heading inside the report body must remain available to section inference.
> Furniture classification therefore requires POSITIONAL evidence in addition
> to textual recurrence."

That rule decides the whole algorithm. Furniture is found by PERIOD: lines
whose shape recurs at a constant interval, at a stable offset within it. A
heading that repeats irregularly through the body fails the interval test and
survives into section inference, which is what must happen.

Four things were wrong on the first working version upstream, and **every one
produced a plausible profile rather than an error**. Each rule below names the
one it fixes, because none of them is obvious and a later reader will be
tempted to simplify it back.
"""

from __future__ import annotations

from ._options import options_from
from ._spans import shape, words_of

__all__ = ["furniture", "page_starts"]

_MAX_BLOCK = 8          # no page header is taller than this


def _shapes_of(rows) -> list:
    return [shape(r.text) for r in rows]


def _words_at(rows, n, starts, off) -> list:
    return [words_of(rows[st - 1 + off].text)
            for st in starts if st - 1 + off < n]


def _block_height(sh, n, base, period, support):
    """How many consecutive leading offsets agree across the implied pages.

    THE BLOCK IS PAGE ONE'S LEADING LINES, CONFIRMED BY THE OTHER PAGES, and
    the first version had that direction backwards: it took the dominant shape
    at each offset across all pages, which lets a block be defined by pages
    2..5 while page 1 disagrees. Measured, that is exactly what happened -- a
    source with one real page locked onto a 14-line period whose "header" was a
    detail-row shape agreeing on four of five imagined pages, with the actual
    first line the odd one out. A page header appears on page one; if page one
    does not have it, it is not a header.
    """
    pages = list(range(base, n, period))
    if len(pages) < 2:
        return 0, len(pages)
    height = 0
    for off in range(_MAX_BLOCK):
        if base + off >= n:
            break
        want = sh[base + off]
        seen = [st + off for st in pages if st + off < n]
        if len(seen) < 2:
            break
        if sum(1 for i in seen if sh[i] == want) / len(seen) < support:
            break
        # A BLOCK THAT BEGINS WITH A BLANK IS NOT A HEADER: blank lines agree
        # with each other for free.
        if off == 0 and want == "<BLANK>":
            return 0, len(pages)
        height += 1
    return height, len(pages)


def page_starts(rows, options=None) -> dict:
    """Where each page begins.

    Reported as page STARTS rather than as a period, and that is not a
    presentation choice: a two-page report has exactly ONE page break, so a
    period needs two gaps and cannot be had at all. The first draft required
    two and found nothing on more than half the corpus -- reports short enough
    to be two pages, which is most real ones.
    """
    o = options_from(options)

    ffs = [r for r in rows if r.form_feed]
    if ffs:
        # WITH FORM FEEDS NOTHING IS INFERRED: the breaks are stated.
        #
        # A FEED THAT SHARES ITS LINE WITH CONTENT *STARTS* THAT PAGE; a feed
        # alone on its line ENDS the page above it. gBASIC treats every feed
        # as an ending and adds one, which disagrees with `ari`'s own engine --
        # there the feed line IS the break, and `drop: 2` removes it and the
        # next. `ari_spec_language.md` §2 documents the shared line as normal
        # ("the form feed may sit at the start of a line that also carries the
        # header, which is what the generated fixture does").
        #
        # MEASURED on that very fixture: feeds at 1, 67, 133, 199 produced
        # starts [1, 2, 68, 134, 200] -- FIVE starts for a four-page document,
        # the second of them a blank line under page one's header. Offset 0
        # then compared the header against four blanks, agreed 1 in 5, and the
        # whole header block was lost: furniture came back as the four feed
        # lines alone, where ARI's own spec for the file says `drop: 2`.
        #
        # The discovery corpus cannot see this -- every source there puts its
        # feed on an otherwise blank line -- which is the same shape of
        # blindness as an all-ASCII corpus hiding a byte offset.
        starts = [1]
        for r in ffs:
            ln = r.physical_line if r.text.strip() else r.physical_line + 1
            if ln <= len(rows) and ln not in starts:
                starts.append(ln)
        return {"starts": sorted(starts), "evidence": "form feeds", "height": 0}

    sh = _shapes_of(rows)
    n = len(sh)
    best_h = best_p = 0

    # PAGINATION STARTS AT THE TOP OF THE FILE. Only base 0 is considered, and
    # that one constraint is what separates a page header from a SECTION block.
    # Measured with any base allowed, the search locks onto the branch block --
    # heading, blank, column heading, rule, details, total -- which genuinely
    # repeats at a nearly constant interval and is a perfectly good repeating
    # block. It claimed up to 24 furniture lines on single-page sources whose
    # header appears exactly once.
    #
    # The period may be nearly the whole document: a 55-line report with a
    # 50-line page has two pages, the second five lines long. The first draft
    # searched only to n/2 -- which assumes two FULL pages -- and found no
    # period at all on every source whose second page is a short tail, which is
    # most of them. A period leaving too little to compare is rejected by the
    # height test rather than by the range.
    for period in range(10, max(10, n - 1)):
        height, _pages = _block_height(sh, n, 0, period, o.minimum_support)
        # A BLOCK, not a line: two consecutive agreeing offsets at minimum.
        if height >= 2 and height > best_h:
            best_h, best_p = height, period

    if best_h >= 2:
        return {"starts": list(range(1, n + 1, best_p)),
                "evidence": f"a {best_h}-line block repeating every {best_p} lines",
                "height": best_h}
    return {"starts": [1], "evidence": "none", "height": 0}


def furniture(rows, options=None) -> dict:
    """Lines whose shape is stable at a fixed offset from the top of a page.

    ``lines`` holds 1-based physical line numbers, which is what an answer key
    records too, so precision and recall are computable against it rather than
    merely reported.
    """
    o = options_from(options)
    ps = page_starts(rows, o)
    pages = len(ps["starts"])

    # A FORM FEED IS FURNITURE BY DEFINITION, not by inference. It is a page
    # break character: nothing else it could be, and no support threshold
    # applies. Missing this cost exactly one line per break on every paginated
    # source -- 8 of 9 found, which reads like a rounding error and is actually
    # a whole category.
    out = [r.physical_line for r in rows if r.form_feed]
    offsets = []

    if pages < 2:
        # ONE PAGE IS NOT EVIDENCE OF FURNITURE, and this is a REFUSAL rather
        # than an empty result. A single-page report's header is
        # indistinguishable from its first heading -- the same lines, in the
        # same place, appearing once -- so calling it furniture would strip a
        # line section inference needs, and calling it content would be equally
        # arbitrary. The honest answer names what is missing.
        return {"lines": out, "pages": pages, "evidence": ps["evidence"],
                "offsets": offsets,
                "why": "only one page could be identified, so a header cannot "
                       "be distinguished from a first heading; furniture needs "
                       "at least two pages to compare"}

    sh = _shapes_of(rows)
    n = len(rows)
    first = ps["starts"][0] - 1

    # FURNITURE IS THE CONTIGUOUS BLOCK FROM THE TOP OF THE PAGE, not any
    # offset in a window that happens to agree. Measured with a fixed 8-line
    # window, one source claimed 15 lines where 9 were planted; the extras were
    # offsets where both pages happened to carry a detail row, and
    # `<IDENTIFIER> <TEXT> <TEXT> <DATE> <MONEY>` is the commonest shape in the
    # document, so agreement there is nearly free. A header ENDS somewhere, and
    # the first offset that disagrees is where.
    for off in range(_MAX_BLOCK):
        if first + off >= n:
            break
        want = sh[first + off]
        seen = [st - 1 + off for st in ps["starts"] if st - 1 + off < n]
        if len(seen) < 2:
            break
        agree = [i for i in seen if sh[i] == want]
        if len(agree) / len(seen) < o.minimum_support:
            break
        if off == 0 and want == "<BLANK>":
            break

        # THE LITERALS MUST AGREE TOO, not only the shapes. Measured with shape
        # agreement alone, two sources claimed 17 furniture lines where 9 were
        # planted: the break fell just before a branch heading, so page 2 opened
        # with the same eight SHAPES as page 1 and the whole window agreed. The
        # branch NAME differs between them, which is a word, so requiring words
        # to agree trims the block back to the four lines that are the header.
        wants = _words_at(rows, n, ps["starts"], off)
        if not wants or sum(1 for w in wants if w == wants[0]) / len(wants) < o.minimum_support:
            break

        offsets.append({"offset": off, "shape": want, "words": wants[0],
                        "seen": len(agree), "pages": len(seen)})
        for st in ps["starts"]:
            i = st - 1 + off
            if i < n and sh[i] == want and st + off not in out:
                out.append(st + off)

    return {"lines": sorted(out), "pages": pages, "evidence": ps["evidence"],
            "offsets": offsets, "why": ""}
