# 2. Why a column cannot find the amount

This is the measurement the library is built on. It is worth doing yourself.

```python
rows = """\
GL                          Tran #    Type                          Amount
Cash Deposit             001000234    12                             $9,250.00
Check Deposit CHK#4211   001002345    11                            $18,500.00
ACH Transfer             001004326    13                             $6,000.25-
"""

for line in rows.splitlines():
    print(f"{len(line.rstrip()):>3}  {line.rstrip()[-14:]!r}")
```

```text
 74  '        Amount'
 78  '     $9,250.00'
 78  '    $18,500.00'
 79  '    $6,000.25-'
```

Two separate problems, and each one alone is fatal.

## The heading is adrift of its own data

`Amount` ends at column 74. Its values end at 78 and 79. Deriving the column
span from the heading above it — the obvious, elegant approach — is four
columns wrong here and eleven columns wrong in the other fixture in this repo.

This is not a defect in the fixture. Headings and data drift apart over
decades of separate edits, because they are edited by different people at
different times for different reasons. A report that has been in production
since 1987 has had this happen.

## The negative is one column wider than the positive

Look at the last two rows, and note which one runs further right.
`$18,500.00` is the **longer number** and ends at column 78. `$6,000.25-` is
shorter and ends at **79**.

The amounts are right-justified to the same column, and *then* the trailing
minus is appended — outside the justified field. So a negative occupies one
more column than any positive, however large.

Now pick a column span:

| you choose | what happens |
|---|---|
| `columns 65-78` | `$6,000.25` — **the sign is gone.** −6000.25 becomes +6000.25 |
| `columns 65-79` | every positive carries a trailing space |
| from the heading | four columns out, every row |

The first one is the dangerous choice, because it produces a number a reader
would accept. Nothing raises. The report still balances against itself. It is
simply the wrong sign on every refund in the file.

## Ask the way a person reads it

A person does not count columns. They look at the row and take the thing that
looks like money, at the end.

```python
import arispec

spec = """
section detail starts(/^GL\\s+Tran #/):
    rows:
        field gl:     columns 0-24
        field amount: last money
"""

r = arispec.parse(rows, spec)
print(r.value["rows"]["amount"])
```

```text
[Decimal('9250.00'), Decimal('18500.00'), Decimal('-6000.25')]
```

`last money` — the last money-shaped token on the line. The sign survives. The
drift does not matter. The spec does not care that the heading moved.

## `as <type>` delimits as well as converts

That is the sentence to remember. When you write `as money`, the recognizer is
not handed a clean string to parse — it is handed whatever the locator cut,
and it **finds the token of that shape inside it**.

```python
r = arispec.parse(
    "Teller: Wendy Hermin         Teller #: 386                     Summary\n",
    """
section t:
    field teller_no: right of "Teller #:" as integer
""")
print(r.value["teller_no"])
```

```text
386
```

`right of "Teller #:"` yields `'386                     Summary'`. `as integer`
reduced that to `386`. No second locator, no trimming rule, no `.split()[0]`
that breaks when a teller is called `Summary Jones`.

## Columns are not forbidden

Notice `field gl: columns 0-24` above. Within one table the *data* columns
genuinely are stable even where the heading above them is not, and reading a
known-columnar area by column is cheaper — no search.

The rule is: **anchors by default, columns where an area is clearly columnar
and you are saying so on purpose.** What you must not do is reach for a column
because you could not work out how to anchor.

---

Next: [Sections, repeats and rows](03-structure.md)
