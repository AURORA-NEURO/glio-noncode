from __future__ import annotations

import copy
import json
import tempfile
import unicodedata
import unittest
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import fields, replace
from types import MappingProxyType
from typing import Any, ClassVar, cast
from unittest.mock import patch

import glio_noncode.reports as reports_module
import glio_noncode.validation as validation_module
from glio_noncode.data_sources import FetchReceipt, FetchStatus
from glio_noncode.errors import ValidationError
from glio_noncode.models import Dossier, EvidenceState
from glio_noncode.reports import (
    DEFAULT_REPORT_LIMITS,
    RENDERED_REPORT_ADDRESS_PREFIX,
    REPORT_ADDRESS_PREFIX,
    REPORT_PAYLOAD_ADDRESS_PREFIX,
    SUMMARY_ADDRESS_PREFIX,
    DossierReport,
    DossierSummary,
    RenderedReport,
    ReportAudience,
    ReportFormat,
    ReportLimits,
    build_report,
    render_json,
    render_markdown,
    render_report,
    render_report_json,
    render_report_markdown,
    report_capabilities,
    summarize,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import canonical_bytes, canonical_json, content_hash

from .helpers import fixture_manifest


def _rehydrate(raw: dict[str, Any]) -> Dossier:
    raw["content_address"] = content_hash(
        {key: value for key, value in raw.items() if key != "content_address"}
    )
    return Dossier.from_dict(raw)


def _minimal_receipt() -> dict[str, Any]:
    return FetchReceipt(
        source_id="A",
        source_version="1",
        url="http://a",
        request_hash="sha256:" + "0" * 64,
        response_hash="sha256:" + "0" * 64,
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at="0001-01-01T00:00:00+00:00",
        elapsed_seconds=None,
        cache_expires_at=None,
    ).to_dict()


def _json_string_characters(value: object) -> int:
    if type(value) is str:
        return len(value)
    if isinstance(value, Mapping):
        return sum(
            _json_string_characters(key) + _json_string_characters(item)
            for key, item in value.items()
        )
    if isinstance(value, Sequence):
        return sum(_json_string_characters(item) for item in value)
    return 0


def _legacy_markdown_text_reference(value: str) -> str:
    output: list[str] = []
    previous_space = False
    for character in value:
        if character in "\r\n\t" or unicodedata.category(character).startswith("C"):
            if not previous_space:
                output.append(" ")
                previous_space = True
            continue
        previous_space = character.isspace()
        if character == "&":
            output.append("&amp;")
        elif character == "<":
            output.append("&lt;")
        elif character == ">":
            output.append("&gt;")
        elif character in "\\`*_{}[]()#!|":
            output.extend(("\\", character))
        else:
            output.append(character)
    return "".join(output).strip()


def _legacy_markdown_reference(dossier: Dossier) -> str:
    summary = summarize(dossier)
    lifecycle, _ = reports_module._lifecycle(dossier)
    escape = _legacy_markdown_text_reference
    lines = [
        f"# Research Dossier: {escape(dossier.case_id)}",
        "",
        f"- Status: {escape(dossier.status.value)}",
        f"- Run: {escape(dossier.run_id)}",
        f"- Research-use only: {str(dossier.research_use_only).lower()}",
        f"- Policy: {escape(dossier.policy_version)}",
        f"- Input: {escape(dossier.input_address)}",
        f"- Content: {escape(dossier.content_address)}",
        f"- Summary: {escape(summary.content_address)}",
        f"- Release gate valid: {str(summary.release_gate_valid).lower()}",
        "",
        "## Evidence state summary",
        "",
    ]
    lines.extend(f"- {escape(state)}: {count}" for state, count in summary.evidence_state_counts)
    lines.extend(
        [
            f"- Active: {summary.active_claim_count}",
            f"- Superseded: {summary.superseded_claim_count}",
            f"- Orphan: {summary.orphan_claim_count}",
            "",
            "## Hypotheses",
            "",
        ]
    )
    hypotheses = sorted(
        dossier.hypotheses,
        key=lambda item: (-item.support, item.uncertainty, item.hypothesis_id),
    )
    for index, hypothesis in enumerate(hypotheses, start=1):
        lines.extend(
            [
                f"### {index}. {escape(hypothesis.hypothesis_id)}",
                f"- Variant: {escape(hypothesis.variant_id)}",
                f"- Element: {escape(hypothesis.element_id)}",
                f"- Gene: {escape(hypothesis.gene_id)}",
                f"- State: {escape(hypothesis.state_id)}",
                f"- Support: {canonical_json(hypothesis.support)}",
                f"- Uncertainty: {canonical_json(hypothesis.uncertainty)}",
                f"- Mechanism: {escape(hypothesis.mechanism)}",
                f"- Missing evidence: {len(hypothesis.missing_evidence)}",
                f"- Negative evidence: {len(hypothesis.negative_evidence)}",
                "",
            ]
        )
        for edge in hypothesis.edges:
            lines.append(
                "  - "
                f"{escape(edge.edge_type.value)} "
                f"{escape(edge.source_id)} → {escape(edge.target_id)}; "
                f"support {canonical_json(edge.support)}; "
                f"uncertainty {canonical_json(edge.uncertainty)}"
            )
        lines.append("")
    lines.extend(["## Evidence ledger", ""])
    for claim in dossier.evidence:
        lines.append(
            "- "
            f"{escape(claim.evidence_id)} "
            f"[{lifecycle[claim.evidence_id]}] "
            f"{escape(claim.state.value)} "
            f"{escape(claim.channel)}: {escape(claim.summary)}"
        )
    lines.extend(["", "## Validation routes", ""])
    experiments = sorted(
        dossier.experiments,
        key=lambda item: (-item.priority, item.option_id),
    )
    for option in experiments:
        lines.extend(
            [
                "- "
                f"{escape(option.option_id)} "
                f"{escape(option.assay.value)} priority "
                f"{canonical_json(option.priority)}",
                "  - Readouts: " + ", ".join(escape(item) for item in option.readouts),
                "  - Controls: " + ", ".join(escape(item) for item in option.controls),
                "  - Limitations: "
                + ", ".join(escape(item) for item in option.limitations),
            ]
        )
    if dossier.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {escape(warning)}" for warning in dossier.warnings)
    lines.append("")
    return "\n".join(lines)


class ReportsHardeningTests(unittest.TestCase):
    _directory: ClassVar[tempfile.TemporaryDirectory[str]]
    dossier: ClassVar[Dossier]

    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        cls.dossier = CaseRuntime(cls._directory.name).evaluate(fixture_manifest())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_reporting_requires_an_exact_valid_addressed_dossier(self) -> None:
        with self.assertRaises(ValidationError):
            summarize(cast(Any, object()))
        with self.assertRaises(ValidationError):
            render_markdown(cast(Any, object()))

        forged = replace(self.dossier, content_address="sha256:" + "0" * 64)
        with self.assertRaises(ValidationError):
            summarize(forged)
        with self.assertRaises(ValidationError):
            render_json(forged)

    def test_reporting_accepts_the_maximal_live_source_closure(self) -> None:
        source_addresses = tuple(f"sha256:{index:064x}" for index in range(3_006))
        pending = replace(
            self.dossier,
            source_bundle_addresses=source_addresses,
            content_address="pending",
        )
        body = pending.to_dict()
        body.pop("content_address")
        expanded = replace(pending, content_address=content_hash(body))

        self.assertEqual(summarize(expanded).dossier_address, expanded.content_address)

        for rebound in (1, 1_000_000):
            with self.subTest(rebound=rebound), patch.object(
                reports_module,
                "MAX_REPORT_SOURCE_BUNDLES",
                rebound,
            ):
                self.assertEqual(
                    summarize(expanded).dossier_address,
                    expanded.content_address,
                )

    def test_source_receipt_capacity_is_independent_of_generic_sequence_limit(self) -> None:
        receipt = FetchReceipt(
            source_id="SRC-REPORT-RECEIPT",
            source_version="1",
            url="https://example.test/report-receipt",
            request_hash=content_hash({"request": "report-receipt"}),
            response_hash=content_hash({"response": "report-receipt"}),
            status=FetchStatus.FETCHED,
            http_status=200,
            attempts=1,
            retrieved_at="2026-09-08T00:00:00+00:00",
            elapsed_seconds=0.0,
            cache_expires_at=None,
        ).to_dict()
        receipt_count = 34_443
        one_receipt = replace(self.dossier, source_receipts=(receipt,))
        expanded = copy.copy(self.dossier)
        object.__setattr__(
            expanded,
            "source_receipts",
            (one_receipt.source_receipts[0],) * receipt_count,
        )
        object.__setattr__(
            expanded,
            "source_bundle_addresses",
            (content_hash({"bundle": "report-receipt"}),),
        )
        body = expanded.to_dict()
        body.pop("content_address")
        object.__setattr__(expanded, "content_address", content_hash(body))

        self.assertGreater(receipt_count, 34_442)
        self.assertEqual(summarize(expanded).dossier_address, expanded.content_address)
        self.assertEqual(
            cast(dict[str, int], report_capabilities()["hard_limits"])["source_receipts"],
            256_000,
        )
        with self.assertRaisesRegex(ValidationError, "validation_limit_exceeded"):
            summarize(expanded, limits=ReportLimits(max_source_receipts=20_000))

        warning_pending = replace(
            self.dossier,
            warnings=tuple(f"report-warning-{index}" for index in range(20_001)),
            content_address="pending",
        )
        warning_body = warning_pending.to_dict()
        warning_body.pop("content_address")
        warning_expanded = replace(
            warning_pending,
            content_address=content_hash(warning_body),
        )
        with self.assertRaisesRegex(ValidationError, "validation_limit_exceeded"):
            summarize(warning_expanded)

    def test_legacy_report_limit_positions_and_receipt_coupling_are_preserved(self) -> None:
        legacy_names = (
            "max_hypotheses",
            "max_evidence_claims",
            "max_experiments",
            "max_edges_per_hypothesis",
            "max_total_edges",
            "max_sequence_items",
            "max_issue_codes",
            "max_text_characters",
            "max_total_characters",
            "max_dossier_bytes",
            "max_summary_bytes",
            "max_markdown_bytes",
            "max_rendered_report_bytes",
        )
        legacy_values = (
            100,
            200,
            50,
            10,
            100,
            123,
            8,
            1_000,
            2_000,
            4_096,
            2_048,
            1_024,
            2_048,
        )
        limits = ReportLimits(*legacy_values)

        self.assertEqual(tuple(field.name for field in fields(ReportLimits))[:13], legacy_names)
        self.assertEqual(
            tuple(getattr(limits, name) for name in legacy_names),
            legacy_values,
        )
        self.assertIsNone(limits.max_source_receipts)
        self.assertEqual(
            reports_module._validation_limits(limits).max_source_receipts,
            min(limits.max_sequence_items, reports_module.MAX_REPORT_SOURCE_RECEIPTS),
        )

    def test_explicit_and_default_source_receipt_limits_are_independent(self) -> None:
        custom = ReportLimits(max_sequence_items=7)
        explicit = ReportLimits(max_sequence_items=7, max_source_receipts=23)

        self.assertIsNone(custom.max_source_receipts)
        self.assertEqual(reports_module._validation_limits(custom).max_source_receipts, 7)
        self.assertEqual(explicit.max_source_receipts, 23)
        self.assertEqual(reports_module._validation_limits(explicit).max_source_receipts, 23)
        self.assertEqual(
            DEFAULT_REPORT_LIMITS.max_source_receipts,
            reports_module.MAX_REPORT_SOURCE_RECEIPTS,
        )
        self.assertEqual(
            reports_module._validation_limits(DEFAULT_REPORT_LIMITS).max_source_receipts,
            reports_module.MAX_REPORT_SOURCE_RECEIPTS,
        )

        for invalid in (0, -1, True, reports_module.MAX_REPORT_SOURCE_RECEIPTS + 1):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                ReportLimits(max_source_receipts=cast(Any, invalid))

    def test_full_receipt_boundary_is_reachable_through_report_limits(self) -> None:
        receipt = _minimal_receipt()
        receipt_count = reports_module.MAX_REPORT_SOURCE_RECEIPTS
        pending = replace(
            self.dossier,
            source_bundle_addresses=("sha256:" + "1" * 64,),
            content_address="pending",
        )
        body = pending.to_dict()
        body.pop("content_address")
        base = replace(pending, content_address=content_hash(body))
        raw = base.to_dict()
        self.assertEqual(raw["source_receipts"], [])

        receipt_bytes = len(canonical_bytes(receipt))
        receipt_array_bytes = 2 + receipt_count * receipt_bytes + receipt_count - 1
        full_payload_bytes = len(canonical_bytes(raw)) - len(b"[]") + receipt_array_bytes
        full_string_characters = (
            _json_string_characters(raw)
            + receipt_count * _json_string_characters(receipt)
        )
        limits = DEFAULT_REPORT_LIMITS
        self.assertLessEqual(full_payload_bytes, limits.max_dossier_bytes)
        self.assertLessEqual(full_string_characters, limits.max_total_characters)
        self.assertEqual(limits.max_total_characters, 134_217_728)

        one_receipt = replace(base, source_receipts=(receipt,))
        boundary = copy.copy(base)
        object.__setattr__(
            boundary,
            "source_receipts",
            (one_receipt.source_receipts[0],) * receipt_count,
        )
        validation_limits = reports_module._validation_limits(limits)
        validation_module._dossier_preflight(boundary, validation_limits)
        validation_module._measure_model(
            boundary,
            validation_limits,
            compact_source_receipts=b"\x01" * receipt_count,
        )

        hard_limits = cast(dict[str, int], report_capabilities()["hard_limits"])
        self.assertEqual(hard_limits["source_receipts"], receipt_count)
        self.assertEqual(hard_limits["structured_nodes"], limits.max_structured_nodes)
        self.assertEqual(hard_limits["total_characters"], limits.max_total_characters)

    def test_summary_is_strict_addressed_and_replay_verifiable(self) -> None:
        summary = summarize(self.dossier)
        self.assertTrue(summary.content_address.startswith(SUMMARY_ADDRESS_PREFIX + ":"))
        self.assertEqual(DossierSummary.from_dict(summary.to_dict()), summary)
        self.assertTrue(summary.verify(self.dossier))
        self.assertFalse(summary.verify(replace(self.dossier, case_id="different-case")))

        unknown = summary.to_dict()
        unknown["unexpected"] = True
        with self.assertRaises(ValidationError):
            DossierSummary.from_dict(unknown)
        with self.assertRaises(ValidationError):
            DossierSummary.from_dict(cast(Any, MappingProxyType(summary.to_dict())))

        changed = summary.to_dict()
        changed["warning_count"] = cast(int, changed["warning_count"]) + 1
        with self.assertRaises(ValidationError):
            DossierSummary.from_dict(changed)

    def test_summary_conserves_all_evidence_and_lifecycle_states(self) -> None:
        raw = self.dossier.to_dict()
        old_claim = dict(raw["evidence"][0])
        old_claim.update(
            {
                "evidence_id": "report-orphan-old",
                "edge_id": "report-orphan-edge",
                "state": "absent",
                "score": None,
                "depends_on": [],
                "supersedes": None,
                "summary": "explicit absent orphan claim",
            }
        )
        current_claim = dict(raw["evidence"][0])
        current_claim.update(
            {
                "evidence_id": "report-orphan-current",
                "edge_id": "report-orphan-edge",
                "depends_on": [],
                "supersedes": "report-orphan-old",
                "summary": "current orphan claim",
            }
        )
        raw["evidence"].extend([old_claim, current_claim])
        dossier = _rehydrate(raw)

        summary = summarize(dossier)
        state_counts = dict(summary.evidence_state_counts)
        self.assertEqual(
            tuple(state_counts),
            tuple(state.value for state in EvidenceState),
        )
        self.assertEqual(sum(state_counts.values()), summary.evidence_count)
        self.assertEqual(
            summary.supported_claim_count
            + summary.negative_claim_count
            + summary.missing_claim_count,
            summary.evidence_count,
        )
        self.assertEqual(
            summary.active_claim_count
            + summary.superseded_claim_count
            + summary.orphan_claim_count,
            summary.evidence_count,
        )
        self.assertEqual(state_counts["absent"], 1)
        self.assertGreaterEqual(summary.superseded_claim_count, 1)
        self.assertGreaterEqual(summary.orphan_claim_count, 1)

    def test_ranking_is_deterministic_and_independent_of_storage_order(self) -> None:
        raw = self.dossier.to_dict()
        duplicate = dict(raw["hypotheses"][0])
        duplicate["hypothesis_id"] = "000-report-ranking-tie"
        raw["hypotheses"].append(duplicate)
        raw["hypotheses"].reverse()
        raw["experiments"].reverse()
        dossier = _rehydrate(raw)

        expected_hypothesis = min(
            raw["hypotheses"],
            key=lambda item: (-item["support"], item["uncertainty"], item["hypothesis_id"]),
        )["hypothesis_id"]
        expected_experiment = min(
            dossier.experiments,
            key=lambda item: (-item.priority, item.option_id),
        ).option_id
        first = summarize(dossier)
        second = summarize(dossier)
        self.assertEqual(first, second)
        self.assertEqual(first.top_hypothesis_id, expected_hypothesis)
        self.assertEqual(first.recommended_experiment_id, expected_experiment)

    def test_limits_are_downward_only_and_revalidated_at_use(self) -> None:
        with self.assertRaises(ValidationError):
            ReportLimits(
                max_hypotheses=DEFAULT_REPORT_LIMITS.max_hypotheses + 1,
            )

        tampered = ReportLimits()
        object.__setattr__(
            tampered,
            "max_hypotheses",
            DEFAULT_REPORT_LIMITS.max_hypotheses + 1,
        )
        with self.assertRaises(ValidationError):
            summarize(self.dossier, limits=tampered)
        with self.assertRaises(ValidationError):
            render_markdown(self.dossier, limits=ReportLimits(max_markdown_bytes=1))

        raw = self.dossier.to_dict()
        duplicate = dict(raw["hypotheses"][0])
        duplicate["hypothesis_id"] = "report-limit-hypothesis"
        raw["hypotheses"].append(duplicate)
        with self.assertRaises(ValidationError):
            summarize(_rehydrate(raw), limits=ReportLimits(max_hypotheses=1))

        with self.assertRaisesRegex(ValidationError, "validation_limit_exceeded"):
            summarize(self.dossier, limits=ReportLimits(max_structured_nodes=1))

    def test_issue_code_cap_does_not_truncate_authoritative_gate_evaluation(self) -> None:
        raw = self.dossier.to_dict()
        raw["evidence"][0]["summary"] = "This asserts a diagnosis."
        dossier = _rehydrate(raw)
        ordinary = summarize(dossier)
        self.assertIn("policy_violation", ordinary.release_gate_issue_codes)
        self.assertIn("release_status_required", ordinary.release_gate_issue_codes)
        with self.assertRaisesRegex(ValidationError, "issue codes exceed"):
            summarize(dossier, limits=ReportLimits(max_issue_codes=1))

    def test_markdown_escapes_untrusted_text_and_rejects_invalid_utf8(self) -> None:
        raw = self.dossier.to_dict()
        raw["evidence"][0]["summary"] = (
            "claim\n# injected <script>alert(1)</script> [click](javascript:bad) `code`"
        )
        dossier = _rehydrate(raw)
        markdown = render_markdown(dossier)
        self.assertNotIn("\n# injected", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertNotIn("[click](javascript:bad)", markdown)
        self.assertIn("&lt;script&gt;", markdown)
        self.assertEqual(markdown.encode("utf-8").decode("utf-8"), markdown)

        hostile_claim = replace(self.dossier.evidence[0], summary="invalid \ud800 text")
        hostile = replace(
            self.dossier,
            evidence=(hostile_claim, *self.dossier.evidence[1:]),
        )
        with self.assertRaises(ValidationError):
            render_markdown(hostile)

    def test_incremental_markdown_is_byte_exact_with_the_legacy_renderer(self) -> None:
        expected = _legacy_markdown_reference(self.dossier)
        byte_count = len(expected.encode("utf-8"))

        self.assertEqual(render_markdown(self.dossier), expected)
        self.assertEqual(
            render_markdown(
                self.dossier,
                limits=replace(DEFAULT_REPORT_LIMITS, max_markdown_bytes=byte_count),
            ),
            expected,
        )
        with self.assertRaisesRegex(
            ValidationError,
            f"configured maximum of {byte_count - 1} bytes",
        ):
            render_markdown(
                self.dossier,
                limits=replace(DEFAULT_REPORT_LIMITS, max_markdown_bytes=byte_count - 1),
            )

    def test_incremental_writer_admits_escaping_and_joins_by_utf8_bytes(self) -> None:
        samples = (
            "",
            "   \r\n\t",
            "  leading and trailing\u2003",
            "a\r\n\x00b",
            "<&> \\`*_{}[]()#!|",
            "Unicode café → glioma",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                parity = reports_module._BoundedMarkdownWriter(1_024)
                parity.write_text(sample)
                self.assertEqual(parity.finish(), _legacy_markdown_text_reference(sample))

        exact = reports_module._BoundedMarkdownWriter(5)
        exact.write_text("&")
        self.assertEqual(exact.finish(), "&amp;")

        expansion_rejected = reports_module._BoundedMarkdownWriter(4)
        with self.assertRaisesRegex(ValidationError, "configured maximum of 4 bytes"):
            expansion_rejected.write_text("&")
        self.assertEqual(expansion_rejected.finish(), "")

        visited: list[str] = []

        def values() -> Iterator[str]:
            for value in ("a", "&", "must-not-be-visited"):
                visited.append(value)
                yield value

        joined = reports_module._BoundedMarkdownWriter(3)
        with self.assertRaisesRegex(ValidationError, "configured maximum of 3 bytes"):
            joined.write_joined_text(values())
        self.assertEqual(joined.finish(), "a, ")
        self.assertEqual(visited, ["a", "&"])

    def test_markdown_budget_exhaustion_does_not_escape_trailing_content(self) -> None:
        expanded_summary = "&" * 64
        trailing_warning = "markdown-trailing-content-canary"
        raw = self.dossier.to_dict()
        raw["evidence"][0]["summary"] = expanded_summary
        raw["warnings"].append(trailing_warning)
        dossier = _rehydrate(raw)
        complete = render_markdown(dossier)
        escaped_summary = reports_module._markdown_text(expanded_summary)
        summary_offset = complete.index(escaped_summary)
        limit = len(complete[:summary_offset].encode("utf-8")) + 4
        visited: list[str] = []
        original = reports_module._BoundedMarkdownWriter.write_text

        def tracked_write_text(
            writer: reports_module._BoundedMarkdownWriter,
            value: str,
        ) -> None:
            visited.append(value)
            original(writer, value)

        with patch.object(
            reports_module._BoundedMarkdownWriter,
            "write_text",
            tracked_write_text,
        ), self.assertRaisesRegex(
            ValidationError,
            f"configured maximum of {limit} bytes",
        ):
            render_markdown(
                dossier,
                limits=replace(DEFAULT_REPORT_LIMITS, max_markdown_bytes=limit),
            )
        self.assertIn(expanded_summary, visited)
        self.assertNotIn(trailing_warning, visited)

    def test_legacy_json_remains_the_full_canonical_dossier_export(self) -> None:
        self.assertEqual(json.loads(render_json(self.dossier)), self.dossier.to_dict())

    def test_public_projection_is_allowlisted_and_redacts_free_text_and_ids(self) -> None:
        canary = "PRIVATE-CANARY-CASE-AND-FREE-TEXT"
        raw = self.dossier.to_dict()
        raw["case_id"] = canary
        raw["policy_version"] = canary
        raw["warnings"].append(canary)
        raw["evidence"][0]["summary"] = canary
        dossier = _rehydrate(raw)

        public = build_report(dossier, audience=ReportAudience.PUBLIC)
        review = build_report(dossier, audience=ReportAudience.REVIEW)
        public_json = render_report_json(public)
        self.assertNotIn(canary, public_json)
        self.assertIn(canary, render_report_json(review))
        self.assertNotIn("case_id", public.projection)
        self.assertNotIn("run_id", public.projection)
        self.assertNotIn("top_hypothesis_id", public.projection)
        self.assertNotIn("recommended_experiment_id", public.projection)
        self.assertNotIn("input_address", public.projection)
        self.assertNotIn("event_head", public.projection)
        self.assertNotIn("policy_version", public.projection)
        self.assertTrue(public.projection["public_safe"])
        self.assertNotEqual(public.content_address, review.content_address)
        self.assertTrue(public.verify(dossier))
        self.assertTrue(review.verify(dossier))
        self.assertEqual(DossierReport.from_dict(public.to_dict()), public)

        public_markdown = render_report_markdown(public)
        self.assertNotIn(canary, public_markdown)
        self.assertNotIn("Top hypothesis", public_markdown)

    def test_report_and_rendered_envelopes_are_strict_and_content_addressed(self) -> None:
        report = build_report(self.dossier)
        self.assertTrue(report.content_address.startswith(REPORT_ADDRESS_PREFIX + ":"))
        for report_format in ReportFormat:
            rendered = render_report(report, format=report_format)
            self.assertTrue(
                rendered.content_address.startswith(RENDERED_REPORT_ADDRESS_PREFIX + ":")
            )
            self.assertTrue(
                rendered.payload_address.startswith(REPORT_PAYLOAD_ADDRESS_PREFIX + ":")
            )
            self.assertEqual(rendered.byte_count, len(rendered.payload.encode("utf-8")))
            self.assertEqual(RenderedReport.from_dict(rendered.to_dict()), rendered)
            self.assertTrue(rendered.verify(report))
            self.assertEqual(rendered, render_report(report, format=report_format))

            changed = rendered.to_dict()
            changed["payload"] = cast(str, changed["payload"]) + "tampered"
            with self.assertRaises(ValidationError):
                RenderedReport.from_dict(changed)

        with self.assertRaises(ValidationError):
            render_report(report, limits=ReportLimits(max_rendered_report_bytes=1))

    def test_public_report_rejects_extra_projection_fields_even_if_readdressed(self) -> None:
        report = build_report(self.dossier, audience="public")
        raw = report.to_dict()
        projection = cast(dict[str, Any], raw["projection"])
        projection["case_id"] = self.dossier.case_id
        body = {key: value for key, value in raw.items() if key != "content_address"}
        raw["content_address"] = content_hash(body, prefix=REPORT_ADDRESS_PREFIX)
        with self.assertRaises(ValidationError):
            DossierReport.from_dict(raw)


if __name__ == "__main__":
    unittest.main()
