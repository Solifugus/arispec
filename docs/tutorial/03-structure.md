# 3. Sections, repeats and rows

Real reports nest: regions hold branches, branches hold tellers, tellers hold
a table of transactions. Three words cover all of it.

```python
import arispec

report = """\
REGION: SOUTHEAST
  BRANCH 142  RIVERSIDE
    0017447348  SMITH, JOHN Q      24,368.82
    0015615407  GARCIA, MARIA      36,868.53
  BRANCH 149  NORTHGATE
    0018887310  LINDQVIST, INES    15,876.05
"""

spec = """
section report:
    field region: right of "REGION:"

    section branches repeats starts(/^  BRANCH /):
        field no: right of "BRANCH" as integer
        rows:
            field account: columns 4-14
            field amount:  last money
"""

r = arispec.parse(report, spec)
for b in r.value["branches"]:
    print(b["no"], b["rows"]["amount"])
```

```text
142 [Decimal('24368.82'), Decimal('36868.53')]
149 [Decimal('15876.05')]
```

## `starts(...)` — where a section begins

A pattern in `starts(...)` is a `"literal"` or a `/regex/`. The first line
matching it opens the section.

```text
section branches starts(/^  BRANCH /):
```

The leading two spaces in that regex are doing real work — they distinguish an
indented branch heading from the word BRANCH appearing anywhere else.

## `repeats` — and how a section knows to stop

```text
section branches repeats starts(/^  BRANCH /):
```

Without `repeats` you get the first instance. With it you get a list of them.

A repeating section with no `ends(...)` runs **until the next occurrence of its
own `starts` pattern**, or the end of its parent. That is what makes `BRANCH`
work: nothing in the report terminates a branch, the next branch just begins.

When a block *does* have a terminator, say so:

```text
section detail starts(/^    ACCOUNT/) ends(/^\s*$|^    -+$/):
```

A blank line or a rule line closes it. Alternation is ordinary regex.

**One instance cannot tell you it found them all.** If a branch has two tables
and your spec omits `repeats`, you get the first and no complaint. When you
expect several, say `repeats` and check the count.

## `rows:` — one record per line, as a frame

```text
rows:
    field account: columns 4-14
    field amount:  last money
```

`rows:` means *one record per remaining line in this section*. The result is a
**frame** — columns of equal length:

```python
print(r.value["branches"][0]["rows"])
```

```text
{'account': ['0017447348', '0015615407'], 'amount': [Decimal('24368.82'), Decimal('36868.53')]}
```

Columns rather than a list of records, because that is what a dataframe takes:

```text
import polars as pl
pl.DataFrame(r.value["branches"][0]["rows"])
```

arispec depends on nothing and does not import polars or pandas; it just hands
you the shape they accept.

## The section's own heading is not a data row

```text
section detail starts(/^GL\s+Tran #/):
    rows:
        field gl: columns 0-24
```

The line that *matched* `starts(...)` belongs to the section. It is not
offered to `rows:`, so the column heading does not become your first record.
This is the kind of rule you only notice when it is missing.

## Anchor by label, not by row offset

Here is the case that decides the whole design. Two tellers in one report:

```text
Teller: Wendy Hermin         Teller #: 386
Beginning Cash                          $13,586.25
Ending Cash                              $8,651.75-
Total Transactions                      $56,870.50

Teller: Ryan Bellbowl        Teller #: 261
Beginning Cash                           $3,863.50
Total Transactions                      $66,921.35
Ending Cash                             $18,510.75
```

Read them. **The second teller prints Total before Ending.** Same report, same
page, different order — because the program that generates it has a branch in
it that nobody has looked at since.

A spec written as "line 2 is beginning, line 3 is ending, line 4 is total"
parses both without error and returns the wrong number for the second one.
Nothing is unknown. Nothing is flagged. The totals just disagree with the
general ledger by one teller's day.

```text
field beginning_cash: right of "Beginning Cash" as money
field ending_cash:    right of "Ending Cash" as money
field total_trans:    right of "Total Transactions" as money
```

Anchored by label, both tellers come out right, and you never had to know the
report was inconsistent.

---

Next: [Locators: across and down the page](04-locators.md)
