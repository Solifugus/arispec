# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Discovery options, with an allow-list."""

from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = ["Options", "option_names", "options_from"]


@dataclass(frozen=True, slots=True)
class Options:
    minimum_support: float = 0.80
    minimum_confidence: float = 0.70
    minimum_family_share: float = 0.15
    minimum_variant_sources: int = 3
    holdout: int = 0
    maximum_section_depth: int = 4
    allow_fixed_columns: bool = False
    redact_examples: bool = False


def option_names() -> tuple:
    return tuple(f.name for f in fields(Options))


def options_from(given) -> Options:
    """``None`` means the caller supplied none; a dict is checked against the
    allow-list, which keyword arguments would give for free but a stored
    options record would not."""
    if given is None:
        return Options()
    if isinstance(given, Options):
        return given
    if not isinstance(given, dict):
        raise TypeError(
            f"ari_discover: options must be a dict, not a {type(given).__name__}")
    unknown = [k for k in given if k not in option_names()]
    if unknown:
        raise ValueError(
            f"ari_discover: '{unknown[0]}' is not an option -- the options are "
            + ", ".join(option_names()))
    return Options(**given)
