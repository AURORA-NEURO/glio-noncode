"""Shared test-process safeguards for the generated historical module graph."""

from __future__ import annotations

import sys


# Historical compatibility layers are intentionally importable as a single
# public chain. Pytest's assertion/import hooks add frames to that chain on
# Windows, so keep the test process below Python's safe recursion boundary
# without changing the production interpreter configuration.
sys.setrecursionlimit(max(sys.getrecursionlimit(), 4096))
