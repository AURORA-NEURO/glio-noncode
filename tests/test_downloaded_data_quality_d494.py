"""Regression tests for portable D494 release evidence archives."""
from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_audit as runtime_audit_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_query_audit as query_audit_model
from glio_noncode import downloaded_data_quality_d494_release_evidence_archive as archive_model
from glio_noncode import downloaded_data_quality_d494_release_evidence_archive_audit as archive_audit_model
from glio_noncode.errors import ValidationError
from tests.test_downloaded_data_quality_d491 import _registries


def _inputs(strict_added: int = 0, release_added: int = 1, *, make_bundle: bool = True, query_resources: tuple[str, ...] | None = None):
    blocked, ready, _ = _registries()
    base = history_model.build_history(blocked, history_id="d494-history", snapshot_id="blocked")
    candidate = history_model.append_history(base, ready, snapshot_id="ready", expected_head=base.entries[-1].content_address)
    diff = diff_model.build_diff(base, candidate, diff_id="d494-diff")

    def run(suffix: str, maximum: int):
        policy = runtime_model.build_policy(
            f"d494-{suffix}-policy", diff.diff_id, minimum_items=2, maximum_added=maximum,
            maximum_removed=0, maximum_changed=0, allowed_directions=("improved",),
            require_accepted=True, require_state_change=True, allow_unchanged=True,
        )
        return runtime_model.run_runtime(diff, runtime_id=f"d494-{suffix}", policy=policy)

    strict = run("strict", strict_added)
    release = run("release", release_added)
    strict_audit = runtime_audit_model.audit_runtime(strict, diff)
    release_audit = runtime_audit_model.audit_runtime(release, diff)
    query = query_model.query_runtime(release, resources=query_resources or query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, release)
    bundle = archive_model.build_archive(diff, strict, strict_audit, release, release_audit, query, query_audit, bundle_id="d494-test-bundle") if make_bundle else None
    return diff, strict, strict_audit, release, release_audit, query, query_audit, bundle


def _rewrite_zip(raw: bytes, *, renamed: str | None = None, changed: str | None = None) -> bytes:
    with zipfile.ZipFile(io.BytesIO(raw), "r") as source:
        members = [(item.filename, source.read(item), item) for item in source.infolist()]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as target:
        for name, payload, original in members:
            if name == renamed:
                name = "../" + name
            if name == changed:
                payload += b" "
            info = zipfile.ZipInfo(name, date_time=original.date_time)
            info.create_system = original.create_system
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = original.external_attr
            target.writestr(info, payload)
    return output.getvalue()


class D494ReleaseEvidenceArchiveTests(unittest.TestCase):
    def test_deterministic_archive_round_trip_and_independent_audit(self) -> None:
        *_, bundle = _inputs()
        another = _inputs()[-1]
        encoded = archive_model.archive_bytes(bundle)
        self.assertEqual(encoded, archive_model.archive_bytes(another))
        self.assertEqual(bundle.manifest.state, "ready")
        self.assertEqual(bundle.manifest.file_count, len(archive_model.FILE_NAMES))
        self.assertEqual(archive_audit_model.audit_archive(bundle).passed_count, 12)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.zip"
            archive_model.persist_archive(bundle, path)
            loaded = archive_model.load_archive(path)
            self.assertEqual(loaded.content_address, bundle.content_address)
            self.assertEqual(archive_model.archive_bytes(loaded), encoded)
            self.assertTrue(archive_audit_model.audit_archive(loaded).accepted)
            with self.assertRaises(ValidationError):
                archive_model.persist_archive(bundle, path)

    def test_payload_tamper_and_unsafe_member_are_rejected(self) -> None:
        *_, bundle = _inputs()
        raw = archive_model.archive_bytes(bundle)
        changed = _rewrite_zip(raw, changed="runtime/release.json")
        unsafe = _rewrite_zip(raw, renamed="report.md")
        with tempfile.TemporaryDirectory() as temporary:
            changed_path = Path(temporary) / "changed.zip"
            unsafe_path = Path(temporary) / "unsafe.zip"
            changed_path.write_bytes(changed)
            unsafe_path.write_bytes(unsafe)
            with self.assertRaises(ValidationError):
                archive_model.load_archive(changed_path)
            with self.assertRaises(ValidationError):
                archive_model.load_archive(unsafe_path)

    def test_weaker_strict_policy_is_not_admitted(self) -> None:
        diff, strict, strict_audit, release, release_audit, query, query_audit, _ = _inputs(strict_added=2, make_bundle=False)
        self.assertEqual(strict.policy.maximum_added, 2)
        self.assertEqual(release.policy.maximum_added, 1)
        with self.assertRaises(ValidationError):
            archive_model.build_archive(diff, strict, strict_audit, release, release_audit, query, query_audit)

    def test_archive_contains_only_redacted_comparison_summary(self) -> None:
        *_, bundle = _inputs()
        members = dict(zip(archive_model.FILE_NAMES, bundle.payloads, strict=True))
        archive_payload = b"".join(bundle.payloads)
        self.assertNotIn(b"left_snapshot", archive_payload)
        self.assertNotIn(b"right_snapshot", archive_payload)
        self.assertNotIn(b"C:\\Users\\", archive_payload)
        self.assertNotIn(b"source_zip", archive_payload)
        self.assertIn(b"diff_address", members["comparison/diff-summary.json"])

    def test_filtered_query_cannot_mark_evidence_release_ready(self) -> None:
        *_, bundle = _inputs(query_resources=("checks",))
        self.assertEqual(bundle.manifest.state, "blocked")
        self.assertFalse(bundle.manifest.release_ready)
        audit = archive_audit_model.audit_archive(bundle)
        self.assertTrue(audit.accepted)
        self.assertEqual((audit.passed_count, audit.check_count), (12, 12))


if __name__ == "__main__":
    unittest.main()
