from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode._safe_persistence import (
    atomic_write_bytes,
    atomic_write_text,
    read_bytes,
    read_text,
)
from glio_noncode.errors import ValidationError


class SafePersistenceTests(unittest.TestCase):
    def test_atomic_writes_replace_complete_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            self.assertEqual(atomic_write_text(path, "first\n"), path)
            self.assertEqual(path.read_text(encoding="utf-8"), "first\n")
            self.assertEqual(atomic_write_bytes(path, b"second\n"), path)
            self.assertEqual(path.read_bytes(), b"second\n")
            self.assertEqual(tuple(Path(directory).glob(".*.tmp")), ())

    def test_rejects_symlinked_target_and_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.txt"
            outside.write_text("unchanged", encoding="utf-8")
            target = root / "artifact.txt"
            parent_link = root / "linked"
            try:
                target.symlink_to(outside)
                with self.assertRaises(ValidationError):
                    atomic_write_text(target, "redirected")
                self.assertEqual(outside.read_text(encoding="utf-8"), "unchanged")

                parent_link.symlink_to(root, target_is_directory=True)
                with self.assertRaises(ValidationError):
                    atomic_write_text(parent_link / "artifact.txt", "redirected")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")

    def test_rejects_non_directory_parent_and_non_string_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent_file = root / "parent"
            parent_file.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(ValidationError):
                atomic_write_text(parent_file / "artifact.txt", "payload")
            with self.assertRaises(ValidationError):
                atomic_write_text(root / "artifact.txt", 42)  # type: ignore[arg-type]
            with self.assertRaises(ValidationError):
                atomic_write_bytes(root / "artifact.txt", "payload")  # type: ignore[arg-type]

    def test_safe_reads_preserve_payload_and_reject_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "fixture.json"
            target.write_bytes(b'{"ok":true}\n')
            self.assertEqual(read_bytes(target), b'{"ok":true}\n')
            self.assertEqual(read_text(target), '{"ok":true}\n')
            link = root / "link.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(ValidationError):
                read_bytes(link)
            with self.assertRaises(ValidationError):
                read_text(link)


if __name__ == "__main__":
    unittest.main()
