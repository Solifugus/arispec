# arispec

**Declarative extraction from irregular text reports.** No dependencies.

Legacy print reports, mainframe spool, teller totals, delinquency registers —
the fixed-width output that every bank, insurer, telecom and government agency
still produces, and that no CSV reader will touch.

```bash
pip install arispec
```

## The problem, measured

Here are three rows of a real-shaped teller report. Find the amount.

```text
GL                          Tran #    Type                          Amount
Cash Deposit             001000234    12                             $9,250.00
Check Deposit CHK#4211   001002345    11                            $18,500.00
ACH Transfer             001004326    13                             $6,000.25-
```

The `Amount` heading ends at column 74. Its values end at columns 78, 78 and
**79**. The heading is four columns adrift of its own data — headings and data
drift apart over decades of separate edits — and the row that runs a column
further is the negative one, because a trailing minus is appended *after*
right-justification.

So pin the column at 78 and you truncate the sign, turning −6000.25 into
6000.25. Pin it at 79 and every positive carries a leading space. Use the
heading and you are four columns out. **Neither the heading nor the column can
find the amount.**

What works is asking the way a person reads it: *the last money-shaped token
on this row.*

```python
import arispec

report = """\
GL                          Tran #    Type                          Amount
Cash Deposit             001000234    12                             $9,250.00
Check Deposit CHK#4211   001002345    11                            $18,500.00
ACH Transfer             001004326    13                             $6,000.25-
"""

spec = """
section detail starts(/^GL\\s+Tran #/):
    rows:
        field gl:     columns 0-24
        field amount: last money
"""

r = arispec.parse(report, spec)
print(r.value["rows"]["amount"])
```

```text
[Decimal('9250.00'), Decimal('18500.00'), Decimal('-6000.25')]
```

`as <type>` does not merely convert a value — it **delimits** it. That is the
central idea, and everything else follows from it.

## A spec is data, not code

```text
section report:
    field branch: right of "Branch:" as integer

    section tellers repeats starts(/^Teller: /):
        field name:      between "Teller:" and "Teller #:"
        field teller_no: right of "Teller #:" as integer
        field opened:    down 1 of "OPENED" as date
```

A short indented document you can store in a database, generate from a UI,
diff in review and hand to someone who has never seen this library. Not a
chain of method calls that exists only in source.

## It refuses rather than guesses

A cell that matches no rule becomes `UNKNOWN` **for that cell alone** — never
a silent zero, and never an exception that sinks a 100,000-line import because
one teller's bait cash was keyed `$8,0000`.

```python
r = arispec.parse('Bait Cash   $8,0000\n', """
section drawer:
    field bait_cash: right of "Bait Cash" as money
""")
print(r.value["bait_cash"], r.diagnostics)
```

```text
UNKNOWN ({'path': 'drawer.bait_cash', 'reason': 'malformed-money', 'line': 1},)
```

`03/04/2026` is 3 April and 4 March and nothing in the token says which, so it
is `ambiguous-date` until a spec declares `using date: dmy`. `27/12/2026`
needs no declaration — 27 cannot be a month.

## Start here

| | |
|---|---|
| [1. Your first spec](docs/tutorial/01-your-first-spec.md) | Three fields out of a five-line report |
| [2. Why a column cannot find the amount](docs/tutorial/02-why-columns-lie.md) | The idea the library is built on |
| [3. Sections, repeats and rows](docs/tutorial/03-structure.md) | Reports that nest, and tables inside them |
| [4. Locators: across and down the page](docs/tutorial/04-locators.md) | Labels above, beside and below their values |
| [5. Types, dialects and refusals](docs/tutorial/05-values.md) | Reading money and dates that disagree with themselves |
| [6. What did my spec miss?](docs/tutorial/06-trace.md) | `trace`, and why coverage is not a grade |
| [7. Starting from a pile of reports](docs/tutorial/07-discovery.md) | Profiling a corpus you have never read |
| [Spec language reference](docs/spec-language.md) | Every locator, every directive, on one page |

## Every example here runs

`tests/test_docs.py` executes every `python` block in this README and in
`docs/`, and compares what it prints against the `text` block beneath it.
Documentation rots quietly — a rename lands, the suite stays green, and the
tutorial keeps printing an output nobody re-ran. Writing these tutorials found
two real defects in the library, which is the argument for doing it this way.

## Status

0.1.0 — the spec parser, the runtime, `trace`, and discovery Phases 0 and 1:
profiling a corpus, and proposing a specification for its dominant repeating
row family. 121 tests over six report fixtures plus a 24-source corpus with a
planted answer key.

Next: sections and pagination (Phase 2), so a proposal nests branches around
their rows instead of flattening them.

Ported from gBASIC's `stdlib/ari.bas`, with which it shares its spec language
and its measured behaviour.

Apache-2.0. Copyright 2026 Matthew C. Tedder.
