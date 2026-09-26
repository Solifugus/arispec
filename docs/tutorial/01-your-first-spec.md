# 1. Your first spec

A five-line report, three fields out of it.

```python
import arispec

report = """\
ACME SAVINGS                                    Page 1

Account: 0012345678
Opened:  14/03/2021
Balance:      $1,284.55
"""

spec = """
section account:
    field number:  right of "Account:"
    field opened:  right of "Opened:" as date
    field balance: right of "Balance:" as money
"""

r = arispec.parse(report, spec)
print(r.value)
```

```text
{'number': '0012345678', 'opened': datetime.date(2021, 3, 14), 'balance': Decimal('1284.55')}
```

Three things happened there that are worth slowing down for.

## You got native values, not strings

`opened` is a `datetime.date` and `balance` is a `Decimal` — not `'14/03/2021'`
and `'$1,284.55'`. A `Decimal`, not a float: money that goes through binary
floating point stops summing to what the report says, and a report is
something people reconcile against.

`number` is a string because you did not ask for a type. Account numbers with
leading zeros are strings, and `as integer` would have quietly eaten the two
zeros off the front of `0012345678`.

## The locator found the value, not the column

`right of "Account:"` means *everything after that literal, to the end of the
line*. Nothing in the spec mentions column 9, so the spec still works when
somebody widens the label next quarter.

## The type did the trimming

`right of "Balance:"` hands over `'      $1,284.55'` — spaces, a currency
symbol, a grouping comma. `as money` reduced that to `Decimal('1284.55')` by
finding the money-shaped token inside it.

That is the whole idea, and [tutorial 2](02-why-columns-lie.md) is about why
it has to work that way.

## The shape of a spec

```text
section <name>:
    field <name>: <locator> [as <type>]
```

Indentation defines the blocks, like Python or YAML. `section` groups fields;
the value you get back is a dict keyed by field name, and a nested section is
a nested dict.

A spec is **data**. It is a short document you can keep in a config file or a
database column, generate from a form, diff in code review, and hand to a
colleague who has never used this library — which is the point, because
recurrence and layout rules outlive the programs that read them.

## When a spec is wrong

```python
r = arispec.parse(report, """
section account:
    field balance: right of "Balance:" as munny
""")
print(r.ok, r.message)
```

```text
False account.balance: `munny` is not a type (builtins: date, money, integer, decimal, text)
```

`ok` is about the **specification**, not the report. A spec that cannot be read
gives `ok=False` and a message. A report with unreadable *cells* parses fine
and records them separately — [tutorial 5](05-values.md) covers that, and the
difference matters more than it looks.

---

Next: [Why a column cannot find the amount](02-why-columns-lie.md)
