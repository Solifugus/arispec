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
import json

truth = json.loads(Path("tests/fixtures/discover/truth.json").read_text())
recs = truth["sources"][:8]
sources = [{"id": r["id"],
            "text": Path("tests/fixtures/discover") .joinpath(Path(r["file"]).name).read_text()}
           for r in recs]

c = discover.profile_corpus(sources)

print(f'{c["sources"]} sources')
for e in c["shared"][:3]:
    print(f'  {e["sources"]}/{c["sources"]}  {e["signature"]}')
print(f'\nonly one source has: {len(c["only_one_source"])} signatures')
print(c["warning"][:64])
```

```text
8 sources
  8/8  <IDENTIFIER> <TEXT> <TEXT> <DATE> <MONEY>
  8/8  <RULE>
  7/8  BRANCH <NUMBER> <TEXT>

only one source has: 6 signatures
support over 8 sources can only take 8 distinct values, so `mini
```

Support is counted in **sources**, not in lines: a signature appearing 400
times in one file and never again is an accident of that file, and one
appearing three times in every file is structure.

And note the warning. With nine sources, support can only take nine values, so
a threshold of 0.80 and one of 0.95 are the same threshold. It says so rather
than reporting a figure that cannot mean what it looks like.

## Proposing a spec

`profile` measures and proposes nothing — measurement before interpretation,
so a guess can always be evaluated separately from the measurement it rests
on. `infer` is where the guessing starts, and it shows its working.

```python
p = discover.infer(sources)
print(p["spec"])
```

```text
' Generated by arispec.discover.
' Detail family: <IDENTIFIER> <TEXT> <TEXT> <DATE> <MONEY>
'   45 lines, examples at 9, 10, 11
' Field names taken from the column heading above it.
section report:
    section rows repeats starts(/^[ ]*[0-9]{5,}/):
        ' the only date column on the row
        field posted: first date as date
        ' the only money column on the row
        field amount: first money as money
```

Two fields, each with the evidence for its locator written into the spec as a
comment — because you will maintain that spec afterwards **without** this
library, and the reasoning cannot live in a report that gets thrown away.

## What it will not reach, it asks about

```python
for q in p["questions"]:
    print(f'{q["field"]}: {q["kind"]} at {q["cp_start"]}, e.g. {q["example"]!r}')
    for opt in q["options"]:
        print(f'   - {opt}')
```

```text
acct_no: identifier at 4, e.g. '00141935'
   - enable allow_fixed_columns and accept a positional rule
   - supply an anchor this adapter cannot see
   - leave the field out
member_name: text at 16, e.g. 'CHAUDHRY, MARGARET'
   - enable allow_fixed_columns and accept a positional rule
   - supply an anchor this adapter cannot see
   - leave the field out
```

A detail row carries no literal anchors, so `first`/`last` reaches the money
and the date and **nothing else**. That limit is the report's, not the tool's,
and reporting it is the honest profile.

Notice what it did *not* do: propose `columns 4-11` for the account number.

## Why a column is a question and not an answer

Turn positional rules on and the proposal looks strictly better:

```python
loose = discover.infer(sources, {"allow_fixed_columns": True})
v = loose["validation"]
print({f["name"]: f["locator"] for f in loose["fields"]})
print(f'source_coverage={v["source_coverage"]:.2f}  rows={v["rows"]}  unknown_rate={v["unknown_rate"]:.3f}')
```

```text
{'acct_no': 'columns 4-11', 'member_name': 'columns 16-34', 'posted': 'first date', 'amount': 'first money'}
source_coverage=1.00  rows=230  unknown_rate=0.000
```

Four fields instead of two, every source parsed, every row extracted, nothing
unknown. By every number the parse can produce, it is perfect.

Now score it against the corpus's **planted** answer key — the values the
generator planted, not values read back out of the text it printed:

```python
import arispec
from decimal import Decimal

for name, spec in (("first money  ", p["spec"]), ("columns 4-11 ", loose["spec"])):
    key = "amount" if "first money" in name else "acct_no"
    hit = total = 0
    for rec, s in zip(recs, sources):
        rows = arispec.parse(s["text"], spec).value["rows"]
        if key == "amount":
            want = [Decimal(a["amount_cents"]) / 100
                    for b in rec["branches"] for a in b["accounts"]]
            got = [r["amount"] for r in rows]
            hit += sum(1 for w in want if w in got); total += len(want)
        else:
            want = {a["account"] for b in rec["branches"] for a in b["accounts"]}
            got = {str(r["acct_no"]) for r in rows}
            hit += len(want & got); total += len(want)
    print(f"{name}: {hit}/{total} planted values recovered")
```

```text
first money  : 230/230 planted values recovered
columns 4-11 : 147/230 planted values recovered
```

A third of them are wrong, and **nothing in the parse can tell you.** The
account numbers it returns are ordinary-looking account numbers — from the
wrong column, with the leading zeros gone, because the corpus varies its table
indent and a `columns` rule cannot follow.

## The measure that needs no answer key

You will not usually have a planted answer key. This is what you have instead:

```python
st = loose["anchor_stability"]
print(f'stability {st["stability"]:.2f} over {st["layouts"]} distinct layouts '
      f'in {st["sources"]} sources')
```

```text
stability 0.25 over 7 distinct layouts in 8 sources
```

It asks one question — *is this family's column structure the same in every
source?* — and needs nothing but the corpus. Seven different layouts across
eight files is the answer that stops you shipping a positional spec, and it is
the only number in the scorecard that moved.

## It refuses on text with no structure

```python
nulls = [{"id": f.stem, "text": f.read_text()}
         for f in sorted(Path("tests/fixtures/discover/null").glob("*.rpt"))]
n = discover.infer(nulls)
print(n["ok"])
print(n["why"])
```

```text
False
no row family is both DOMINANT within a source (at least 15% of its content lines) and present in at least 80% of the 12 sources, so there is no repeating structure to write a specification against
```

A family has to be **dominant within its source**, not merely recurring across
the corpus. An earlier version required only recurrence and proposed a
specification for pure noise: a `<MONEY> <DATE>` family of *one line*,
appearing in 11 of 12 structureless sources by chance, because a two-token
shape recurs whenever tokens are drawn at random.

## Holding sources back

```python
h = discover.infer(sources, {"holdout": 3})
print(f'trained on {h["trained_on"]}, held {h["holdout"]["sources"]}')
print(f'train rows={h["validation"]["rows"]}  held rows={h["holdout"]["rows"]}')
```

```text
trained on 5, held 3
train rows=118  held rows=112
```

The last *n* sources are reserved from inference and scored separately —
reserved from the end rather than at random, so the same ordered corpus gives
the same proposal and no seed nobody passed decides your result.

Its purpose is not reassurance. A spec inferred from a corpus and scored on
that same corpus is scored on the data that shaped it, and the two numbers only
part company when something has been fitted to the training set — which is
exactly when you need to know.

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
