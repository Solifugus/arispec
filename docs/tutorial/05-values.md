# 5. Types, dialects and refusing to guess

A single report disagrees with itself. Three branches of one teller report
print money three different ways, because three different programs wrote them
over twenty years:

```text
branch 14:   $13,586.25          plain
branch 21:   $        -12,113.25  symbol, inner padding, leading minus
branch 28:   12,573.25-           no symbol, trailing minus
```

So a type is not a pattern. It is a **permissive recognizer over the union of
forms**, and `as money` reads all three without being told which is which.

```python
import arispec

spec = 'section r:\n    field amount: last money\n'
for line in ["$13,586.25", "$        -12,113.25", "12,573.25-",
             "(1,234.56)", "<$99.00>", "1,234.56 CR", "1.234,56"]:
    print(f"{line:>22}  ->  {arispec.parse(line + '\\n', spec).value['amount']}")
```

```text
            $13,586.25  ->  13586.25
   $        -12,113.25  ->  -12113.25
            12,573.25-  ->  -12573.25
            (1,234.56)  ->  -1234.56
              <$99.00>  ->  -99.00
           1,234.56 CR  ->  -1234.56
              1.234,56  ->  1234.56
```

The last one is European grouping — `1.234,56` is one thousand two hundred
thirty-four and fifty-six, not one point two three four. It reads correctly
because **the last separator is the decimal mark**, and that is a fact about
the two notations rather than a guess about this report: each convention uses
the other character for grouping.

## What it refuses, and why that is the feature

```python
for line in ["1.234", "123,45", "$8,0000", "1,234.567"]:
    r = arispec.parse(line + "\n", spec)
    print(f"{line:>12}  ->  {r.value['amount']!r}   {r.diagnostics[0]['reason']}")
```

```text
       1.234  ->  UNKNOWN   malformed-money
      123,45  ->  UNKNOWN   malformed-money
     $8,0000  ->  UNKNOWN   malformed-money
   1,234.567  ->  UNKNOWN   malformed-money
```

`1.234` is one thousand two hundred thirty-four under one convention and
one-point-two-three-four under the other. **A single separator is genuinely
ambiguous**, and reading it either way would be choosing a convention the token
does not state. So it stays unknown.

`1,234.567` has three decimal places. An earlier version of this engine
returned `1234.56` for it — a third decimal silently dropped. Related measured
failures, each of which returned a number a reader would accept:

| input | used to give | error |
|---|---|---|
| `1,234.567` | `1234.56` | a decimal place dropped |
| `1.234,56` | `1.23` | **thousandfold** |
| `12.345.678,90` | `12.34` | **millionfold** |
| `1,234` as integer | `1` | a count off by a thousand |

Not one of them raised. That is why the recognizers refuse a token that sits
inside a longer number, and why you should be suspicious of any extraction
tool that never says "I don't know".

## UNKNOWN is per cell

```python
report = """\
Teller#: 386
Hundreds    13
Bait Cash   $8,0000
"""
r = arispec.parse(report, """
section c:
    field teller:    right of "Teller#:" as integer
    field hundreds:  right of "Hundreds" as integer
    field bait_cash: right of "Bait Cash" as money
""")
print(r.value["teller"], r.value["hundreds"], r.value["bait_cash"])
print([(d["path"], d["reason"]) for d in r.diagnostics])
```

```text
386 13 UNKNOWN
[('c.bait_cash', 'malformed-money')]
```

One malformed cell. The record still parses, the other two fields are fine,
and the bad one is named with a reason and a line number. Never a silent zero;
never an exception that sinks a 100,000-line import.

`UNKNOWN` has no truth value on purpose — `if value:` would quietly treat an
unreadable cell as an empty one:

```python
from arispec import UNKNOWN
try:
    bool(UNKNOWN)
except TypeError as e:
    print(str(e)[:60])
```

```text
UNKNOWN has no truth value -- an unreadable cell is not an e
```

Test it with `is UNKNOWN`.

## Dates, and the ambiguity that cannot be settled

```python
spec = 'section r:\n    field d: first date as date\n'
for line in ["27/12/2026", "2026-03-15", "15-Mar-2026", "03/04/2026"]:
    r = arispec.parse(line + "\n", spec)
    why = r.diagnostics[0]["reason"] if r.diagnostics else ""
    print(f"{line:>12}  ->  {r.value['d']!s:<12} {why}")
```

```text
  27/12/2026  ->  2026-12-27   
  2026-03-15  ->  2026-03-15   
 15-Mar-2026  ->  2026-03-15   
  03/04/2026  ->  UNKNOWN      ambiguous-date
```

`27/12/2026` needs no declaration — 27 cannot be a month. `03/04/2026` is 3
April and 4 March, and **nothing in the token says which**. Picking the
commoner reading would be wrong half the time in silence, so it refuses.

Tell it:

```python
r = arispec.parse("03/04/2026\n", """
section r:
    using date: dmy
    field d: first date as date
""")
print(r.value["d"])
```

```text
2026-04-03
```

**A declaration is authoritative, not a hint.** Under `using date: mdy`,
`27/12/2026` becomes `invalid-date` rather than being quietly re-read
day-first — month 27 does not exist, and you have stated this column is
month-first, so the honest answer is that the data contradicts the
declaration.

## `using` is scoped

```text
section report:
    using date: dmy              # applies here and below

    section legacy starts(/^OLD/):
        using date: mdy          # overrides, inside this section only
        field d: first date as date
```

And a `using` that names nothing real is refused when the spec is read, with
the known set spelled out:

```python
r = arispec.parse("x\n", 'section r:\n    using date: german\n    field a: right of "x"\n')
print(r.ok, r.message)
```

```text
False r: `using date: german` names neither a declared type nor a dialect of date (dialects: dmy, mdy; declared types: none)
```

## When the union is not enough

Declare your own type. Rules are tried in order and the first match wins, so
the negative form must come first:

```python
spec = """
type usd_bracketed:
    /<\\$?([\\d,]+\\.\\d{2})>/   -> negate as decimal
    /\\$?\\s*([\\d,]+\\.\\d{2})/  -> as decimal
    output: money

section r:
    field a: right of "A:" as usd_bracketed
    field b: right of "B:" as usd_bracketed
"""
r = arispec.parse("A: <$1,234.56>\nB: $1,234.56\n", spec)
print(r.value)
```

```text
{'a': Decimal('-1234.56'), 'b': Decimal('1234.56')}
```

A rule may also **rewrite** before converting, with `$1`..`$9` group
references — useful for a shape the recognizers do not know:

```text
type rewritten_date:
    /([0-9]{2})\/([0-9]{2})\/([0-9]{4})/$3-$2-$1/ -> as date
    output: date
```

A value matching no rule becomes `UNKNOWN` with `no-rule-matched`. Same
discipline: that cell, and nothing else.

---

Next: [What did my spec miss?](06-trace.md)
