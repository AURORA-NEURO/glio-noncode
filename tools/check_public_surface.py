#!/usr/bin/env python3
"""Fail when the generated lazy-root surface differs from the eager root."""

from __future__ import annotations

from migrate_public_surface import (
    build_manifest,
    check_generated,
    validate_manifest,
)


def main() -> int:
    manifest = build_manifest()
    validate_manifest(manifest)
    check_generated(manifest)
    print(
        f"public surface is current: {len(manifest.exports)} descriptors, "
        f"{len(manifest.all_names)} __all__ entries, {manifest.surface_digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
