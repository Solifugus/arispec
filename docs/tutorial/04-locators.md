# 4. Locators: across and down the page

A locator answers *where is the value*, relative to the lines of the current
record.

## Across a line

| locator | takes |
|---|---|
| `right of <pat>` | from just after the match to the end of the line |
| `left of <pat>` | from the start of the line to just before the match |
| `between <pat> and <pat>` | the span between two matches |
| `columns <a>-<b>` | a fixed span, 0-based and inclusive |
| `first <type>` / `last <type>` | the first or last token of that type |
| `<locator> within columns <a>-<b>` | the same search, restricted to a window |

`<pat>` is a `"literal"` or a `/regex/`. The quoting is the whole distinction.

```python
import arispec

r = arispec.parse(
    'Teller: Wendy Hermin         Teller #: 386                Summary\n',
    """
section t:
    field name:      between "Teller:" and "Teller #:"
    field teller_no: right of "Teller #:" as integer
""")
print(repr(r.value["name"]), r.value["teller_no"])
```

```text
'Wendy Hermin' 386
```

## `within columns` — when a literal is also part of a longer word

A closing-cash grid contains both `Dollars` and `Half-Dollars`. Anchoring on
the literal `"Dollars"` matches inside both.

A word boundary does **not** fix this, and it is worth knowing why: a hyphen is
a non-word character, so there *is* a boundary between `-` and `D`.
`\bDollars` matches inside `Half-Dollars` exactly as the bare literal does.
What is needed is a whitespace-or-line-start boundary, which is a different
assertion:

```text
field dollars: right of /(^| )Dollars/ as integer
```

or, when the area is columnar anyway, restrict the search:

```text
field dollars: right of "Dollars" within columns 26-79 as integer
```

## Down the page

Labels are not always beside their values.

```python
report = """\
  BRANCH 142  RIVERSIDE
  OFFICER
  T. OKONKWO
  ------------------------------------------
                              90,180.72
                          =================
                          BRANCH TOTAL

  NOTES ..................... SEE SCHEDULE B
  REMARKS:

    Member contacted; promised payment.
"""

spec = """
section branch starts(/^  BRANCH /):
    field officer: down 1 of "OFFICER"
    field total:   up 2 of "BRANCH TOTAL" as money
    field notes:   right flush of /\\.\\.\\.\\. /
    field remarks: down 1-3 of "REMARKS:"
"""

r = arispec.parse(report, spec)
for k, v in r.value.items():
    print(f"{k:>8}: {str(v).strip()!r}")
```

```text
 officer: 'T. OKONKWO'
   total: '90180.72'
   notes: 'SEE SCHEDULE B'
 remarks: 'Member contacted; promised payment.'
```

`down 1 of "OFFICER"` — find the anchor, take the line below it.
`up 2 of "BRANCH TOTAL"` — the amount is printed *above* its label, under a
rule. Reports do this.

## A distance may be a range, and usually should be

`down 1-3 of "REMARKS:"` searches offsets 1, 2 and 3 and takes the first that
yields a value.

That is not a convenience. In the delinquency fixture in this repo, the gap
between `REMARKS:` and its note is **1, 2, 2 and 3 lines** across four
branches, because the generator emits a varying number of blank lines — which
is what real reports do. An exact distance matches one branch and misses the
other three, silently, leaving three `UNKNOWN`s that look like missing data
rather than a broken spec.

| form | meaning |
|---|---|
| `down 2 of X` | exactly two lines below |
| `down 1-3 of X` | the first of offsets 1, 2, 3 that yields a value |
| `down 3- of X` | from 3 to the end of the block |
| `down -8 of X` | from 1 to 8 |
| `down flush of X` | to the edge of the block |

`right flush of <pat>` reads naturally and means what `right of` already does —
to the end of the line. It is accepted so specs can say it.

## Page furniture

A page header that recurs every 60 lines is not data, and it will wreck your
anchors if it lands in the middle of a section. Strip it once, at the top:

```text
page:
    break: formfeed
    drop: 2
```

or, for reports paginated by a header line rather than a form feed:

```text
page:
    break: /^[0-9]{2}\/[0-9]{2}\/[0-9]{4} .*Page [0-9]+$/
    drop: 2
```

`break:` says where furniture begins; `drop:` says how many lines to remove,
**counting from and including the break line**. `drop: through /regex/` removes
up to and including the first subsequent match, for a header block whose height
varies.

Everything downstream sees the clean grid, so `up` and `down` count over the
*content* and never over the physical file — an offset means the same thing
regardless of where a page happened to break. Diagnostics still report physical
line numbers, so you can open the file and look.

```python
strip_headings = """
page:
    break: /^  BRANCH /
    drop: 1

section body:
    field first: right of "OFFICER"
"""
clean = arispec.clean_grid(report, strip_headings)
print(len(report.splitlines()), "->", len(clean))
```

```text
12 -> 12
```

---

Next: [Types, dialects and refusals](05-values.md)
