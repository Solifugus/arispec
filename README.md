# arispec

Anchor-relative identification: declarative extraction from irregular text and grids

Declarative extraction of fields from irregular, semi-structured text: legacy
print reports, mainframe spool, teller totals, and the 2D grids that arrive as
spreadsheets. **No dependencies.**

## Why not a column, and why not a heading

Measured on two real-shaped teller reports:

| fixture | `Amount` heading ends at | value rows end at |
|---|---|---|
| `teller_totals.rpt` | col 74 | col 78, 78, **79** |
| `teller_totals_generated.rpt` | col 68 | col 79 |

The heading is adrift of its own data by four columns in one file and eleven
in the other, because headings and data drift apart over decades of separate
edits. And the row that runs a column further is the negative one —
`$6,000.25-` — because a trailing minus is appended *after* right-justification,
so negatives are one column wider than the positives above them. Pin that
column to 78 and you truncate the sign; pin it to 79 and every positive
carries a leading space.

So neither the heading nor the column can find the amount. What works is
**bounding by type**: *the last money-shaped token on this row*. `as <type>`
does not merely convert a value — it **delimits** it. That is the central idea.

## A spec

```python
import arispec

spec = r'''
page:
    break: formfeed
    drop: 2

section report:
    section tellers repeats starts(/^Teller: /):
        field name:       between "Teller:" and "Teller #:"
        field teller_no:  right of "Teller #:" as integer
        field beginning:  right of "Beginning Cash" as money

        section detail starts(/^GL\s+Tran #/) ends(/^\s*$/):
            rows:
                field gl:     columns 0-24
                field amount: last money
'''

r = arispec.parse(report_text, spec)
for t in r.value["tellers"]:
    print(t["teller_no"], t["beginning"])
```

Fields are anchored by **label**, not by row offset, and that is the case that
matters: in the fixture, teller 386 prints Beginning/Ending/Total while tellers
261 and 262 print Beginning/Total/Ending. An offset-based read returns the
wrong number for two of the three and reports nothing wrong.

A spec is **data** — a short indented document you can store in a database,
generate, diff and review. Not a chain of method calls that exists only in
source.

## Locators

| locator | meaning |
|---|---|
| `right of <pat>` | from just after the match to the end of the line |
| `left of <pat>` | from the start of the line to just before the match |
| `between <pat> and <pat>` | the span between two matches on one line |
| `columns <a>-<b>` | a fixed span, where an area genuinely is columnar |
| `first <type>` / `last <type>` | the first/last token of that type on the line |
| `down <n> of <locator>` | apply the locator `n` lines below the anchor |
| `up <n> of <locator>` | the same, upward |
| `<locator> within columns <a>-<b>` | restrict the search to a column range |

A distance may be exact (`1`), a range (`1-3`), open (`3-`, `-8`) or `flush`.
A range is not a convenience: in the delinquency fixture the gap between
`REMARKS:` and its note is 1, 2, 2 and 3 lines across four branches, because
the generator emits a varying number of blank lines — which is what real
reports do. An exact distance matches one branch and misses the rest, silently.

## It refuses rather than guesses

A cell that matches no rule becomes `UNKNOWN` **for that cell alone** — never
a silent zero, and never a raise that sinks a 100,000-line import because one
teller's bait cash was keyed `$8,0000`.

```python
r.diagnostics   # every unreadable cell: path, reason, physical line
```

`03/04/2026` is 3 April and 4 March and nothing in the token says which, so it
is `ambiguous-date` until a spec declares `using date: dmy`. `27/12/2026`
needs no declaration — 27 cannot be a month. And a declaration is
**authoritative, not a hint**: under `using date: mdy`, `27/12/2026` is
invalid, because silently re-reading it day-first would be guessing against an
explicit statement.

## What a spec missed

```python
t = arispec.trace(report, spec)
for u in t.unclaimed:
    print(u["line"], u["text"])      # text no rule accounts for
```

`content_coverage` is **not a grade** — a report carrying commentary, totals a
spec does not read, or rule lines can never reach 1.0 and should not. It is
useful as a *difference*: between two candidate specs over one corpus, or one
spec before and after a field is added. Blanks are not counted; a print image
is mostly column padding, and counting it would put every spec near 1.0.

## Frames

A `rows:` block emits columns of equal length, which `polars.DataFrame` and
`pandas.DataFrame` both take directly — with no dependency on either from here.

```python
import polars as pl
pl.DataFrame(r.value["tellers"][0]["detail"]["rows"])
```

## Install

```bash
pip install arispec
```

Python 3.11+. No dependencies, and none planned.

## Tests

```bash
PYTHONPATH=. python -m unittest discover -s tests
```

58 tests, no network access, fixtures included in the sdist.

## Discovery: measure a corpus, propose nothing

```python
from arispec import discover

p = discover.profile(report_text)
p["furniture"]["lines"]   # physical line numbers that are page furniture
p["families"]             # recurring line shapes, most frequent first

c = discover.profile_corpus([{"id": "q1", "text": ...}, ...])
c["shared"]               # signatures most sources carry
c["only_one_source"]      # and those only one does
```

Give it forty quarters of the same report and it tells you where the page
furniture is, which line shapes recur, and which literals are stable enough to
anchor on. It **proposes nothing**, deliberately: a profiling layer that also
guessed would make the guess impossible to evaluate separately from the
measurement it rests on. Specification generation is the next phase.

Measured against a **planted** answer key — written by the program that wrote
the reports, from the values it planted, never read back out of the text it
printed — over 24 branch-activity reports across nine drift axes:

| | result |
|---|---|
| furniture precision / recall | **1.000 / 1.000** (190 planted, 190 claimed) |
| single-page sources | all 4 **refuse with a reason** rather than guess |
| 12 structureless noise sources | **0** furniture lines claimed |

`import arispec` never pulls this in: the deterministic parser stays free of
clustering and inference, so a caller with a known specification pays none of
it.

## Status

0.1.0. The spec parser, the runtime, `trace`, and discovery Phase 0
(profiling) are implemented — 93 tests over six fixtures plus a 24-source
corpus with a planted answer key. Specification *generation* from a profile is
the next phase.

Ported from gBASIC's `stdlib/ari.bas`, with which it shares its spec language
and its measured behaviour — see
[the roadmap](https://github.com/Solifugus/etl-tools/blob/master/docs/roadmap.md).

Apache-2.0. Copyright 2026 Matthew C. Tedder.
