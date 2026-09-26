# Spec language reference

An indentation-defined document. Blocks are opened by a trailing `:` and
closed by dedenting. A line whose first non-space character is `'` is a
comment.

```text
spec        := page-decl? type-decl* section+

page-decl   := "page:" INDENT ("break:" break-spec) ("drop:" drop-spec) DEDENT

type-decl   := "type" NAME ":" INDENT type-rule+ ("output:" base-type) DEDENT
type-rule   := "/" regex "/" ["/" replacement "/"] "->" action

section     := "section" NAME section-mod* ":" INDENT section-body DEDENT
section-mod := "repeats" | "starts(" pat ")" | "ends(" pat ")"
section-body:= using-decl* (field | section | rows)+

rows        := "rows" ["continue(" pat ")"] ":" INDENT field+ DEDENT
using-decl  := "using" base-type ":" NAME

field       := "field" NAME ":" locator ["as" type-ref]

pat         := "\"" literal "\"" | "/" regex "/"
```

## Patterns

`"literal"` matches exactly. `/regex/` is a Python regular expression. The
quoting is the only distinction, and it applies everywhere a pattern is taken:
`starts()`, `ends()`, `continue()`, and inside every locator.

## Locators

| locator | takes |
|---|---|
| `right of <pat>` | from just after the match to the end of the line |
| `right flush of <pat>` | the same; `flush` reads naturally and is accepted |
| `left of <pat>` | from the start of the line to just before the match |
| `between <pat> and <pat>` | the span between two matches on one line |
| `columns <a>-<b>` | a fixed span, 0-based, inclusive |
| `first <type>` | the first token of that type on the line |
| `last <type>` | the last token of that type on the line |
| `down <dist> of <pat> [<locator>]` | apply the locator `dist` lines below the anchor |
| `up <dist> of <pat> [<locator>]` | the same, upward |
| `<locator> within columns <a>-<b>` | restrict the search to a column window |

A vertical locator with no inner locator takes the whole target line.

### Distances

| form | meaning |
|---|---|
| `2` | exactly two lines away |
| `1-3` | the first of offsets 1, 2, 3 that yields a value |
| `3-` | from 3 to the edge of the block |
| `-8` | from 1 to 8 |
| `flush` | to the edge of the block |

A range is the usual case: label-to-value gaps vary down a real report.

## Types

Built-ins: `date`, `money`, `integer`, `decimal`, `text`.

Each is a permissive recognizer over the union of common forms, and **`as
<type>` delimits as well as converts** — the span handed in may carry
neighbouring text, and the recognizer takes the token of that shape out of it.

A field naming a type that is neither a built-in nor a declared `type` is
refused when the spec is read.

| type | returns | notes |
|---|---|---|
| `text` | `str` | trimmed; also the result when no type is named |
| `integer` | `int` | grouped forms accepted (`1,234` and `1.234` are both 1234); a token with a decimal part is **refused**, not truncated |
| `decimal` | `Decimal` | any number of places |
| `money` | `Decimal` | symbols, grouping, and the notational negatives below |
| `date` | `datetime.date` | ISO, `DD-MMM-YYYY`, `MMM-DD-YYYY`, and numeric forms |

### Money forms read without a declaration

`$1,234.56` · `1234.56` · `1.234,56` (continental) · `(1,234.56)` ·
`<$1,234.56>` · `-$1,234.56` · `$-1,234.56` · `1,234.56-` · `1,234.56 CR` ·
`1,234.56 DR`

**The last separator is the decimal mark.** That reads both grouping
conventions without being told which, because each uses the other character to
group. A *single* separator (`1.234`, `123,45`) is genuinely ambiguous and is
refused.

### Dialects

A `using` may name a dialect instead of a custom type:

| built-in | dialects | settles |
|---|---|---|
| `date` | `dmy`, `mdy` | `03/04/2026` is 3 April or 4 March; nothing in the token says which |
| `money` | `ledger` *(default)*, `statement` | which sign a `DR`/`CR` suffix carries |

A declaration is **authoritative, not a hint**: under `using date: mdy`,
`27/12/2026` is `invalid-date` rather than silently re-read day-first.

Notational negatives — trailing minus, parentheses, angle brackets — are
notation, not a sense, and are unaffected by the `money` dialect.

### Custom types

```text
type usd_bracketed:
    /<\$?([\d,]+\.\d{2})>/   -> negate as decimal
    /\$?\s*([\d,]+\.\d{2})/  -> as decimal
    output: money
```

Rules are tried in order and the first match wins, so a negative form must be
declared before the general one. With a capture group and no rewrite, group 1
is the value; with a rewrite, the whole match is rewritten first.

A rewrite uses `$1`..`$9` group references:

```text
type rewritten_date:
    /([0-9]{2})\/([0-9]{2})\/([0-9]{4})/$3-$2-$1/ -> as date
    output: date
```

A value matching no rule becomes `UNKNOWN` with `no-rule-matched`.

### Scope

```text
section report:
    using money: usd_trailing     ' this section and everything nested
    section inner starts(/^X/):
        using money: usd_plain    ' overrides, here and below
```

A `using` must be written **inside** a section — there is no file scope for it
to attach to. One naming neither a declared type nor a dialect is refused when
the spec is read, with both lists named. A type written directly on a field
beats any `using` in scope.

## Sections

```text
section <name> [repeats] [starts(<pat>)] [ends(<pat>)]:
```

- The line matching `starts(...)` **belongs to the section** and is not offered
  to its `rows:` — so a column heading does not become a data row.
- `ends(...)` is optional. A `repeats` section without one runs to the next
  occurrence of its **own** `starts` pattern, or the end of its parent.
- Without `repeats` you get the first instance; with it, a list.
- A section with no `starts` spans its whole parent.

A non-repeating section that is not found yields `UNKNOWN` and a
`section-not-found` diagnostic.

## `rows:`

One record per remaining line in the enclosing section, emitted as a **frame**
— a dict of equal-length columns, which `polars.DataFrame` and
`pandas.DataFrame` both accept.

`rows continue(<pat>):` treats a line matching `<pat>` as a **continuation** of
the record above it rather than a new record, for wrapped fields. Every
locator, including the vertical ones, works inside a multi-line record.

## `page:`

```text
page:
    break: formfeed          ' or: break: /regex/
    drop: 2                  ' or: drop: through /regex/
```

`break:` says where furniture begins; `drop:` how much to remove, **counting
from and including the break line**. The form feed may sit at the start of a
line that also carries the header.

Everything downstream sees the clean grid, so `up`/`down` count over content
and never over the physical file. Diagnostics still report physical line
numbers.

## API

| call | returns |
|---|---|
| `arispec.parse(report, spec)` | `Result(ok, value, message, diagnostics)` |
| `arispec.trace(report, spec)` | `Trace` — the result plus claims, unclaimed runs, coverage, collisions |
| `arispec.clean_grid(report, spec)` | the report's lines with furniture stripped |
| `arispec.builtin_types()` | the base type names |
| `arispec.type_dialects()` | the dialect words, per built-in |
| `arispec.money_patterns()` / `date_patterns()` | the recognizer tables |

`Result.ok` is about the **specification**. A report with unreadable cells
parses fine and reports them in `diagnostics`; only a spec that cannot be read
gives `ok=False`.

`Result` and `UNKNOWN` both refuse `bool()`: a parse that succeeded with
unreadable cells is not a failure, and an unreadable cell is not an empty one.

### Diagnostic reasons

`malformed-money` · `no-integer-found` · `no-decimal-found` · `no-date-found` ·
`ambiguous-date` · `invalid-date` · `unknown-month-name` · `no-rule-matched` ·
`not-found` · `anchor-not-found` · `section-not-found`
