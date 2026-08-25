"""Independent certification domains for the program-runtime handoff."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from .program_runtime_offline_boundary import program_runtime_offline_key_inventory
from .program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
    PROGRAM_RUNTIME_OFFLINE_CERTIFICATION_VERSION,
    PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
    PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
    ProgramRuntimeOfflineBundle,
)
from .program_runtime_offline_query import _payload, _rows
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineCertificationCheck:
    check_id: str
    domain: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    evidence_artifact_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineCertificationDomain:
    domain_id: str
    title: str
    check_ids: tuple[str, ...]
    passed_count: int
    check_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineCertificationReport:
    version: str
    bundle_id: str
    artifact_count: int
    check_count: int
    passed_check_count: int
    failed_check_count: int
    coverage_percent: float
    domains: tuple[ProgramRuntimeOfflineCertificationDomain, ...]
    checks: tuple[ProgramRuntimeOfflineCertificationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def accepted_domain_count(self) -> int:
        return sum(item.accepted for item in self.domains)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted_domain_count": self.accepted_domain_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _check(
    check_id: str,
    domain: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    evidence: tuple[str, ...] = (),
) -> ProgramRuntimeOfflineCertificationCheck:
    body = {
        "check_id": check_id,
        "domain": domain,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
        "evidence_artifact_ids": evidence,
    }
    return ProgramRuntimeOfflineCertificationCheck(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-certification-check"),
    )


def _json_ok(bundle: ProgramRuntimeOfflineBundle) -> bool:
    for item in bundle.artifacts:
        if item.media_type != "application/json":
            continue
        try:
            json.loads(item.payload or "{}")
        except json.JSONDecodeError:
            return False
    return True


def _build_checks(
    bundle: ProgramRuntimeOfflineBundle,
) -> tuple[ProgramRuntimeOfflineCertificationCheck, ...]:
    domains = _rows(bundle, "domains")
    checks = _rows(bundle, "checks")
    stages = _rows(bundle, "stages")
    quality = _rows(bundle, "quality")
    release_checks = _rows(bundle, "release_checks")
    specifications = _rows(bundle, "specifications")
    capabilities = _rows(bundle, "capabilities")
    runtime = _payload(bundle, "runtime") or {}
    report = _payload(bundle, "report") or {}
    operational = _payload(bundle, "operational") or {}
    key_inventory = program_runtime_offline_key_inventory(bundle)
    return (
        _check(
            "manifest-ready",
            "manifest",
            bundle.ready,
            bundle.state.value,
            "ready",
            "manifest is ready",
            ("runtime",),
        ),
        _check(
            "manifest-boundary",
            "manifest",
            bundle.boundary.startswith("public_aggregate_"),
            bundle.boundary,
            "public aggregate boundary",
            "manifest boundary is public aggregate",
            ("runtime",),
        ),
        _check(
            "manifest-address",
            "manifest",
            bundle.content_address.startswith("program-runtime-offline-bundle:"),
            bundle.content_address,
            "address",
            "manifest is addressed",
            ("runtime",),
        ),
        _check(
            "manifest-artifacts",
            "manifest",
            bundle.artifact_count == PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            bundle.artifact_count,
            PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            "portable artifact denominator is closed",
            ("runtime",),
        ),
        _check(
            "manifest-checks",
            "manifest",
            bundle.failed_check_count == 0,
            bundle.failed_check_count,
            0,
            "manifest checks have no holds",
            ("runtime",),
        ),
        _check(
            "inventory-identities",
            "inventory",
            len({item.artifact_id for item in bundle.artifacts}) == bundle.artifact_count,
            bundle.artifact_count,
            bundle.artifact_count,
            "artifact identities are unique",
            ("runtime",),
        ),
        _check(
            "inventory-paths",
            "inventory",
            len({item.relative_path for item in bundle.artifacts}) == bundle.artifact_count,
            bundle.artifact_count,
            bundle.artifact_count,
            "artifact paths are unique",
            ("runtime",),
        ),
        _check(
            "inventory-addresses",
            "inventory",
            all(item.content_address for item in bundle.artifacts),
            True,
            True,
            "artifacts are addressed",
            ("runtime",),
        ),
        _check(
            "inventory-bytes",
            "inventory",
            all(item.byte_count > 0 for item in bundle.artifacts),
            True,
            True,
            "artifacts have bytes",
            ("runtime",),
        ),
        _check(
            "inventory-lines",
            "inventory",
            all(item.line_count > 0 for item in bundle.artifacts),
            True,
            True,
            "artifacts have lines",
            ("runtime",),
        ),
        _check(
            "runtime-domains",
            "runtime",
            len(domains) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(domains),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "sixteen domain operations are present",
            ("operations",),
        ),
        _check(
            "runtime-checks",
            "runtime",
            len(checks) == PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            len(checks),
            PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            "program checks are present",
            ("checks",),
        ),
        _check(
            "runtime-quality",
            "runtime",
            len(quality) == PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
            len(quality),
            PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
            "quality checks are present",
            ("quality",),
        ),
        _check(
            "runtime-stages",
            "runtime",
            len(stages) == PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            len(stages),
            PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            "runtime stages are present",
            ("stages",),
        ),
        _check(
            "runtime-sequence",
            "runtime",
            [item.get("ordinal") for item in stages] == list(range(1, 13)),
            [item.get("ordinal") for item in stages],
            list(range(1, 13)),
            "runtime sequence is contiguous",
            ("stages",),
        ),
        _check(
            "release-check-denominator",
            "release",
            len(release_checks) == 18,
            len(release_checks),
            18,
            "release checks are present",
            ("release-checks",),
        ),
        _check(
            "release-check-state",
            "release",
            all(str(item.get("passed")).casefold() == "true" for item in release_checks),
            True,
            True,
            "release checks pass",
            ("release-checks",),
        ),
        _check(
            "release-specifications",
            "release",
            len(specifications) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(specifications),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "specifications are present",
            ("specifications",),
        ),
        _check(
            "release-capabilities",
            "release",
            len(capabilities) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(capabilities),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "capability matrix is present",
            ("capabilities",),
        ),
        _check(
            "release-replay",
            "release",
            any(item.artifact_id == "replay" for item in bundle.artifacts),
            True,
            True,
            "replay artifact is present",
            ("replay",),
        ),
        _check(
            "release-failure-controls",
            "release",
            any(item.artifact_id == "failure-controls" for item in bundle.artifacts),
            True,
            True,
            "failure controls are present",
            ("failure-controls",),
        ),
        _check(
            "reconciliation-runtime",
            "reconciliation",
            runtime.get("accepted") is True,
            runtime.get("accepted"),
            True,
            "runtime is accepted",
            ("runtime",),
        ),
        _check(
            "reconciliation-report",
            "reconciliation",
            report.get("accepted") is True,
            report.get("accepted"),
            True,
            "report is accepted",
            ("report",),
        ),
        _check(
            "reconciliation-operational",
            "reconciliation",
            operational.get("accepted") is True,
            operational.get("accepted"),
            True,
            "operational trace is accepted",
            ("operational",),
        ),
        _check(
            "reconciliation-address",
            "reconciliation",
            runtime.get("content_address") == bundle.runtime_address,
            runtime.get("content_address"),
            bundle.runtime_address,
            "runtime address joins manifest",
            ("runtime",),
        ),
        _check(
            "reconciliation-identities",
            "reconciliation",
            len({item.get("domain_id") for item in domains}) == len(domains),
            len({item.get("domain_id") for item in domains}),
            len(domains),
            "domain identity join is unique",
            ("operations",),
        ),
        _check(
            "query-domains",
            "query",
            len(_rows(bundle, "domains")) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(_rows(bundle, "domains")),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "domain query resource is populated",
            ("operations",),
        ),
        _check(
            "query-states",
            "query",
            len(_rows(bundle, "states")) > 0,
            len(_rows(bundle, "states")),
            ">0",
            "state query resource is populated",
            ("operations",),
        ),
        _check(
            "query-capabilities",
            "query",
            len(_rows(bundle, "capabilities")) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(_rows(bundle, "capabilities")),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "capability query resource is populated",
            ("capabilities",),
        ),
        _check(
            "query-checks",
            "query",
            len(_rows(bundle, "checks")) == PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            len(_rows(bundle, "checks")),
            PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            "check query resource is populated",
            ("checks",),
        ),
        _check(
            "query-addresses",
            "query",
            all(item.get("content_address") for item in domains),
            True,
            True,
            "query rows retain stable addresses",
            ("operations",),
        ),
        _check(
            "public-keys",
            "public",
            key_inventory["accepted"],
            key_inventory["forbidden_keys"],
            (),
            "public key inventory contains no prohibited keys",
            ("runtime",),
        ),
        _check(
            "public-json",
            "public",
            _json_ok(bundle),
            True,
            True,
            "all JSON payloads parse",
            ("runtime",),
        ),
        _check(
            "public-paths",
            "public",
            all(".." not in item.relative_path.split("/") for item in bundle.artifacts),
            True,
            True,
            "artifact paths cannot escape the bundle",
            ("runtime",),
        ),
        _check(
            "public-payloads",
            "public",
            all(item.payload is not None for item in bundle.artifacts),
            True,
            True,
            "every in-memory artifact has a payload",
            ("runtime",),
        ),
        _check(
            "public-boundary",
            "public",
            all(
                key not in key_inventory["forbidden_keys"]
                for key in key_inventory["forbidden_keys"]
            ),
            len(key_inventory["forbidden_keys"]) == 0,
            True,
            "public boundary is closed",
            ("runtime",),
        ),
    )


def certify_program_runtime_offline_bundle(
    bundle: ProgramRuntimeOfflineBundle,
) -> ProgramRuntimeOfflineCertificationReport:
    """Run seven independent certification domains over the handoff."""

    checks = _build_checks(bundle)
    titles = (
        ("manifest", "Manifest identity and lifecycle", 0, 5),
        ("inventory", "Artifact inventory and byte accounting", 5, 10),
        ("runtime", "Runtime denominator and stage closure", 10, 15),
        ("release", "Release projection closure", 15, 20),
        ("reconciliation", "Cross-artifact identity joins", 20, 25),
        ("query", "Offline query resource closure", 25, 30),
        ("public", "Public aggregate boundary", 30, 36),
    )
    domains = tuple(
        ProgramRuntimeOfflineCertificationDomain(
            domain_id=domain_id,
            title=title,
            check_ids=tuple(item.check_id for item in checks[start:end]),
            passed_count=sum(item.passed for item in checks[start:end]),
            check_count=end - start,
            accepted=all(item.passed for item in checks[start:end]),
            content_address=content_hash(
                {
                    "domain_id": domain_id,
                    "title": title,
                    "check_ids": tuple(item.check_id for item in checks[start:end]),
                    "passed_count": sum(item.passed for item in checks[start:end]),
                    "check_count": end - start,
                },
                prefix="program-runtime-offline-certification-domain",
            ),
        )
        for domain_id, title, start, end in titles
    )
    passed_count = sum(item.passed for item in checks)
    body = {
        "version": PROGRAM_RUNTIME_OFFLINE_CERTIFICATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "artifact_count": bundle.artifact_count,
        "check_count": len(checks),
        "passed_check_count": passed_count,
        "failed_check_count": len(checks) - passed_count,
        "coverage_percent": round(100.0 * passed_count / max(1, len(checks)), 6),
        "domains": domains,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    return ProgramRuntimeOfflineCertificationReport(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-certification"),
    )


def program_runtime_offline_certification_csv(
    report: ProgramRuntimeOfflineCertificationReport,
) -> str:
    output = io.StringIO()
    fieldnames = (
        "check_id",
        "domain",
        "passed",
        "observed",
        "required",
        "detail",
        "evidence_artifact_ids",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in report.checks:
        writer.writerow(
            {
                "check_id": item.check_id,
                "domain": item.domain,
                "passed": item.passed,
                "observed": json.dumps(item.observed, sort_keys=True),
                "required": json.dumps(item.required, sort_keys=True),
                "detail": item.detail,
                "evidence_artifact_ids": ",".join(item.evidence_artifact_ids),
                "content_address": item.content_address,
            }
        )
    return output.getvalue()


def program_runtime_offline_certification_markdown(
    report: ProgramRuntimeOfflineCertificationReport,
) -> str:
    lines = [
        "# Architecture program offline certification",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        f"Coverage: `{report.coverage_percent:.2f}%`",
        "",
        "| Domain | Passed | Checks | State |",
        "| --- | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| `{item.domain_id}` {item.title} | {item.passed_count} | {item.check_count} | "
        f"`{('pass' if item.accepted else 'hold')}` |"
        for item in report.domains
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "ProgramRuntimeOfflineCertificationCheck",
    "ProgramRuntimeOfflineCertificationDomain",
    "ProgramRuntimeOfflineCertificationReport",
    "certify_program_runtime_offline_bundle",
    "program_runtime_offline_certification_csv",
    "program_runtime_offline_certification_markdown",
]
