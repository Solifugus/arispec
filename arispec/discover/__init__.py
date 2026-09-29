# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""``arispec.discover`` -- measure a corpus of reports, and propose nothing.

Phase 0 of spec inference: what repeats, what varies, what collides. Give it
forty quarters of the same report and it tells you where the page furniture is,
which line shapes recur, and which literals are stable enough to anchor on.

    from arispec import discover

    p = discover.profile(report_text)
    p["furniture"]["lines"]      # physical line numbers that are page furniture
    p["families"]                # recurring line shapes, most frequent first

    c = discover.profile_corpus([{"id": "q1", "text": ...}, ...])
    c["shared"]                  # signatures most sources carry
    c["only_one_source"]         # and those only one does

``profile`` proposes nothing, deliberately -- measurement before
interpretation, so a guess can always be evaluated separately from the
measurement it rests on. :func:`infer` is where the guessing starts, and it
shows its working::

    p = discover.infer([{"id": "q1", "text": ...}, ...])
    print(p["spec"])              # a specification, with its evidence in comments
    p["questions"]                # what no anchor-relative rule could reach
    p["anchor_stability"]         # whether the layout is the same everywhere

**The dependency points one way.** ``arispec`` never imports this, so a caller
with a known specification pays none of it -- no clustering, no inference. That
is the architectural rule (§2), and it is why this is a submodule you import
explicitly rather than part of ``arispec``'s own surface.
"""

from ._families import families
from ._infer import columns_of, gutters, infer_fields, spec_text
from ._furniture import furniture, page_starts
from ._grid import Row, grid
from ._options import Options, option_names, options_from
from ._profile import profile, profile_corpus, profile_source
from ._propose import Proposal, infer
from ._spans import (Span, byte_count, shape, signature, spans, token_kinds,
                     words_of)
from ._validate import anchor_stability, validate

__all__ = [
    "Options", "Proposal", "Row", "Span", "anchor_stability", "byte_count",
    "columns_of", "families", "furniture", "grid", "gutters", "infer",
    "infer_fields", "option_names", "options_from", "page_starts", "profile",
    "profile_corpus", "profile_source", "shape", "signature", "spans",
    "spec_text", "token_kinds", "validate", "words_of",
]
