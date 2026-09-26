# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Run every example in the documentation.

Documentation rots quietly: a rename lands, the tests stay green, and the
tutorial keeps printing an output nobody re-ran. So each ```python block in
`README.md` and `docs/` is executed here, in file order, sharing a namespace
within its file the way a reader following along would.

Where a ```python block is immediately followed by a ```text block, that text
is treated as the expected output and compared. That is the half that actually
decays -- code keeps running long after it stops printing what the prose says
it prints.
"""

import contextlib
import io
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = [ROOT / "README.md"] + sorted((ROOT / "docs").rglob("*.md"))

_BLOCK = re.compile(r"^```(python|text)\n(.*?)^```", re.S | re.M)


def blocks(text):
    """(language, body, expected_output_or_None) for each fenced block."""
    found = [(m.group(1), m.group(2), m.end()) for m in _BLOCK.finditer(text)]
    for i, (lang, body, _end) in enumerate(found):
        if lang != "python":
            continue
        nxt = found[i + 1] if i + 1 < len(found) else None
        expected = nxt[1] if nxt and nxt[0] == "text" else None
        yield body, expected


class TestDocumentation(unittest.TestCase):
    maxDiff = None

    def test_every_example_runs_and_prints_what_it_says(self):
        checked = ran = 0
        for doc in DOCS:
            ns = {"__name__": "__doc_example__"}
            for i, (code, expected) in enumerate(blocks(doc.read_text()), 1):
                where = f"{doc.relative_to(ROOT)} block {i}"
                out = io.StringIO()
                try:
                    # Relative fixture paths in the docs are written as a
                    # reader would, from the repo root.
                    with contextlib.redirect_stdout(out), _cwd(ROOT):
                        exec(compile(code, where, "exec"), ns)
                except Exception as e:                  # noqa: BLE001
                    self.fail(f"{where} raised {type(e).__name__}: {e}\n\n{code}")
                ran += 1
                if expected is None:
                    continue
                self.assertEqual(expected.strip(), out.getvalue().strip(),
                                 f"{where} printed something else")
                checked += 1
        self.assertGreater(ran, 20, "the doc scanner found almost nothing")
        self.assertGreater(checked, 15, "almost no example has expected output")


@contextlib.contextmanager
def _cwd(path):
    import os
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class TestDocumentationLinks(unittest.TestCase):
    def test_every_relative_link_resolves(self):
        broken = []
        for doc in DOCS:
            for m in re.finditer(r"\[[^\]]+\]\(([^)#:]+)\)", doc.read_text()):
                target = (doc.parent / m.group(1)).resolve()
                if not target.exists():
                    broken.append(f"{doc.relative_to(ROOT)} -> {m.group(1)}")
        self.assertEqual([], broken)


if __name__ == "__main__":
    unittest.main()
