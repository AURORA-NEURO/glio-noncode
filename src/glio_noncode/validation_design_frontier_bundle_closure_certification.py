"""Certification domains for the D13 closure handoff."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .serialization import content_hash
from .validation_design_frontier_bundle_closure_boundary import (
    validate_validation_design_closure_boundary,
)
from .validation_design_frontier_bundle_closure_contracts import (
    VALIDATION_DESIGN_CLOSURE_CERTIFICATION_VERSION,
    ValidationDesignClosureCertificationCheck,
    ValidationDesignClosureCertificationDomain,
    ValidationDesignClosureCertificationReport,
    ValidationDesignClosureIndexAudit,
    ValidationDesignClosureIndexes,
    ValidationDesignClosureReconciliationReport,
    ValidationDesignClosureSummary,
    ValidationDesignClosureSummaryAudit,
)
from .validation_design_frontier_bundle_closure_indexes import (
    audit_validation_design_closure_indexes,
    build_validation_design_closure_indexes,
)
from .validation_design_frontier_bundle_closure_reconciliation import (
    reconcile_validation_design_closure,
)
from .validation_design_frontier_bundle_closure_summary import (
    audit_validation_design_closure_summary,
    build_validation_design_closure_summary,
)
from .validation_design_frontier_bundle_closure_support import (
    all_rows,
    bundle_count_map,
    csv_text,
    payload,
)
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle

_DOMAINS = (
    ("manifest", "Manifest integrity"),
    ("fixture", "Public fixture coverage"),
    ("evaluation", "Evaluation closure"),
    ("runtime", "Runtime trace"),
    ("indexes", "Address-only indexes"),
    ("public", "Public boundary"),
    ("query", "Offline query surface"),
    ("release", "Release certification"),
)


def _accepted(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("accepted"))


def _check(
    check_id: str,
    domain: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    evidence: Iterable[str],
) -> ValidationDesignClosureCertificationCheck:
    body = {
        "check_id": check_id,
        "domain": domain,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
        "evidence": tuple(sorted(str(item) for item in evidence)),
    }
    return ValidationDesignClosureCertificationCheck(
        **body,
        content_address=content_hash(body, prefix="validation-design-closure-certification-check"),
    )


def _domain(
    domain_id: str, title: str, checks: list[ValidationDesignClosureCertificationCheck]
) -> ValidationDesignClosureCertificationDomain:
    body = {
        "domain_id": domain_id,
        "title": title,
        "check_ids": tuple(item.check_id for item in checks),
        "passed_count": sum(item.passed for item in checks),
        "check_count": len(checks),
        "accepted": all(item.passed for item in checks),
    }
    return ValidationDesignClosureCertificationDomain(
        **body,
        content_address=content_hash(body, prefix="validation-design-closure-certification-domain"),
    )


def certify_validation_design_closure(
    bundle: ValidationDesignBundle,
    *,
    indexes: ValidationDesignClosureIndexes | None = None,
    index_audit: ValidationDesignClosureIndexAudit | None = None,
    reconciliation: ValidationDesignClosureReconciliationReport | None = None,
    summary: ValidationDesignClosureSummary | None = None,
    summary_audit: ValidationDesignClosureSummaryAudit | None = None,
) -> ValidationDesignClosureCertificationReport:
    """Run eight six-check certification domains over the portable handoff."""

    value_indexes = indexes or build_validation_design_closure_indexes(bundle)
    value_index_audit = index_audit or audit_validation_design_closure_indexes(
        bundle, value_indexes
    )
    value_reconciliation = reconciliation or reconcile_validation_design_closure(bundle)
    value_summary = summary or build_validation_design_closure_summary(bundle)
    value_summary_audit = summary_audit or audit_validation_design_closure_summary(
        bundle, value_summary
    )
    rows = all_rows(bundle)
    counts = bundle_count_map(bundle)
    boundary = validate_validation_design_closure_boundary(bundle)
    evidence = {
        "manifest": ("bundle.json",),
        "fixture": ("fixture", "access", "data-dictionary"),
        "evaluation": ("evaluation", "quality", "failure-injection"),
        "runtime": ("runtime", "replay", "observability"),
        "indexes": ("bundle.json",),
        "public": tuple(item.artifact_id for item in bundle.artifacts),
        "query": ("fixture", "evaluation", "runtime", "review-csv"),
        "release": ("release", "summary", "report", "review-csv"),
    }
    by_domain: dict[str, list[ValidationDesignClosureCertificationCheck]] = {
        domain: [] for domain, _ in _DOMAINS
    }
    by_domain["manifest"].extend(
        (
            _check(
                "manifest-01",
                "manifest",
                len(bundle.artifacts) == 27,
                len(bundle.artifacts),
                27,
                "artifact denominator closed",
                evidence["manifest"],
            ),
            _check(
                "manifest-02",
                "manifest",
                len({item.artifact_id for item in bundle.artifacts}) == 27,
                len({item.artifact_id for item in bundle.artifacts}),
                27,
                "artifact identities unique",
                evidence["manifest"],
            ),
            _check(
                "manifest-03",
                "manifest",
                len({item.relative_path for item in bundle.artifacts}) == 27,
                len({item.relative_path for item in bundle.artifacts}),
                27,
                "artifact paths unique",
                evidence["manifest"],
            ),
            _check(
                "manifest-04",
                "manifest",
                all(item.payload is not None for item in bundle.artifacts),
                sum(item.payload is not None for item in bundle.artifacts),
                27,
                "all artifact bytes hydrated",
                evidence["manifest"],
            ),
            _check(
                "manifest-05",
                "manifest",
                bundle.warning_count == 0,
                bundle.warning_count,
                0,
                "manifest warning count is zero",
                evidence["manifest"],
            ),
            _check(
                "manifest-06",
                "manifest",
                bundle.ready,
                bundle.ready,
                True,
                "manifest is ready",
                evidence["manifest"],
            ),
        )
    )
    by_domain["fixture"].extend(
        (
            _check(
                "fixture-01",
                "fixture",
                len(rows["records"]) == 16,
                len(rows["records"]),
                16,
                "records conserved",
                evidence["fixture"],
            ),
            _check(
                "fixture-02",
                "fixture",
                len(rows["sources"]) == 5,
                len(rows["sources"]),
                5,
                "source receipts conserved",
                evidence["fixture"],
            ),
            _check(
                "fixture-03",
                "fixture",
                len(rows["operations"]) == 4,
                len(rows["operations"]),
                4,
                "operation families conserved",
                evidence["fixture"],
            ),
            _check(
                "fixture-04",
                "fixture",
                all(row.get("source_ids") for row in rows["records"]),
                sum(bool(row.get("source_ids")) for row in rows["records"]),
                16,
                "every record has source joins",
                evidence["fixture"],
            ),
            _check(
                "fixture-05",
                "fixture",
                all(str(row.get("uri", "")).startswith("https://") for row in rows["sources"]),
                5,
                5,
                "source receipts are HTTPS",
                evidence["fixture"],
            ),
            _check(
                "fixture-06",
                "fixture",
                len(rows["reviews"]) == 16,
                len(rows["reviews"]),
                16,
                "review rows conserve records",
                evidence["fixture"],
            ),
        )
    )
    by_domain["evaluation"].extend(
        (
            _check(
                "evaluation-01",
                "evaluation",
                len(rows["executions"]) == 16,
                len(rows["executions"]),
                16,
                "executions conserved",
                evidence["evaluation"],
            ),
            _check(
                "evaluation-02",
                "evaluation",
                len(rows["checks"]) == 80,
                len(rows["checks"]),
                80,
                "checks conserved",
                evidence["evaluation"],
            ),
            _check(
                "evaluation-03",
                "evaluation",
                sum(bool(row.get("passed")) for row in rows["checks"]) == 80,
                sum(bool(row.get("passed")) for row in rows["checks"]),
                80,
                "all evaluation checks pass",
                evidence["evaluation"],
            ),
            _check(
                "evaluation-04",
                "evaluation",
                all(row.get("record_id") for row in rows["checks"]),
                sum(bool(row.get("record_id")) for row in rows["checks"]),
                80,
                "checks retain record joins",
                evidence["evaluation"],
            ),
            _check(
                "evaluation-05",
                "evaluation",
                value_reconciliation.accepted,
                value_reconciliation.accepted,
                True,
                "reconciliation accepts evaluation",
                evidence["evaluation"],
            ),
            _check(
                "evaluation-06",
                "evaluation",
                value_summary.counter_map.get("failed_evaluation_checks") == 0,
                value_summary.counter_map.get("failed_evaluation_checks"),
                0,
                "summary reports no failed checks",
                evidence["evaluation"],
            ),
        )
    )
    by_domain["runtime"].extend(
        (
            _check(
                "runtime-01",
                "runtime",
                len(rows["stages"]) == 79,
                len(rows["stages"]),
                79,
                "runtime stages conserved",
                evidence["runtime"],
            ),
            _check(
                "runtime-02",
                "runtime",
                [row.get("sequence") for row in rows["stages"]] == list(range(1, 80)),
                "contiguous",
                "1..79",
                "runtime sequence is contiguous",
                evidence["runtime"],
            ),
            _check(
                "runtime-03",
                "runtime",
                all(
                    str(row.get("output_address", "")).startswith("sha256:")
                    for row in rows["stages"]
                ),
                79,
                79,
                "runtime stage outputs are addressed",
                evidence["runtime"],
            ),
            _check(
                "runtime-04",
                "runtime",
                len(rows["planes"]) == 57,
                len(rows["planes"]),
                57,
                "runtime planes conserved",
                evidence["runtime"],
            ),
            _check(
                "runtime-05",
                "runtime",
                all(bool(row.get("accepted")) for row in rows["planes"]),
                57,
                57,
                "runtime planes accepted",
                evidence["runtime"],
            ),
            _check(
                "runtime-06",
                "runtime",
                isinstance(payload_value := bundle.runtime_address, str)
                and payload_value.startswith("validation-design-runtime-public:"),
                bundle.runtime_address,
                "validation-design-runtime-public:",
                "runtime manifest address is stable",
                evidence["runtime"],
            ),
        )
    )
    by_domain["indexes"].extend(
        (
            _check(
                "indexes-01",
                "indexes",
                value_indexes.accepted,
                value_indexes.accepted,
                True,
                "index projection accepted",
                evidence["indexes"],
            ),
            _check(
                "indexes-02",
                "indexes",
                value_index_audit.accepted,
                value_index_audit.accepted,
                True,
                "index audit accepted",
                evidence["indexes"],
            ),
            _check(
                "indexes-03",
                "indexes",
                len(value_indexes.by_artifact_id) == 27,
                len(value_indexes.by_artifact_id),
                27,
                "artifact index complete",
                evidence["indexes"],
            ),
            _check(
                "indexes-04",
                "indexes",
                len(value_indexes.by_check_id) == 80,
                len(value_indexes.by_check_id),
                80,
                "check index complete",
                evidence["indexes"],
            ),
            _check(
                "indexes-05",
                "indexes",
                len(value_indexes.by_stage_id) == 79,
                len(value_indexes.by_stage_id),
                79,
                "stage index complete",
                evidence["indexes"],
            ),
            _check(
                "indexes-06",
                "indexes",
                all(item.address for item in value_indexes.by_record_id),
                sum(bool(item.address) for item in value_indexes.by_record_id),
                len(value_indexes.by_record_id),
                "record index addressed",
                evidence["indexes"],
            ),
        )
    )
    by_domain["public"].extend(
        (
            _check(
                "public-01",
                "public",
                boundary.accepted,
                boundary.accepted,
                True,
                "closure boundary accepts",
                evidence["public"],
            ),
            _check(
                "public-02",
                "public",
                not boundary.forbidden_keys,
                boundary.forbidden_keys,
                (),
                "no forbidden keys discovered",
                evidence["public"],
            ),
            _check(
                "public-03",
                "public",
                boundary.path_checks.get("all_safe_relative", False),
                boundary.path_checks,
                True,
                "artifact paths are safe relative paths",
                evidence["public"],
            ),
            _check(
                "public-04",
                "public",
                boundary.path_checks.get("all_unique", False),
                boundary.path_checks,
                True,
                "artifact paths are unique",
                evidence["public"],
            ),
            _check(
                "public-05",
                "public",
                all(bool(item.get("payload_present")) for item in boundary.artifact_checks),
                sum(bool(item.get("payload_present")) for item in boundary.artifact_checks),
                27,
                "all public payloads are present",
                evidence["public"],
            ),
            _check(
                "public-06",
                "public",
                all(bool(item.get("accepted")) for item in boundary.artifact_checks),
                sum(bool(item.get("accepted")) for item in boundary.artifact_checks),
                27,
                "all artifact boundary checks pass",
                evidence["public"],
            ),
        )
    )
    by_domain["query"].extend(
        (
            _check(
                "query-01",
                "query",
                counts["artifacts"] == 27,
                counts["artifacts"],
                27,
                "artifacts are queryable",
                evidence["query"],
            ),
            _check(
                "query-02",
                "query",
                counts["records"] == 16,
                counts["records"],
                16,
                "records are queryable",
                evidence["query"],
            ),
            _check(
                "query-03",
                "query",
                counts["checks"] == 80,
                counts["checks"],
                80,
                "checks are queryable",
                evidence["query"],
            ),
            _check(
                "query-04",
                "query",
                counts["sources"] == 5,
                counts["sources"],
                5,
                "sources are queryable",
                evidence["query"],
            ),
            _check(
                "query-05",
                "query",
                counts["stages"] == 79,
                counts["stages"],
                79,
                "stages are queryable",
                evidence["query"],
            ),
            _check(
                "query-06",
                "query",
                counts["planes"] == 57,
                counts["planes"],
                57,
                "planes are queryable",
                evidence["query"],
            ),
        )
    )
    by_domain["release"].extend(
        (
            _check(
                "release-01",
                "release",
                value_summary.accepted,
                value_summary.accepted,
                True,
                "summary accepted",
                evidence["release"],
            ),
            _check(
                "release-02",
                "release",
                value_summary_audit.accepted,
                value_summary_audit.accepted,
                True,
                "summary audit accepted",
                evidence["release"],
            ),
            _check(
                "release-03",
                "release",
                value_reconciliation.accepted,
                value_reconciliation.accepted,
                True,
                "reconciliation accepted",
                evidence["release"],
            ),
            _check(
                "release-04",
                "release",
                _accepted(payload_value := payload(bundle, "release")),
                payload_value.get("accepted") if isinstance(payload_value, dict) else False,
                True,
                "source release projection accepted",
                evidence["release"],
            ),
            _check(
                "release-05",
                "release",
                len(rows["reviews"]) == 16,
                len(rows["reviews"]),
                16,
                "release review rows complete",
                evidence["release"],
            ),
            _check(
                "release-06",
                "release",
                all(item.evidence for item in sum(by_domain.values(), [])),
                True,
                True,
                "certification checks retain evidence",
                evidence["release"],
            ),
        )
    )
    checks = tuple(item for domain, _ in _DOMAINS for item in by_domain[domain])
    domains = tuple(_domain(domain, title, by_domain[domain]) for domain, title in _DOMAINS)
    passed = sum(item.passed for item in checks)
    body = {
        "version": VALIDATION_DESIGN_CLOSURE_CERTIFICATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "artifact_count": len(bundle.artifacts),
        "check_count": len(checks),
        "passed_check_count": passed,
        "failed_check_count": len(checks) - passed,
        "coverage_percent": round(100.0 * passed / len(checks), 2) if checks else 0.0,
        "domains": domains,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    return ValidationDesignClosureCertificationReport(
        version=VALIDATION_DESIGN_CLOSURE_CERTIFICATION_VERSION,
        bundle_id=bundle.bundle_id,
        artifact_count=len(bundle.artifacts),
        check_count=len(checks),
        passed_check_count=passed,
        failed_check_count=len(checks) - passed,
        coverage_percent=body["coverage_percent"],
        domains=domains,
        checks=checks,
        accepted=bool(body["accepted"]),
        content_address=content_hash(body, prefix="validation-design-closure-certification"),
    )


def export_validation_design_closure_certification_csv(
    report: ValidationDesignClosureCertificationReport,
) -> str:
    return csv_text([item.to_dict() for item in report.checks])


def export_validation_design_closure_certification_domains_csv(
    report: ValidationDesignClosureCertificationReport,
) -> str:
    return csv_text([item.to_dict() for item in report.domains])


__all__ = [
    "certify_validation_design_closure",
    "export_validation_design_closure_certification_csv",
    "export_validation_design_closure_certification_domains_csv",
]
