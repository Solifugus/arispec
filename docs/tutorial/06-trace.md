# 6. What did my spec miss?

A spec that quietly stops matching is the failure mode that costs money. The
load runs, the row count looks plausible, and one field has been `UNKNOWN`
since the vendor changed a heading in March.

`trace` answers the question a diff cannot: **what in this report does my
specification not account for?**

```python
import arispec
from pathlib import Path

report = Path("tests/fixtures/teller_totals.rpt").read_text()

spec = r"""
page:
    break: /^[0-9]{2}\/[0-9]{2}\/[0-9]{4} .*Page [0-9]+$/
    drop: 2

section report starts(/^Branch: /):
    field branch: right of "Branch:" as integer

    section tellers repeats starts(/^Teller: /):
        field teller_no: right of "Teller #:" as integer
        field beginning: right of "Beginning Cash" as money
"""

t = arispec.trace(report, spec)
print(f"claimed {t.claimed_chars} of {t.content_chars} non-blank characters")

biggest = sorted(t.unclaimed, key=lambda u: -u["chars"])[:4]
for u in biggest:
    print(f'  line {u["line"]:>3}: {u["text"][:46]!r}')
```

```text
claimed 130 of 1906 non-blank characters
  line   4: '=============================================='
  line   6: '----------------------------------------------'
  line  10: '----------------------------------------------'
  line  17: '----------------------------------------------'
```

## Read `unclaimed`, not the percentage

The four biggest unclaimed runs here are rule lines — decoration. That is the
normal result and it is telling you the spec is fine so far. What you are
looking for is a run that is *data*:

```python
interesting = [u for u in t.unclaimed
               if any(c.isdigit() for c in u["text"]) and u["chars"] > 8]
for u in sorted(interesting, key=lambda u: -u["chars"])[:4]:
    print(f'  line {u["line"]:>3}: {u["text"][:46]!r}')
```

```text
  line  13: 'Check Deposit CHK#4211   001002345    11      '
  line  24: 'Check Deposit CHK#5621   001002345    11      '
  line  37: 'Check Deposit CHK#3467   001002345    11      '
  line  14: 'ACH Transfer             001004326    13      '
```

Those are the transaction detail rows — an entire table this spec never
declared, repeated once per teller. On a report you have never seen, that list
*is* your to-do list, ordered by how much text each run accounts for.

## `content_coverage` is not a grade

```python
print(f"{t.content_coverage:.2f}")
```

```text
0.07
```

Seven percent, and there is nothing wrong with this spec — it reads four
fields out of a report that also carries three transaction tables, three
closing grids and a page of rule lines. **A report can never reach 1.0 and
should not.** Commentary, totals you do not need and decoration are all
content that no correct spec claims.

The number is useful as a **difference**, not as a score:

- the same spec over two quarters of the same report — a drop means the layout
  moved;
- two candidate specs over one corpus — the higher one explains more;
- before and after adding a field — did it claim what you thought?

Two specs are only comparable when they strip the same furniture, because
coverage's denominator is the text the `page:` directive *kept*.

Both fractions carry their own definition, so nobody has to remember:

```python
print(t.content_coverage_is[:78])
```

```text
claimed non-blank characters / non-blank characters on the lines the page: dir
```

## Blanks are not content

A print image is mostly column padding. If padding counted, every spec would
score near 1.0 — the flattering and useless direction. The denominator is
non-blank characters on non-furniture lines, so a page header costs a spec
nothing and a wall of spaces does not flatter it.

## An anchor is a claim

```python
kinds = {}
for c in t.claims:
    kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
print(kinds)
```

```text
{'section': 4, 'field': 7, 'anchor': 7}
```

Three kinds. A **field** claim is a value you extracted. An **anchor** claim is
a literal your spec named — `Beginning Cash` — and a **section** claim is the
heading that located a section.

Anchors count as explained text on purpose. A literal you wrote is the most
spec-relevant text on the page; leaving it out would put it in `unclaimed` and
depress coverage by exactly the labels you authored.

## Collisions: a span explained twice

```python
print(t.collisions, t.collision_rate)
```

```text
() 0.0
```

A collision is a span two different rules both claim, which means at least one
of them is wrong and the parse cannot tell you which.

Note what is *not* counted. This spec declares `section report starts(/^Branch: /)`
**and** `field branch: right of "Branch:"` — those name the same seven
characters deliberately. Counting that would make the commonest correct shape
in the language fire the alarm, so a collision requires a **value** on at least
one side. A number that fires on correct specs is noise with a name.

## `trace` and `parse` share one walk

A trace cannot describe a different program from the one that ran, which is
what makes it worth trusting when you are debugging at 6pm.

---

Next: [Starting from a pile of reports](07-discovery.md)
