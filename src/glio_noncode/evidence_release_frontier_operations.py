"""Independent execution logic for evidence-release transitions.

Each operation accepts a plain mapping and returns a typed result.  The functions do
not mutate input records, read a database, or infer missing context.  A state that
needs a person or another artifact remains explicit as ``review`` or ``blocked``.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence
from typing import Any

from .evidence_release_frontier_contracts import (
    EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY,
    EvidenceReleaseOperation,
    EvidenceReleaseOperationResult,
    EvidenceReleaseState,
)
from .evidence_release_frontier_support import (
    address,
    bounded,
    context_matches,
    duplicate_values,
    mapping,
    normalized_issue_codes,
    positive_number,
    required_text,
    safe_output,
    sequence,
)
from .serialization import canonical_bytes

FIXTURE_KEY_ID = "evidence-release-fixture-key-001"
_FIXTURE_SIGNING_MATERIAL = "public-fixture-verification-material"


def _result(operation: EvidenceReleaseOperation, state: EvidenceReleaseState, codes: Sequence[str], output: Mapping[str, Any]) -> EvidenceReleaseOperationResult:
    normalized = normalized_issue_codes(codes)
    projected = safe_output(output)
    body = {"operation": operation, "state": state, "issue_codes": normalized, "output": projected}
    return EvidenceReleaseOperationResult(**body, content_address=address(body))


def _invalid(operation: EvidenceReleaseOperation, fields: Sequence[str]) -> EvidenceReleaseOperationResult:
    return _result(operation, EvidenceReleaseState.REJECTED, ("invalid_payload",), {"accepted_fields": tuple(fields)})


def evaluate_reclassification(payload: Mapping[str, Any]) -> EvidenceReleaseOperationResult:
    """Propose a tier transition only when independent support is complete."""
    operation = EvidenceReleaseOperation.RECLASSIFICATION
    try:
        evidence_id = required_text(payload.get("evidence_id"), "evidence_id")
        context = payload.get("context_key")
        previous = required_text(payload.get("previous_tier"), "previous_tier")
        proposed = required_text(payload.get("proposed_tier"), "proposed_tier")
        score = bounded(payload.get("evidence_score"), "evidence_score")
        threshold = bounded(payload.get("threshold", 0.75), "threshold")
        reviewers = tuple(required_text(value, "reviewer_id") for value in sequence(payload.get("reviewer_ids", ()), "reviewer_ids"))
        sources = tuple(required_text(value, "source_id") for value in sequence(payload.get("source_ids", ()), "source_ids"))
        issues: list[str] = []
        if not context_matches(context, EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY):
            issues.append("context_mismatch")
        if proposed == previous:
            issues.append("classification_unchanged")
        if score < threshold:
            issues.append("score_below_threshold")
        if len(set(reviewers)) < 2:
            issues.append("independent_reviewers_missing")
        if len(set(sources)) < 2:
            issues.append("independent_sources_missing")
        if "context_mismatch" in issues:
            state = EvidenceReleaseState.BLOCKED
        elif issues:
            state = EvidenceReleaseState.REVIEW
        else:
            state = EvidenceReleaseState.RECLASSIFIED
        output = {"evidence_id": evidence_id, "previous_tier": previous, "proposed_tier": proposed, "evidence_score": round(score, 6), "threshold": round(threshold, 6), "reviewer_count": len(set(reviewers)), "source_count": len(set(sources)), "decision_basis_address": address({"evidence_id": evidence_id, "score": score, "reviewers": sorted(set(reviewers)), "sources": sorted(set(sources))})}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("evidence_id", "context_key", "previous_tier", "proposed_tier", "evidence_score", "reviewer_ids", "source_ids"))


def _supersession_cycle(graph: Mapping[str, str | None]) -> bool:
    for start in graph:
        seen: set[str] = set()
        current: str | None = start
        while current is not None:
            if current in seen:
                return True
            seen.add(current)
            current = graph.get(current)
    return False


def evaluate_supersession(payload: Mapping[str, Any]) -> EvidenceReleaseOperationResult:
    """Close a deprecation chain only if every target and context is resolvable."""
    operation = EvidenceReleaseOperation.SUPERSESSION
    try:
        context = payload.get("context_key")
        rows = sequence(payload.get("records", ()), "records")
        parsed: list[dict[str, Any]] = []
        ids: list[str] = []
        for index, raw in enumerate(rows, start=1):
            row = mapping(raw, f"records[{index}]")
            record_id = required_text(row.get("record_id"), f"records[{index}].record_id")
            status = required_text(row.get("status"), f"records[{index}].status")
            supersedes_value = row.get("supersedes")
            supersedes = None if supersedes_value in (None, "") else required_text(supersedes_value, f"records[{index}].supersedes")
            row_context = row.get("context_key")
            ids.append(record_id)
            parsed.append({"record_id": record_id, "status": status, "supersedes": supersedes, "context_key": row_context})
        issues: list[str] = []
        if not context_matches(context, EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY) or any(not context_matches(row["context_key"], EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY) for row in parsed):
            issues.append("context_mismatch")
        if duplicate_values(ids):
            issues.append("duplicate_record_id")
        known = set(ids)
        missing = tuple(sorted({row["supersedes"] for row in parsed if row["supersedes"] and row["supersedes"] not in known}))
        if missing:
            issues.append("supersession_target_missing")
        if any(row["supersedes"] == row["record_id"] for row in parsed):
            issues.append("self_supersession")
        graph = {row["record_id"]: row["supersedes"] for row in parsed}
        if _supersession_cycle(graph):
            issues.append("supersession_cycle")
        active = tuple(sorted(row["record_id"] for row in parsed if row["status"] == "active"))
        retired = tuple(sorted(row["record_id"] for row in parsed if row["status"] in {"deprecated", "superseded", "retired"}))
        if "context_mismatch" in issues or "supersession_cycle" in issues or "self_supersession" in issues:
            state = EvidenceReleaseState.BLOCKED
        elif issues:
            state = EvidenceReleaseState.REVIEW
        else:
            state = EvidenceReleaseState.SUPERSEDED
        output = {"record_count": len(parsed), "active_ids": active, "retired_ids": retired, "missing_targets": missing, "chain_address": address(graph)}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("context_key", "records", "record_id", "status", "supersedes"))


def evaluate_reproducibility_bundle(payload: Mapping[str, Any]) -> EvidenceReleaseOperationResult:
    """Assemble three independently addressable sections into an audit bundle."""
    operation = EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE
    try:
        bundle_id = required_text(payload.get("bundle_id"), "bundle_id")
        context = payload.get("context_key")
        raw_sections = sequence(payload.get("sections", ()), "sections")
        sections: list[dict[str, Any]] = []
        section_ids: list[str] = []
        issues: list[str] = []
        for index, raw in enumerate(raw_sections, start=1):
            row = mapping(raw, f"sections[{index}]")
            section_id = required_text(row.get("section_id"), f"sections[{index}].section_id")
            kind = required_text(row.get("kind"), f"sections[{index}].kind")
            items = sequence(row.get("items", ()), f"sections[{index}].items")
            section_context = row.get("context_key")
            if not context_matches(section_context, EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY):
                issues.append("context_mismatch")
            if not items:
                issues.append("section_empty")
            addresses: list[str] = []
            for item_index, item in enumerate(items, start=1):
                item_map = mapping(item, f"sections[{index}].items[{item_index}]")
                item_address = item_map.get("content_address")
                if not isinstance(item_address, str) or not item_address.startswith("sha256:"):
                    issues.append("item_address_missing")
                else:
                    addresses.append(item_address)
            section_ids.append(section_id)
            sections.append({"section_id": section_id, "kind": kind, "item_count": len(items), "item_addresses": tuple(addresses), "section_address": address({"section_id": section_id, "kind": kind, "items": items})})
        if not context_matches(context, EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY):
            issues.append("context_mismatch")
        if duplicate_values(section_ids):
            issues.append("duplicate_section_id")
        required_kinds = {"evidence", "review", "release"}
        observed_kinds = {item["kind"] for item in sections}
        missing_kinds = tuple(sorted(required_kinds - observed_kinds))
        if missing_kinds:
            issues.append("required_section_missing")
        if "context_mismatch" in issues:
            state = EvidenceReleaseState.BLOCKED
        elif issues:
            state = EvidenceReleaseState.REVIEW if not any(code in issues for code in ("item_address_missing",)) else EvidenceReleaseState.REVIEW
        else:
            state = EvidenceReleaseState.BUNDLED
        manifest = {"bundle_id": bundle_id, "context_key": context, "sections": tuple(sections), "missing_kinds": missing_kinds}
        output = manifest | {"bundle_address": address(manifest)}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("bundle_id", "context_key", "sections", "section_id", "kind", "items"))


def _signature(payload: Mapping[str, Any], key_material: str) -> str:
    return "hmac-sha256:" + hmac.new(key_material.encode("utf-8"), canonical_bytes(payload), hashlib.sha256).hexdigest()


def sign_dossier(payload: Mapping[str, Any], *, signing_key: str = _FIXTURE_SIGNING_MATERIAL) -> EvidenceReleaseOperationResult:
    """Create a verifiable receipt while excluding key material from the result."""
    operation = EvidenceReleaseOperation.SIGNED_DOSSIER
    try:
        dossier_id = required_text(payload.get("dossier_id"), "dossier_id")
        context = payload.get("context_key")
        audience = required_text(payload.get("audience"), "audience")
        key_id = required_text(payload.get("key_id", FIXTURE_KEY_ID), "key_id")
        expires = required_text(payload.get("expires_at"), "expires_at")
        dossier_payload = mapping(payload.get("payload"), "payload")
        issues: list[str] = []
        if not context_matches(context, EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY):
            issues.append("context_mismatch")
        if len(audience.split()) < 1:
            issues.append("audience_missing")
        if expires.startswith("expired:"):
            issues.append("dossier_expired")
        if not dossier_payload:
            issues.append("dossier_payload_empty")
        body = {"dossier_id": dossier_id, "context_key": context, "audience": audience, "key_id": key_id, "expires_at": expires, "payload": dossier_payload}
        signature = _signature(body, signing_key)
        state = EvidenceReleaseState.BLOCKED if "context_mismatch" in issues else EvidenceReleaseState.REVIEW if issues else EvidenceReleaseState.SIGNED
        output = body | {"payload_address": address(dossier_payload), "signature": signature, "verification_state": "signed" if state == EvidenceReleaseState.SIGNED else "not_signed"}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("dossier_id", "context_key", "audience", "expires_at", "payload", "key_id"))


def verify_signed_dossier(payload: Mapping[str, Any], *, signing_key: str = _FIXTURE_SIGNING_MATERIAL) -> EvidenceReleaseOperationResult:
    """Verify a dossier receipt by recomputing the signed canonical payload."""
    operation = EvidenceReleaseOperation.SIGNED_DOSSIER
    try:
        signed = mapping(payload.get("signed_dossier", payload), "signed_dossier")
        supplied = required_text(signed.get("signature"), "signature")
        unsigned = {key: signed[key] for key in ("dossier_id", "context_key", "audience", "key_id", "expires_at", "payload") if key in signed}
        expected = _signature(unsigned, signing_key)
        context_ok = context_matches(unsigned.get("context_key"), EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY)
        valid = hmac.compare_digest(expected, supplied) and context_ok
        issues = () if valid else ("signature_mismatch",) if not hmac.compare_digest(expected, supplied) else ("context_mismatch",)
        state = EvidenceReleaseState.VERIFIED if valid else EvidenceReleaseState.BLOCKED if "context_mismatch" in issues else EvidenceReleaseState.REJECTED
        output = {"dossier_id": unsigned.get("dossier_id"), "key_id": unsigned.get("key_id"), "signature_valid": valid, "verified_payload_address": address(unsigned.get("payload", {})), "verification_state": "verified" if valid else "failed"}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("signed_dossier", "signature", "dossier_id", "payload"))


def run_evidence_release_operation(operation: EvidenceReleaseOperation, payload: Mapping[str, Any]) -> EvidenceReleaseOperationResult:
    dispatch = {
        EvidenceReleaseOperation.RECLASSIFICATION: evaluate_reclassification,
        EvidenceReleaseOperation.SUPERSESSION: evaluate_supersession,
        EvidenceReleaseOperation.REPRODUCIBILITY_BUNDLE: evaluate_reproducibility_bundle,
        EvidenceReleaseOperation.SIGNED_DOSSIER: sign_dossier,
    }
    return dispatch[operation](mapping(payload, "payload"))


__all__ = [
    "FIXTURE_KEY_ID",
    "evaluate_reclassification",
    "evaluate_reproducibility_bundle",
    "evaluate_supersession",
    "run_evidence_release_operation",
    "sign_dossier",
    "verify_signed_dossier",
]
