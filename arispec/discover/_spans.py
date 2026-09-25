# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Typed spans, line signatures, and shapes (design §6.2, §6.3).

**Two index spaces, never mixed** (§6.1). ARI locates in **codepoints** -- its
``columns`` rule, every recognizer -- so anything that could become part of a
generated rule is measured in codepoints. Provenance back to the file is
measured in **bytes**, because that is what maps to what a person opens. Every
position field says which: ``cp_`` or ``byte_``, never a bare ``start``.

That rule exists because the defect it prevents has shipped twice upstream:
offsets accumulated with a codepoint length, sliced with a codepoint slice,
and reported as a byte offset -- invisible on an ASCII fixture, and on the
first line carrying an ``É`` every later field shifts one place left and the
extracted value is an ordinary-looking shorter string with nothing raised.

Python makes this structurally harder to get wrong than gBASIC did: ``str``
indices *are* codepoints and bytes live in a different type, so mixing the two
is a ``TypeError`` rather than a plausible number. The naming rule is kept
anyway -- the field names are part of the contract, and a caller reading
``cp_start`` should not have to know which language computed it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import date_patterns, money_patterns

__all__ = ["Span", "byte_count", "shape", "signature", "spans", "token_kinds"]


def byte_count(text: str) -> int:
    return len(text.encode("utf-8"))


@dataclass(slots=True)
class Span:
    kind: str
    text: str
    cp_start: int
    cp_length: int
    byte_start: int = 0
    byte_length: int = 0
    alternatives: list = field(default_factory=list)
    needs_dialect: bool = False

    @property
    def cp_end(self) -> int:
        return self.cp_start + self.cp_length


def token_kinds() -> tuple:
    """``page_number`` and ``separator`` are deliberately NOT here.

    Both are conclusions about a line's ROLE, not about a token's shape, and a
    recognizer that decided them would be doing inference inside the
    measurement layer -- the thing §7 warns against when it says a line is not
    furniture merely because it repeats.
    """
    return ("money", "date", "number", "identifier", "word")


def _claims(text: str, patterns, kind: str) -> list:
    out = []
    for p in patterns:
        for m in re.finditer(p["re"], text):
            out.append(Span(kind=kind, text=m.group(0), cp_start=m.start(),
                            cp_length=m.end() - m.start(),
                            needs_dialect=p.get("needs_dialect", False)))
    return out


def _overlaps(a: Span, b: Span) -> bool:
    return a.cp_start < b.cp_end and b.cp_start < a.cp_end


def spans(line_text: str) -> list:
    """The typed spans of one line, ordered by position.

    MOST SPECIFIC FIRST, REJECTING OVERLAPS -- the same rule the money
    recognizer applies, for the same reason: in ``... $6,000.25-`` a specific
    pattern claims ``$6,000.25-`` and a generic one claims ``6,000.25`` INSIDE
    it and further right, so rightmost-wins drops the sign.

    AMBIGUITY IS RECORDED, NOT RESOLVED. ``20260916`` is plausibly a date, an
    identifier and an integer; the losers travel with the winner as
    ``alternatives``, because a premature choice here cannot be revisited by
    anything downstream, and the span that lost is exactly the competing
    hypothesis a human review will be asked about.
    """
    candidates = []
    candidates += _claims(line_text, money_patterns(), "money")
    candidates += _claims(line_text, date_patterns(), "date")
    # An identifier is a run of digits too long to be an ordinary number, or a
    # mixed alphanumeric token. Checked AFTER money and date, so the "16" in
    # "16-OCT-2026" is never a separate identifier.
    candidates += _claims(line_text, [{"re": r"[0-9]{5,}"}], "identifier")
    candidates += _claims(line_text, [{"re": r"-?[0-9]+"}], "number")
    candidates += _claims(line_text, [{"re": r"[A-Za-z][A-Za-z'.#/-]*"}], "word")

    chosen: list = []
    for c in candidates:
        clash = [k for k in chosen if _overlaps(c, k)]
        if not clash:
            chosen.append(c)
        else:
            for w in clash:
                if c.kind not in w.alternatives:
                    w.alternatives.append(c.kind)

    chosen.sort(key=lambda s: s.cp_start)
    for s in chosen:
        s.byte_start = byte_count(line_text[:s.cp_start])
        s.byte_length = byte_count(line_text[:s.cp_end]) - s.byte_start
    return chosen


def _is_rule(t: str) -> bool:
    """A rule line: a run of one punctuation character, possibly with gaps.

    A RULE LINE MAY HAVE GAPS IN IT, and the first version required one
    unbroken run. A column rule under a table heading is several runs separated
    by spaces -- ``----------  ----------------------   ----------`` -- so it
    matched nothing, fell through to the token scan which found no words or
    numbers either, and every such line was profiled as ``<OTHER>``: four per
    source, silently, in a category whose name says the tool does not know.
    """
    if len(t) < 4 or re.fullmatch(r"[-=_*. ]+", t) is None:
        return False
    # At least four punctuation characters, so a line of spaces and one dash is
    # not a rule.
    return sum(1 for c in t if c != " ") >= 4


def signature(line_text: str) -> str:
    """Variable spans become typed placeholders; literals survive verbatim.

    What it KEEPS is token order, and whether a typed value is first or last.
    What it DROPS is exact column positions -- "exact columns are evidence, not
    identity" -- because a signature keyed to columns makes every indent
    variant a different family, which is the drift the tool exists to survive.

    A WORD IS KEPT VERBATIM and a typed span is not, and that asymmetry is the
    point: ``BRANCH TOTAL`` must stay recognisable so it can be proposed as an
    anchor, while ``1,245.00`` must not, or every detail row is its own family.
    """
    t = line_text.strip()
    if not t:
        return "<BLANK>"
    if _is_rule(t):
        return "<RULE>"
    parts = [s.text.upper() if s.kind == "word" else f"<{s.kind.upper()}>"
             for s in spans(line_text)]
    return " ".join(parts) if parts else "<OTHER>"


def shape(line_text: str) -> str:
    """The signature with LITERALS BLANKED TOO -- the shape alone.

    Furniture detection needs this: a page header differs from page to page
    only in its page number and run stamp, so its literal signature is stable,
    but a heading whose wording drifts across sources is recognisable only at
    this level.
    """
    t = line_text.strip()
    if not t:
        return "<BLANK>"
    if _is_rule(t):
        return "<RULE>"
    parts = [f"<{s.kind.upper()}>" for s in spans(line_text)]
    return " ".join(parts) if parts else "<OTHER>"


def words_of(line_text: str) -> str:
    """The WORD tokens of a line, joined.

    A furniture line is one whose LITERALS are stable while its typed values
    may vary: a page header differs from page to page only in its page number
    and run stamp, both typed spans and neither a word.
    """
    return " ".join(s.text.upper() for s in spans(line_text) if s.kind == "word")
