"""Adversarial tests for deterministic cross-run portfolio releases."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.portfolio_release import (
    build_portfolio_release,
    verify_portfolio_release_bundle,
    write_portfolio_release_bundle,
)
from glio_noncode.portfolio_release_contracts import PortfolioArtifactKind, PortfolioReleaseState
from glio_noncode.portfolio_release_lineage import (
    build_portfolio_release_lineage,
    lineage_descendants,
    lineage_for_run,
)
from glio_noncode.portfolio_release_observability import (
    build_portfolio_release_observability,
    portfolio_release_events_csv,
    portfolio_release_metrics_csv,
)
from glio_noncode.portfolio_release_query import (
    diff_portfolio_releases,
    export_portfolio_release_summary_csv,
    load_portfolio_release_bundle,
    query_portfolio_release,
)
from glio_noncode.portfolio_release_runtime import (
    evaluate_portfolio_release_quality,
    replay_portfolio_release,
    run_portfolio_release,
)
from glio_noncode.portfolio_release_schema import (
    portfolio_release_schema,
    validate_portfolio_release_manifest,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest

AS_OF = "2026-09-01T12:00:00Z"


def accepted_review(case_id: str, hypothesis_id: str, claim_ids: tuple[str, ...], review_id: str) -> ReviewDecision:
    return ReviewDecision(
        review_id=review_id,
        case_id=case_id,
        reviewer="portfolio-release-reviewer",
        state=ReviewState.ACCEPTED,
        reviewed_hypothesis_ids=(hypothesis_id,),
        rationale="The cross-run handoff preserves research-only review evidence.",
        checked_claim_ids=claim_ids,
    )


class PortfolioReleaseTests(unittest.TestCase):
    def _runtime(self, directory: str) -> tuple[CaseRuntime, object, object]:
        runtime = CaseRuntime(directory)
        pending = runtime.evaluate(fixture_manifest())
        reviewed_manifest = replace(
            fixture_manifest(),
            case_id="portfolio-release-case-002",
            requested_by="portfolio-release-requester-002",
        )
        reviewed = runtime.evaluate(reviewed_manifest)
        runtime.review_run(
            reviewed.run_id,
            accepted_review(
                reviewed.case_id,
                reviewed.hypotheses[0].hypothesis_id,
                tuple(item.evidence_id for item in reviewed.evidence),
                "portfolio-release-review-002",
            ),
        )
        return runtime, pending, reviewed

    def test_ready_release_contains_namespaced_member_closures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, reviewed = self._runtime(directory)
            bundle = build_portfolio_release(
                runtime,
                run_ids=(reviewed.run_id,),
                as_of=AS_OF,
                include_blocked=False,
            )
            self.assertTrue(bundle.accepted)
            self.assertEqual(bundle.state, PortfolioReleaseState.READY)
            self.assertEqual(bundle.member_count, 1)
            self.assertEqual(bundle.ready_member_count, 1)
            self.assertEqual(bundle.failed_check_ids, ())
            self.assertTrue(any(item.relative_path.endswith("/dossier/release.json") for item in bundle.artifacts))
            self.assertTrue(any(item.relative_path.endswith("/workspace/release.json") for item in bundle.artifacts))
            self.assertTrue(any(item.relative_path == "portfolio-checks.json" for item in bundle.artifacts))
            self.assertTrue(all(item.content_address.startswith("portfolio-release-artifact:") for item in bundle.artifacts))
            serialized = json.dumps(bundle.to_dict(), sort_keys=True).lower()
            for forbidden in (
                "subject_id",
                "sample_id",
                "agent_id",
                "agent_name",
                "assistant_id",
                "generated_by",
                "model_name",
                "author_name",
                "programming_language",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_write_verify_reopens_exact_bytes_and_rejects_extra_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, reviewed = self._runtime(directory)
            bundle = build_portfolio_release(runtime, run_ids=(reviewed.run_id,), as_of=AS_OF)
            destination = Path(directory) / "portfolio-release"
            write_portfolio_release_bundle(bundle, destination)
            verification = verify_portfolio_release_bundle(destination)
            self.assertTrue(verification.accepted)
            self.assertTrue(verification.manifest_version_valid)
            self.assertTrue(verification.manifest_address_valid)
            self.assertTrue(verification.public_boundary_valid)
            self.assertTrue(verification.path_safety_valid)
            self.assertEqual(verification.artifact_count, bundle.artifact_count)
            self.assertEqual(verification.verified_artifact_count, bundle.artifact_count)
            self.assertEqual(verification.member_count, 1)
            self.assertEqual(verification.verified_member_count, 1)
            self.assertEqual(verification.failed_artifact_ids, ())
            (destination / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            tampered = verify_portfolio_release_bundle(destination)
            self.assertFalse(tampered.accepted)
            self.assertEqual(tampered.unexpected_paths, ("unexpected.txt",))

    def test_blocked_member_is_preserved_and_package_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, pending, _ = self._runtime(directory)
            bundle = build_portfolio_release(runtime, run_ids=(pending.run_id,), as_of=AS_OF)
            self.assertFalse(bundle.accepted)
            self.assertEqual(bundle.state, PortfolioReleaseState.BLOCKED)
            self.assertEqual(bundle.member_count, 1)
            self.assertEqual(bundle.members[0].state, PortfolioReleaseState.BLOCKED)
            self.assertIn("dossier:review-accepted", bundle.members[0].failed_check_ids)
            destination = Path(directory) / "blocked-release"
            write_portfolio_release_bundle(bundle, destination)
            verification = verify_portfolio_release_bundle(destination)
            self.assertFalse(verification.accepted)
            self.assertEqual(verification.failed_artifact_ids, ())
            self.assertEqual(verification.failed_member_ids, ())
            self.assertEqual(verification.unexpected_paths, ())

    def test_query_facets_and_csv_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, reviewed = self._runtime(directory)
            bundle = build_portfolio_release(runtime, run_ids=(reviewed.run_id,), as_of=AS_OF)
            first_destination = Path(directory) / "one"
            second_destination = Path(directory) / "two"
            write_portfolio_release_bundle(bundle, first_destination)
            write_portfolio_release_bundle(bundle, second_destination)
            result = query_portfolio_release(
                first_destination,
                run_id=reviewed.run_id,
                artifact_kind=PortfolioArtifactKind.WORKSPACE,
                include_payloads=True,
            )
            self.assertTrue(result.accepted)
            self.assertEqual(result.total_members, 1)
            self.assertGreater(len(result.artifacts), 0)
            self.assertTrue(all(item.payload for item in result.artifacts))
            self.assertIn("run_id,case_id,state", export_portfolio_release_summary_csv(result))
            second = query_portfolio_release(second_destination, case_id=reviewed.case_id)
            self.assertEqual(result.members[0].run_id, second.members[0].run_id)
            self.assertEqual(result.members[0].content_address, second.members[0].content_address)
            with self.assertRaises(ValidationError):
                query_portfolio_release(first_destination, limit=0)
            with self.assertRaises(ValidationError):
                query_portfolio_release(first_destination, artifact_kind="unknown")

    def test_diff_detects_added_and_removed_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, pending, reviewed = self._runtime(directory)
            one = build_portfolio_release(runtime, run_ids=(pending.run_id,), as_of=AS_OF)
            two = build_portfolio_release(runtime, run_ids=(reviewed.run_id,), as_of=AS_OF)
            left = Path(directory) / "left"
            right = Path(directory) / "right"
            write_portfolio_release_bundle(one, left)
            write_portfolio_release_bundle(two, right)
            diff = diff_portfolio_releases(left, right)
            self.assertEqual(diff.added_run_ids, (reviewed.run_id,))
            self.assertEqual(diff.removed_run_ids, (pending.run_id,))
            self.assertEqual(diff.common_run_ids, ())
            self.assertTrue(diff.accepted)
            self.assertTrue(diff.content_address.startswith("portfolio-release-diff:"))

    def test_staged_runtime_quality_and_replay_close(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, reviewed = self._runtime(directory)
            execution = run_portfolio_release(
                runtime,
                run_ids=(reviewed.run_id,),
                as_of=AS_OF,
            )
            self.assertTrue(execution.accepted)
            self.assertEqual(execution.stage_count, 5)
            self.assertEqual(tuple(item.stage_id for item in execution.stages), (
                "portfolio-selected",
                "members-assembled",
                "artifact-closure-verified",
                "public-boundary-verified",
                "release-addressed",
            ))
            self.assertTrue(execution.quality.accepted)
            self.assertEqual(execution.quality.failed_checks, 0)
            replay = replay_portfolio_release(runtime, execution)
            self.assertTrue(replay["same_address"])
            self.assertEqual(replay["previous_address"], replay["replay_address"])
            direct_quality = evaluate_portfolio_release_quality(execution.bundle)
            self.assertEqual(direct_quality.content_address, execution.quality.content_address)

    def test_lineage_observability_and_schema_close_without_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, reviewed = self._runtime(directory)
            bundle = build_portfolio_release(runtime, run_ids=(reviewed.run_id,), as_of=AS_OF)
            destination = Path(directory) / "release"
            write_portfolio_release_bundle(bundle, destination)
            loaded = load_portfolio_release_bundle(destination)
            self.assertEqual(loaded.content_address, bundle.content_address)
            self.assertTrue(all(not item.payload for item in loaded.artifacts))

            lineage = build_portfolio_release_lineage(loaded)
            self.assertTrue(lineage.accepted)
            self.assertEqual(lineage.member_count, 1)
            self.assertGreater(lineage.node_count, lineage.member_count)
            self.assertGreater(lineage.edge_count, lineage.member_count)
            descendants = lineage_descendants(lineage, f"member:{reviewed.run_id}")
            self.assertTrue(any(item.kind.value == "artifact" for item in descendants))
            focused = lineage_for_run(lineage, reviewed.run_id)
            self.assertTrue(focused["accepted"])
            self.assertEqual(focused["run_id"], reviewed.run_id)

            observability = build_portfolio_release_observability(loaded)
            self.assertTrue(observability.accepted)
            self.assertGreaterEqual(observability.event_count, bundle.member_count + len(bundle.checks) + 2)
            self.assertGreaterEqual(observability.metric_count, 10)
            self.assertIn("metric_id,value,unit", portfolio_release_metrics_csv(observability))
            self.assertIn("sequence,event_id,stage", portfolio_release_events_csv(observability))

            schema = portfolio_release_schema()
            self.assertEqual(schema["properties"]["release_version"]["const"], "portfolio-release-v1")
            manifest = json.loads((destination / "release.json").read_text(encoding="utf-8"))
            schema_validation = validate_portfolio_release_manifest(manifest)
            self.assertTrue(schema_validation.accepted)
            manifest["member_count"] = 999
            invalid = validate_portfolio_release_manifest(manifest)
            self.assertFalse(invalid.accepted)
            self.assertIn("member-count", invalid.failed_check_ids)

    def test_unknown_requested_run_fails_closed_without_silent_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, reviewed = self._runtime(directory)
            bundle = build_portfolio_release(
                runtime,
                run_ids=(reviewed.run_id, "run-does-not-exist"),
                as_of=AS_OF,
            )
            self.assertFalse(bundle.accepted)
            self.assertIn("requested-runs-found", bundle.failed_check_ids)
            self.assertEqual(bundle.member_count, 1)

    def test_tampered_json_artifact_fails_public_and_address_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, reviewed = self._runtime(directory)
            bundle = build_portfolio_release(runtime, run_ids=(reviewed.run_id,), as_of=AS_OF)
            destination = Path(directory) / "release"
            write_portfolio_release_bundle(bundle, destination)
            target = destination / "portfolio-members.json"
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload[0]["agent_name"] = "forbidden"
            target.write_text(json.dumps(payload), encoding="utf-8")
            verification = verify_portfolio_release_bundle(destination)
            self.assertFalse(verification.accepted)
            self.assertFalse(verification.public_boundary_valid)
            self.assertIn("portfolio:members", verification.failed_artifact_ids)

    def test_cli_http_and_runtime_surfaces_share_the_same_release_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, reviewed = self._runtime(directory)
            destination = Path(directory) / "cli-release"
            payload_path = Path(directory) / "cli-release.json"
            verification_path = Path(directory) / "cli-verification.json"
            self.assertEqual(
                main(
                    [
                        "portfolio-release",
                        "--data-root",
                        directory,
                        "--run-id",
                        reviewed.run_id,
                        "--release-ready-only",
                        "--as-of",
                        AS_OF,
                        "--destination",
                        str(destination),
                        "--output",
                        str(payload_path),
                    ]
                ),
                0,
            )
            cli_payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertTrue(cli_payload["accepted"])
            self.assertEqual(cli_payload["content_address"], json.loads((destination / "release.json").read_text(encoding="utf-8"))["content_address"])
            self.assertEqual(
                main(
                    [
                        "portfolio-release-verify",
                        str(destination),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            runtime_payload_path = Path(directory) / "runtime.json"
            self.assertEqual(
                main(
                    [
                        "portfolio-release-runtime",
                        "--data-root",
                        directory,
                        "--run-id",
                        reviewed.run_id,
                        "--release-ready-only",
                        "--as-of",
                        AS_OF,
                        "--output",
                        str(runtime_payload_path),
                    ]
                ),
                0,
            )
            runtime_payload = json.loads(runtime_payload_path.read_text(encoding="utf-8"))
            self.assertTrue(runtime_payload["accepted"])

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "GET",
                    f"/v1/portfolio/release?run_id={reviewed.run_id}&release_ready_only=true&as_of={AS_OF}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_payload = json.loads(response.read())
                self.assertTrue(api_payload["accepted"])
                self.assertEqual(api_payload["content_address"], cli_payload["content_address"])
                connection.request(
                    "GET",
                    f"/v1/portfolio/release/lineage?run_id={reviewed.run_id}&focus_run_id={reviewed.run_id}&release_ready_only=true&as_of={AS_OF}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                lineage_payload = json.loads(response.read())
                self.assertTrue(lineage_payload["accepted"])
                self.assertEqual(lineage_payload["run_id"], reviewed.run_id)
                connection.request(
                    "GET",
                    f"/v1/portfolio/release/observability?run_id={reviewed.run_id}&release_ready_only=true&as_of={AS_OF}",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                observability_payload = json.loads(response.read())
                self.assertTrue(observability_payload["accepted"])
                connection.request("GET", "/v1/portfolio/release/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                schema_payload = json.loads(response.read())
                self.assertEqual(schema_payload["properties"]["release_version"]["const"], "portfolio-release-v1")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
