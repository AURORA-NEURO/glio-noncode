"""Independent cross-artifact reconciliation for D13 offline bundles."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle

VALIDATION_DESIGN_BUNDLE_AUDIT_VERSION = "validation-design-bundle-audit-v1"


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleAuditCheck:
    check_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignBundleAudit:
    version: str
    bundle_id: str
    checks: tuple[ValidationDesignBundleAuditCheck, ...]
    accepted: bool
    content_address: str

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "bundle_id": self.bundle_id,
            "checks": [item.to_dict() for item in self.checks],
            "check_count": self.check_count,
            "passed_check_count": self.passed_check_count,
            "failed_check_count": len(self.failed_check_ids),
            "failed_check_ids": list(self.failed_check_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _check(check_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str) -> ValidationDesignBundleAuditCheck:
    body = {"check_id": check_id, "plane": plane, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return ValidationDesignBundleAuditCheck(**body, content_address=content_hash(body, prefix="validation-design-bundle-audit-check"))


def _json_payload(bundle: ValidationDesignBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _accepted(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("accepted"))


def audit_validation_design_offline_bundle(bundle: ValidationDesignBundle) -> ValidationDesignBundleAudit:
    """Reconcile independent fixture, evaluation, runtime, and release views."""

    fixture = _json_payload(bundle, "fixture")
    evaluation = _json_payload(bundle, "evaluation")
    runtime = _json_payload(bundle, "runtime")
    replay = _json_payload(bundle, "replay")
    release = _json_payload(bundle, "release")
    quality = _json_payload(bundle, "quality")
    access = _json_payload(bundle, "access")
    report = _json_payload(bundle, "report")
    checks: list[ValidationDesignBundleAuditCheck] = []
    checks.append(_check("bundle-accepted", "manifest", bundle.accepted and bundle.ready, {"accepted": bundle.accepted, "state": bundle.state.value}, {"accepted": True, "state": "ready"}, "the loaded manifest is release-ready"))
    checks.append(_check("artifact-count", "manifest", bundle.artifact_count == 27, bundle.artifact_count, 27, "the closed D13 artifact denominator is retained"))
    checks.append(_check("artifact-identities", "manifest", len({item.artifact_id for item in bundle.artifacts}) == bundle.artifact_count, len({item.artifact_id for item in bundle.artifacts}), bundle.artifact_count, "artifact identities are unique"))
    checks.append(_check("artifact-addresses", "manifest", all(item.payload is not None and item.content_address for item in bundle.artifacts), sum(item.payload is not None for item in bundle.artifacts), bundle.artifact_count, "every artifact has hydrated addressed bytes"))
    public = all(item.payload is not None and (item.media_type != "application/json" or not _has_forbidden_key(json.loads(item.payload))) and (item.payload is not None and (item.media_type != "application/json" or not contains_private_key(json.loads(item.payload)))) for item in bundle.artifacts if item.payload is not None)
    checks.append(_check("public-boundary", "public_boundary", public, public, True, "materialized JSON artifacts remain public aggregate projections"))
    checks.append(_check("fixture-object", "fixture", isinstance(fixture, dict), type(fixture).__name__, "dict", "fixture artifact is a JSON object"))
    records = fixture.get("records", ()) if isinstance(fixture, dict) else ()
    sources = fixture.get("sources", ()) if isinstance(fixture, dict) else ()
    checks.append(_check("fixture-records", "fixture", isinstance(records, list) and len(records) == 16, len(records) if isinstance(records, list) else 0, 16, "fixture contains four records per planning operation"))
    checks.append(_check("fixture-sources", "fixture", isinstance(sources, list) and len(sources) == 5, len(sources) if isinstance(sources, list) else 0, 5, "fixture source receipt denominator is conserved"))
    source_ids = {str(item.get("source_id")) for item in sources if isinstance(item, dict)}
    checks.append(_check("source-joins", "fixture", all(set(item.get("source_ids", ())) <= source_ids for item in records if isinstance(item, dict)), source_ids, "all referenced source ids", "record source joins close"))
    checks.append(_check("https-sources", "fixture", all(str(item.get("uri", "")).startswith("https://") for item in sources if isinstance(item, dict)), tuple(item.get("uri") for item in sources if isinstance(item, dict)), "https:// receipts", "all source receipts use HTTPS"))
    executions = evaluation.get("executions", ()) if isinstance(evaluation, dict) else ()
    evaluation_checks = evaluation.get("checks", ()) if isinstance(evaluation, dict) else ()
    checks.append(_check("evaluation-accepted", "evaluation", _accepted(evaluation), evaluation.get("accepted") if isinstance(evaluation, dict) else None, True, "evaluation artifact is accepted"))
    checks.append(_check("evaluation-executions", "evaluation", isinstance(executions, list) and len(executions) == 16, len(executions) if isinstance(executions, list) else 0, 16, "every fixture record has one execution"))
    checks.append(_check("evaluation-checks", "evaluation", isinstance(evaluation_checks, list) and len(evaluation_checks) == 80, len(evaluation_checks) if isinstance(evaluation_checks, list) else 0, 80, "five evaluation checks remain attached to every row"))
    record_ids = {str(item.get("record_id")) for item in records if isinstance(item, dict)}
    execution_ids = {str(item.get("record_id")) for item in executions if isinstance(item, dict)}
    checks.append(_check("execution-record-closure", "evaluation", execution_ids == record_ids, len(execution_ids), len(record_ids), "evaluation executions close the fixture record set"))
    checks.append(_check("check-record-closure", "evaluation", all(str(item.get("record_id")) in record_ids for item in evaluation_checks if isinstance(item, dict)), len(evaluation_checks), len(evaluation_checks), "evaluation checks point to known records"))
    stages = runtime.get("stages", ()) if isinstance(runtime, dict) else ()
    checks.append(_check("runtime-accepted", "runtime", _accepted(runtime), runtime.get("accepted") if isinstance(runtime, dict) else None, True, "runtime artifact is accepted"))
    checks.append(_check("runtime-stages", "runtime", isinstance(stages, list) and len(stages) == 79, len(stages) if isinstance(stages, list) else 0, 79, "complete validation-design stage sequence is retained"))
    ordinals = [item.get("sequence") for item in stages if isinstance(item, dict)]
    checks.append(_check("runtime-stage-order", "runtime", ordinals == list(range(1, 80)), ordinals[:3] + ordinals[-3:] if ordinals else (), "1..79", "runtime stages have contiguous sequence numbers"))
    checks.append(_check("runtime-address", "runtime", isinstance(runtime, dict) and runtime.get("content_address") == bundle.runtime_address, runtime.get("content_address") if isinstance(runtime, dict) else None, bundle.runtime_address, "manifest runtime address matches runtime artifact"))
    checks.append(_check("replay-deterministic", "replay", isinstance(replay, dict) and bool(replay.get("deterministic")), replay.get("deterministic") if isinstance(replay, dict) else None, True, "replay receipt is deterministic"))
    checks.append(_check("quality-accepted", "quality", _accepted(quality), quality.get("accepted") if isinstance(quality, dict) else None, True, "quality gate artifact is accepted"))
    access_ok = isinstance(access, dict) and bool(access.get("boundary")) and len(access.get("sources", ())) == 5 and bool(access.get("prohibited_inputs"))
    checks.append(_check("access-boundary", "access", access_ok, {"boundary": access.get("boundary") if isinstance(access, dict) else None, "sources": len(access.get("sources", ())) if isinstance(access, dict) else 0}, {"sources": 5}, "access manifest retains the public aggregate boundary"))
    checks.append(_check("release-accepted", "release", _accepted(release), release.get("accepted") if isinstance(release, dict) else None, True, "release artifact is accepted"))
    checks.append(_check("report-row-count", "report", isinstance(report, dict) and report.get("values", {}).get("row_count") == 16, report.get("values", {}).get("row_count") if isinstance(report, dict) else None, 16, "report reconciles the 16 scenario rows"))
    review_artifact = next((item for item in bundle.artifacts if item.artifact_id == "review-csv"), None)
    review_rows = 0
    if review_artifact is not None and review_artifact.payload is not None:
        review_rows = max(0, sum(1 for _ in csv.reader(io.StringIO(review_artifact.payload))) - 1)
    checks.append(_check("review-csv-rows", "projection", review_rows == 16, review_rows, 16, "review CSV contains one row per scenario"))
    checks.append(_check("operation-balance", "fixture", len({str(item.get("operation")) for item in records if isinstance(item, dict)}) == 4, len({str(item.get("operation")) for item in records if isinstance(item, dict)}), 4, "four validation-design operation families remain represented"))
    accepted = all(item.passed for item in checks)
    body = {"version": VALIDATION_DESIGN_BUNDLE_AUDIT_VERSION, "bundle_id": bundle.bundle_id, "checks": tuple(checks), "accepted": accepted}
    return ValidationDesignBundleAudit(**body, content_address=content_hash(body, prefix="validation-design-bundle-audit"))


__all__ = [
    "VALIDATION_DESIGN_BUNDLE_AUDIT_VERSION",
    "ValidationDesignBundleAudit",
    "ValidationDesignBundleAuditCheck",
    "audit_validation_design_offline_bundle",
]
