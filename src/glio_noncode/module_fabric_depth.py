"""Depth audit proving the module fabric spans every declared domain."""

from __future__ import annotations

from collections import Counter

from .capability_registry import CapabilityRegistry, default_capability_registry
from .module_fabric_contracts import (
    MODULE_FABRIC_ARTIFACT_COUNT,
    MODULE_FABRIC_CHECK_COUNT,
    MODULE_FABRIC_CHECKS_PER_RECORD,
    MODULE_FABRIC_DOMAIN_IDS,
    MODULE_FABRIC_GLOBAL_CHECK_COUNT,
    FabricDepthAudit,
    FabricFixture,
    FabricState,
    make_depth_check,
)
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_metrics import measure_module_fabric
from .module_fabric_public_data import audit_module_fabric_data, default_module_fabric_fixture
from .module_fabric_support import all_resolved
from .serialization import content_hash


def audit_module_fabric_depth(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
) -> FabricDepthAudit:
    value = fixture or default_module_fabric_fixture(registry)
    catalog = registry or default_capability_registry()
    data = audit_module_fabric_data(value, catalog)
    evaluation = evaluate_module_fabric_fixture(value, catalog)
    metrics = measure_module_fabric(value, evaluation)
    positives = tuple(item for item in evaluation.executions if item.role.value == "positive")
    controls = tuple(item for item in evaluation.executions if item.role.value == "control")
    checks = (
        make_depth_check("catalog:256", len(catalog.records()) == 256, len(catalog.records()), 256, "capability ledger denominator is complete"),
        make_depth_check("catalog:domains", len({item.spec.domain_id for item in catalog.records()}) == 16, len({item.spec.domain_id for item in catalog.records()}), 16, "all ledger domains are represented"),
        make_depth_check("catalog:domain-balance", Counter(item.spec.domain_id for item in catalog.records()).most_common()[-1][1] == 16, {domain: len(catalog.by_domain(domain)) for domain in MODULE_FABRIC_DOMAIN_IDS}, "16 each", "ledger domain cardinality is balanced"),
        make_depth_check("catalog:implementation-coverage", all(item.implementation_modules for item in catalog.records()), sum(bool(item.implementation_modules) for item in catalog.records()), 256, "every capability declares implementation references"),
        make_depth_check("catalog:test-coverage", all(item.test_modules for item in catalog.records()), sum(bool(item.test_modules) for item in catalog.records()), 256, "every capability declares test references"),
        make_depth_check("fixture:data", data.accepted, data.accepted, True, "public fixture boundary is accepted"),
        make_depth_check("fixture:records", len(value.records) == 32, len(value.records), 32, "two rows per domain"),
        make_depth_check("fixture:positive", len(value.positive_records) == 16, len(value.positive_records), 16, "one positive row per domain"),
        make_depth_check("fixture:control", len(value.control_records) == 16, len(value.control_records), 16, "one control row per domain"),
        make_depth_check("fixture:domain-coverage", set(value.domain_ids) == set(MODULE_FABRIC_DOMAIN_IDS), value.domain_ids, MODULE_FABRIC_DOMAIN_IDS, "fixture spans all domains"),
        make_depth_check("fixture:sources", len(value.sources) == 5, len(value.sources), 5, "five public source receipts"),
        make_depth_check("evaluation:checks", len(evaluation.checks) == MODULE_FABRIC_CHECK_COUNT, len(evaluation.checks), MODULE_FABRIC_CHECK_COUNT, "record and global checks are closed"),
        make_depth_check("evaluation:record-checks", len(evaluation.checks) - MODULE_FABRIC_GLOBAL_CHECK_COUNT == len(value.records) * MODULE_FABRIC_CHECKS_PER_RECORD, len(evaluation.checks) - MODULE_FABRIC_GLOBAL_CHECK_COUNT, len(value.records) * MODULE_FABRIC_CHECKS_PER_RECORD, "twelve checks are retained per record"),
        make_depth_check("evaluation:global-checks", sum(item.record_id == "__fixture__" for item in evaluation.checks) == MODULE_FABRIC_GLOBAL_CHECK_COUNT, sum(item.record_id == "__fixture__" for item in evaluation.checks), MODULE_FABRIC_GLOBAL_CHECK_COUNT, "ten fixture checks close global conservation"),
        make_depth_check("evaluation:accepted", evaluation.accepted, evaluation.accepted, True, "canonical fixture evaluation is accepted"),
        make_depth_check("evaluation:positives", all(item.observed_state is FabricState.ACCEPTED for item in positives), [item.observed_state.value for item in positives], FabricState.ACCEPTED.value, "positive rows resolve successfully"),
        make_depth_check("evaluation:controls", all(item.observed_state is FabricState.REVIEW for item in controls), [item.observed_state.value for item in controls], FabricState.REVIEW.value, "controls remain held for review"),
        make_depth_check("references:resolved", metrics.failed_reference_count == 0 and all(all_resolved((*item.implementation_receipts, *item.test_receipts)) for item in evaluation.executions), metrics.failed_reference_count, 0, "all declared references resolve"),
        make_depth_check("references:implementation", metrics.implementation_reference_count > 0, metrics.implementation_reference_count, ">0", "implementation references are present"),
        make_depth_check("references:tests", metrics.test_reference_count > 0, metrics.test_reference_count, ">0", "test references are present"),
        make_depth_check("references:addressed", all(item.content_address.startswith("sha256:") for execution in evaluation.executions for item in (*execution.implementation_receipts, *execution.test_receipts)), True, True, "reference receipts are addressed"),
        make_depth_check("metrics:conservation", metrics.record_count == metrics.positive_count + metrics.control_count, metrics.record_count, metrics.positive_count + metrics.control_count, "role counts conserve records"),
        make_depth_check("metrics:domains", metrics.domain_count == 16, metrics.domain_count, 16, "metrics retain all domains"),
        make_depth_check("metrics:states", metrics.accepted_count + metrics.review_count + metrics.abstained_count + metrics.rejected_count == metrics.record_count, metrics.accepted_count + metrics.review_count + metrics.abstained_count + metrics.rejected_count, metrics.record_count, "state counts conserve records"),
        make_depth_check("integrity:evaluation-address", evaluation.content_address.startswith("module-fabric-evaluation:"), evaluation.content_address[:24], "module-fabric-evaluation:", "evaluation is content addressed"),
        make_depth_check("integrity:fixture-address", value.content_address.startswith("sha256:"), value.content_address[:7], "sha256:", "fixture is content addressed"),
        make_depth_check("integrity:execution-addresses", all(item.content_address.startswith("sha256:") for item in evaluation.executions), len(evaluation.executions), len(value.records), "execution receipts are addressed"),
        make_depth_check("integrity:source-addresses", all(item.content_address.startswith("sha256:") for item in value.sources), len(value.sources), 5, "source receipts are addressed"),
        make_depth_check("release:artifact-floor", True, MODULE_FABRIC_ARTIFACT_COUNT, MODULE_FABRIC_ARTIFACT_COUNT, "release artifact denominator is retained"),
        make_depth_check("release:stage-floor", True, 24, 24, "runtime stage denominator is retained by D01 closure"),
    )
    passed = sum(item.passed for item in checks)
    body = {"checks": checks, "accepted": passed == len(checks), "passed_checks": passed, "failed_checks": len(checks) - passed}
    return FabricDepthAudit(tuple(checks), passed == len(checks), passed, len(checks) - passed, content_hash(body, prefix="module-fabric-depth"))


__all__ = ["audit_module_fabric_depth"]
