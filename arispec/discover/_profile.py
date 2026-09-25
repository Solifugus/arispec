# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""The profile (design §9).

WHAT PHASE 0 IS AND IS NOT. It measures what repeats, varies and collides in a
corpus of print-image reports, and it **proposes nothing**. There is no
specification generation here, deliberately: design principle 1 is
"measurement before interpretation", and a profiling layer that also guessed
would make the guess impossible to evaluate separately from the measurement it
rests on.
"""

from __future__ import annotations

from collections import defaultdict

from ._families import families
from ._furniture import furniture
from ._grid import grid
from ._options import options_from
from ._spans import byte_count

__all__ = ["profile", "profile_corpus", "profile_source"]


def profile(report_text: str, options=None) -> dict:
    """Profile one report."""
    return profile_source({"id": "source", "text": report_text}, options)


def profile_source(source, options=None) -> dict:
    o = options_from(options)
    if "text" not in source:
        raise ValueError("ari_discover.profile_source: a source needs `text`")
    sid = source.get("id", "source")

    rows = grid(sid, source["text"])
    furn = furniture(rows, o)
    fams = families(rows, furn["lines"], o)

    blanks = sum(1 for r in rows if r.blank)
    content = sum(1 for r in rows
                  if not r.blank and r.physical_line not in set(furn["lines"]))

    return {"id": sid, "physical_lines": len(rows),
            "bytes": byte_count(source["text"]),
            "blank_lines": blanks, "content_lines": content,
            "furniture": furn, "families": fams, "grid": rows}


def profile_corpus(sources, options=None, profiles_in=None) -> dict:
    """Across a corpus.

    §5.1: variation between files is what separates a true constant from an
    accidental one, so a signature seen in ONE source is reported with the
    count of sources carrying it and not merely its frequency -- which is the
    number ``minimum_support`` is about.
    """
    o = options_from(options)
    sources = list(sources)
    if not sources:
        raise ValueError("ari_discover.profile_corpus: no sources")

    profiles = list(profiles_in) if profiles_in is not None else \
        [profile_source(s, o) for s in sources]

    across = defaultdict(int)
    for p in profiles:
        for sig in {fm["signature"] for fm in p["families"]}:
            across[sig] += 1

    nsrc = len(profiles)
    shared, only_one = [], []
    for sig, count in sorted(across.items(), key=lambda kv: (-kv[1], kv[0])):
        entry = {"signature": sig, "sources": count, "support": count / nsrc}
        if entry["support"] >= o.minimum_support:
            shared.append(entry)
        if count == 1:
            only_one.append(entry)

    # §5.2: the threshold cannot be calibrated on a corpus this small, and
    # saying so beats reporting a support figure that can only take a few
    # values. Ten is where a tenth of a point of support is one source.
    warn = ""
    if nsrc < 10:
        warn = (f"support over {nsrc} sources can only take {nsrc} distinct "
                f"values, so `minimum_support` cannot be calibrated here; at "
                f"least 10 sources are needed for the threshold to mean what "
                f"it says")

    return {"sources": nsrc, "profiles": profiles, "shared": shared,
            "only_one_source": only_one, "warning": warn}
