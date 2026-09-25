# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""The source grid (design §6.1).

No preprocessing step may destroy the mapping back to the original bytes, so
each row carries its own byte offset into the file and its byte length
alongside the codepoint measures a rule would use.

A FORM FEED IS A LINE, not a character to strip. It is the strongest page
evidence a print-image report carries, and removing it in normalisation would
throw away the one signal that makes pagination unambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._spans import byte_count

__all__ = ["Row", "grid"]


@dataclass(frozen=True, slots=True)
class Row:
    source_id: str
    physical_line: int          # 1-based, into the original file
    page_guess: int
    text: str                   # the form feed removed, nothing else
    form_feed: bool
    byte_start: int             # provenance: into the file
    byte_length: int
    cp_length: int              # rules: ARI's own index space
    indent: int
    trimmed_length: int
    blank: bool


def grid(source_id: str, report_text: str) -> list:
    lines = report_text.split("\n")
    # A trailing newline produces a final empty element, which is not a line.
    if lines and lines[-1] == "":
        lines = lines[:-1]

    rows, byte_at_line, page = [], 0, 1
    for i, raw in enumerate(lines):
        ff = "\f" in raw
        body = raw.replace("\f", "")
        stripped = body.strip()
        rows.append(Row(
            source_id=source_id,
            physical_line=i + 1,
            page_guess=page,
            text=body,
            form_feed=ff,
            byte_start=byte_at_line,
            byte_length=byte_count(raw),
            cp_length=len(body),
            indent=len(body) - len(body.lstrip(" ")),
            trimmed_length=len(stripped),
            blank=not stripped,
        ))
        if ff:
            page += 1
        byte_at_line += byte_count(raw) + 1     # the newline
    return rows
