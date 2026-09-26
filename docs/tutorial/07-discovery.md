# 7. Starting from a pile of reports

Someone hands you forty quarters of a report nobody at the company can
explain. Before you write a spec, find out what is in there.

```python
from arispec import discover
from pathlib import Path

report = Path("tests/fixtures/discover/01_branch_activity.rpt").read_text()
p = discover.profile(report)

print(f'{p["physical_lines"]} lines, {p["content_lines"]} of them content')
for fam in p["families"][:6]:
    print(f'  {fam["count"]:>3}x  {fam["signature"]}')
```

```text
61 lines, 40 of them content
   22x  <IDENTIFIER> <TEXT> <TEXT> <DATE> <MONEY>
    3x  <RULE>
    3x  REMARKS
    3x  BRANCH TOTAL <MONEY>
    3x  ACCT MEMBER NAME POSTED AMOUNT
    3x  <TEXT> <TEXT> <TEXT> <TEXT> <TEXT>
```

That is the report's structure, derived from the bytes. Twenty-two detail rows
shaped `<IDENTIFIER> <TEXT> <TEXT> <DATE> <MONEY>`; a column heading whose
words are `ACCT MEMBER NAME POSTED AMOUNT`; two branch headings.

## Literals survive, variable text does not

The interesting question is not "what shapes are there" but **what can I
anchor on**. Ask for the families that kept a word:

```python
for fam in p["families"]:
    literals = [w for w in fam["signature"].split() if not w.startswith("<")]
    if literals:
        print(f'  {fam["count"]:>3}x  {fam["signature"]}')
```

```text
    3x  REMARKS
    3x  BRANCH TOTAL <MONEY>
    3x  ACCT MEMBER NAME POSTED AMOUNT
    2x  BRANCH <NUMBER> <TEXT>
    1x  BRANCH <NUMBER> OLD MILL
```

`ACCT MEMBER NAME POSTED AMOUNT` keeps every word, because every member of
that group has them — it is a column heading, printed identically each time.
`BRANCH <NUMBER> <TEXT>` keeps `BRANCH` and blanks the branch *number* and
*name*, because those differ between occurrences.

Same rule, applied to the group — not a list of "words that are probably
labels". And this list *is* your anchor candidates: `ACCT` and `BRANCH` are
things you can write `right of` in a spec. `RIVERSIDE` is not.

The last row is the edge case, shown rather than hidden. `BRANCH <NUMBER> OLD
MILL` appears **once**, and a single occurrence is no evidence of variability
either — so its words are left alone rather than blanked. If that group grows
to two in the next quarter's file and the branch names differ, `OLD MILL`
becomes `<TEXT>` and it merges with the row above. The count is there so you
can tell the two situations apart.

Getting this wrong is instructive. An earlier version treated every word as a
literal, so a member's surname became part of the signature and **every detail
row became its own family** — 39 families in a report with four. Nothing
errored. The profile was just a list of every line.

## Page furniture, found by position rather than repetition

```python
f = p["furniture"]
print(f'{f["pages"]} pages, by {f["evidence"]}')
print(f'furniture lines: {f["lines"]}')
```

```text
2 pages, by form feeds
furniture lines: [1, 2, 3, 4, 51, 52, 53, 54, 55]
```

Four header lines at the top of each page. Note the rule this follows: *a line
is not furniture merely because it repeats.* A section heading repeats too, and
it must survive into section inference. Furniture is text that recurs **at a
fixed offset from the top of a page** — positional evidence, not just textual.

That is measured, not asserted. Against this corpus's planted answer key —
written by the program that generated the reports, from the values it planted,
never read back out of the text it printed — furniture precision and recall are
both **1.000** over 190 planted lines.

## It refuses when it cannot tell

```python
single = Path("tests/fixtures/teller_totals.rpt").read_text()
print(discover.profile(single)["furniture"]["why"])
```

```text
only one page could be identified, so a header cannot be distinguished from a first heading; furniture needs at least two pages to compare
```

A single-page report's header is indistinguishable from its first section
heading — the same lines, in the same place, appearing once. Calling it
furniture would strip a line that section inference needs; calling it content
would be equally arbitrary. So it says what is missing.

Over twelve structureless noise sources, it claims **zero** furniture lines.
That number matters more than the successes: an earlier version accepted a
single recurring line shape as a page period and invented pages in 14 of 18
single-page reports.

## Across a corpus

One report cannot tell you whether a constant is really constant.

```python
sources = [{"id": f"q{i}", "text": Path(f"tests/fixtures/discover/0{i}_branch_activity.rpt").read_text()}
           for i in range(1, 10)]
c = discover.profile_corpus(sources)

print(f'{c["sources"]} sources')
for e in c["shared"][:3]:
    print(f'  {e["sources"]}/{c["sources"]}  {e["signature"]}')
print(f'\nonly one source has: {len(c["only_one_source"])} signatures')
print(c["warning"][:64])
```

```text
9 sources
  9/9  <IDENTIFIER> <TEXT> <TEXT> <DATE> <MONEY>
  9/9  <RULE>
  8/9  BRANCH <NUMBER> <TEXT>

only one source has: 5 signatures
support over 9 sources can only take 9 distinct values, so `mini
```

Support is counted in **sources**, not in lines: a signature appearing 400
times in one file and never again is an accident of that file, and one
appearing three times in every file is structure.

And note the warning. With nine sources, support can only take nine values, so
a threshold of 0.80 and one of 0.95 are the same threshold. It says so rather
than reporting a figure that cannot mean what it looks like.

## It proposes nothing, deliberately

`discover` measures. It does not generate a spec.

That is design principle 1 — *measurement before interpretation*. A profiling
layer that also guessed would make the guess impossible to evaluate separately
from the measurement it rests on, and when the proposal came out wrong you
would not know which half to fix.

Specification generation is the next phase. For now the workflow is: profile
the corpus, read the families, write the anchors it found, and check your work
with [`trace`](06-trace.md).

## `import arispec` does not pay for this

```python
import subprocess, sys
out = subprocess.run([sys.executable, "-c",
    "import arispec, sys; print('arispec.discover' in sys.modules)"],
    capture_output=True, text=True)
print(out.stdout.strip())
```

```text
False
```

Clustering and inference stay out of the deterministic parser. A production
job with a known spec pays none of this — which is why discovery is a
submodule you import on purpose.
