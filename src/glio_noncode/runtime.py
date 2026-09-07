"""Orchestration for case evaluation, review, replay, and local persistence."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .adapters import (
    AdapterClaimCollectionReport,
    AdapterRegistry,
    AdapterRegistrySnapshot,
    AdapterResolutionReport,
)
from .atlas import AtlasBundle, AtlasQuery, PublicAtlasRetriever
from .data_sources import EnrichmentResult, PublicReferenceRetriever
from .errors import PolicyViolation, StoreError, ValidationError
from .events import MAX_EVENT_RECORD_BYTES, EventLog
from .experiments import ExperimentPlanner, ExperimentPlanningLimits
from .expression_claims import (
    RNA_CONSEQUENCE_CHANNEL,
    validate_rna_consequence,
)
from .expression_claims import (
    public_projection as rna_claim_public_projection,
)
from .expression_evidence import RNAConsequenceEvidence
from .hypotheses import HypothesisBuilder, HypothesisWorkLimits
from .models import (
    CaseManifest,
    Dossier,
    EdgeType,
    EvidenceClaim,
    ExperimentOption,
    Hypothesis,
    ResearchStatus,
    ReviewDecision,
    ReviewState,
)
from .policy import PolicyDecision, ResearchPolicy
from .replay import ReplayReport, ReplayVerifier
from .scoring import element_relevance
from .serialization import canonical_bytes, content_hash, freeze_json, jsonable, utc_now
from .storage import MAX_RUN_HISTORY_ENTRIES, RunStore
from .validation import (
    ContractValidator,
    ReleaseGate,
    ValidationIssue,
    ValidationReport,
)

_MAX_RUNTIME_RNA_INPUT_BYTES = 64 * 1024 * 1024
_MAX_RUNTIME_RNA_CONSEQUENCES = 10_000
_MAX_RUNTIME_RNA_ROW_BYTES = 64 * 1024
_MAX_RUNTIME_RNA_REASON_CODES = 256
_MAX_RUNTIME_RNA_REASON_CODE_CHARACTERS = 128
_ADAPTER_INPUT_VERSION_KEYS = (
    "adapter_input_manifest",
    "adapter_registry_snapshot",
    "adapter_resolution_report",
    "adapter_claim_collection_report",
)
_ADAPTER_EVENT_FIELDS = frozenset(
    {
        "adapter_ids",
        "base_input_address",
        "effective_input_address",
        "registry_bundle_address",
        "registry_address",
        "resolution_bundle_address",
        "resolution_address",
        "claim_collection_bundle_address",
        "claim_collection_address",
        "resolved_element_count",
        "attribution_count",
        "claim_count",
        "source_bundle_addresses",
    }
)
_SNAPSHOT_PREDECESSOR_VERSION = "snapshot-predecessor-v1"
_SNAPSHOT_PREDECESSOR_FIELDS = frozenset(
    {
        "version",
        "run_id",
        "previous_event_address",
        "previous_dossier_address",
        "binding_address",
    }
)
_SNAPSHOT_SUCCESSOR_EVENT_TYPES = frozenset({"review_assigned", "review_recorded"})
_REVIEW_ASSIGNMENT_FIELDS = frozenset(
    {
        "assignment_id",
        "run_id",
        "case_id",
        "reviewer",
        "queue_id",
        "due_at",
        "note",
        "created_at",
        "content_address",
    }
)
_RNA_CONSEQUENCE_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "prediction_id",
        "prediction_address",
        "variant_id",
        "feature_id",
        "context_key",
        "predicted_direction",
        "state",
        "expression_state",
        "expression_direction",
        "expression_robust_z",
        "expression_result_address",
        "allelic_state",
        "allelic_direction",
        "allelic_log2_ratio",
        "allelic_q_value",
        "allelic_result_address",
        "reason_codes",
        "content_address",
    }
)
_VERIFIED_RUN_RECORD_FIELDS = frozenset(
    {
        "run_id",
        "input_address",
        "event_address",
        "event_history",
        "dossier_address",
        "dossier_history",
    }
)


def _runtime_sha256_address(value: object, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValidationError(f"{label} must be a canonical sha256 content address")
    return value


@dataclass(frozen=True, slots=True)
class VerifiedRunSnapshot:
    """Detached, typed closure over one replay-verified current run."""

    run_record: Mapping[str, Any]
    manifest: CaseManifest
    event_record: Mapping[str, Any]
    dossier: Dossier
    replay: ReplayReport

    def __post_init__(self) -> None:
        if type(self.run_record) is not dict or set(self.run_record) != _VERIFIED_RUN_RECORD_FIELDS:
            raise ValidationError(
                "verified snapshot run_record must be an exact current run object"
            )
        if type(self.manifest) is not CaseManifest:
            raise ValidationError("verified snapshot manifest must be an exact CaseManifest")
        if type(self.event_record) is not dict:
            raise ValidationError("verified snapshot event_record must be an exact object")
        if type(self.dossier) is not Dossier:
            raise ValidationError("verified snapshot dossier must be an exact Dossier")
        if type(self.replay) is not ReplayReport:
            raise ValidationError("verified snapshot replay must be an exact ReplayReport")
        record = dict(self.run_record)
        run_id = record["run_id"]
        input_address = record["input_address"]
        event_address = record["event_address"]
        dossier_address = record["dossier_address"]
        if type(run_id) is not str or not run_id.startswith("run-") or len(run_id) > 128:
            raise ValidationError("verified snapshot run_id must be a bounded run identifier")
        for field, value in (
            ("input_address", input_address),
            ("event_address", event_address),
            ("dossier_address", dossier_address),
        ):
            _runtime_sha256_address(value, f"verified snapshot {field}")
        for history_field, current in (
            ("event_history", event_address),
            ("dossier_history", dossier_address),
        ):
            history = record[history_field]
            if (
                type(history) is not list
                or not history
                or len(history) > MAX_RUN_HISTORY_ENTRIES
                or any(type(item) is not str for item in history)
                or any(
                    _runtime_sha256_address(item, f"verified snapshot {history_field} entry")
                    != item
                    for item in history
                )
                or len(history) != len(set(history))
                or history[-1] != current
            ):
                raise ValidationError(
                    f"verified snapshot {history_field} must be a unique current-ended address list"
                )
        if len(record["event_history"]) > len(record["dossier_history"]):
            raise ValidationError(
                "verified snapshot event history cannot exceed its dossier history"
            )
        try:
            log = EventLog.from_record(
                self.event_record,
                expected_address=event_address,
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError("verified snapshot event record is invalid") from exc
        if not log.verify():
            raise ValidationError("verified snapshot event record must contain a valid chain")
        event_record = log.to_record()
        dossier_record = self.dossier.to_dict()
        dossier_body = {
            key: value for key, value in dossier_record.items() if key != "content_address"
        }
        expected_replay = ReplayVerifier().verify(record, event_record, dossier_record)
        if (
            run_id != self.dossier.run_id
            or log.run_id != run_id
            or self.dossier.case_id != self.manifest.case_id
            or self.dossier.input_address != self.manifest.content_address
            or input_address != self.manifest.content_address
            or event_address != content_hash(event_record)
            or dossier_address != content_hash(dossier_body)
            or self.dossier.content_address != dossier_address
            or self.dossier.event_head != log.head
            or not expected_replay.event_chain_valid
            or not expected_replay.stored_dossier_matches_address
            or canonical_bytes(self.replay.to_dict()) != canonical_bytes(expected_replay.to_dict())
        ):
            raise ValidationError("verified snapshot artifacts do not form one replay-closed run")
        frozen_record = freeze_json(record, field="verified snapshot run_record")
        if not isinstance(frozen_record, Mapping):  # pragma: no cover - guarded above
            raise ValidationError("verified snapshot run_record must remain an object")
        object.__setattr__(self, "run_record", frozen_record)
        frozen_events = freeze_json(event_record, field="verified snapshot event_record")
        if not isinstance(frozen_events, Mapping):  # pragma: no cover - exact dict above
            raise ValidationError("verified snapshot event_record must remain an object")
        object.__setattr__(self, "event_record", frozen_events)

    @property
    def run_id(self) -> str:
        return self.dossier.run_id

    @property
    def event_log(self) -> EventLog:
        """Return a fresh mutable log detached from the verified snapshot."""

        raw = jsonable(self.event_record)
        if type(raw) is not dict:  # pragma: no cover - constructor invariant
            raise ValidationError("verified snapshot event_record copy must be an object")
        event_address = self.run_record.get("event_address")
        try:
            return EventLog.from_record(
                raw,
                expected_address=event_address if type(event_address) is str else None,
            )
        except (TypeError, ValueError) as exc:  # pragma: no cover - constructor invariant
            raise ValidationError("verified snapshot event log could not be detached") from exc

    def run_record_dict(self) -> dict[str, Any]:
        """Return a mutable canonical copy for compare-and-swap persistence."""

        value = jsonable(self.run_record)
        if type(value) is not dict:  # pragma: no cover - frozen mapping is guaranteed above
            raise ValidationError("verified snapshot run_record copy must be an object")
        return value


class CaseRuntime:
    """Coordinate typed inputs, deterministic builders, policy, and storage."""

    def __init__(
        self,
        data_root: str | Path = ".glio",
        *,
        reference_retriever: PublicReferenceRetriever | None = None,
        atlas_retriever: PublicAtlasRetriever | None = None,
        adapter_registry: AdapterRegistry | None = None,
        hypothesis_limits: HypothesisWorkLimits | None = None,
        experiment_limits: ExperimentPlanningLimits | None = None,
        rna_input_max_bytes: int = _MAX_RUNTIME_RNA_INPUT_BYTES,
    ) -> None:
        if type(rna_input_max_bytes) is not int or not 1 <= rna_input_max_bytes <= (
            _MAX_RUNTIME_RNA_INPUT_BYTES
        ):
            raise ValidationError(
                "rna_input_max_bytes must be a positive integer no greater than "
                f"{_MAX_RUNTIME_RNA_INPUT_BYTES}"
            )
        if adapter_registry is not None and type(adapter_registry) is not AdapterRegistry:
            raise ValidationError("adapter_registry must be an exact AdapterRegistry")
        builder = HypothesisBuilder(limits=hypothesis_limits)
        planner = ExperimentPlanner(limits=experiment_limits)
        self.store = RunStore(data_root)
        self.builder = builder
        self.planner = planner
        self.policy = ResearchPolicy()
        self.validator = ContractValidator()
        self.release_gate = ReleaseGate(self.policy)
        self.reference_retriever = reference_retriever
        self.atlas_retriever = atlas_retriever
        self.adapter_registry = adapter_registry
        self._rna_input_max_bytes = rna_input_max_bytes
        self._logs: dict[str, EventLog] = {}

    def _link_atlas_claims(
        self,
        manifest: CaseManifest,
        bundles: tuple[AtlasBundle, ...],
    ) -> tuple[tuple[EvidenceClaim, ...], tuple[str, ...]]:
        """Bind variant-scoped atlas observations once to the best eligible element edge."""

        if type(manifest) is not CaseManifest:
            raise ValidationError("atlas claim linking requires an exact CaseManifest")
        if type(bundles) is not tuple or any(type(bundle) is not AtlasBundle for bundle in bundles):
            raise ValidationError("atlas claim linking requires exact AtlasBundle values")
        if len(bundles) != len(manifest.variants):
            raise ValidationError("atlas bundles must cover every manifest variant exactly once")
        claims: list[EvidenceClaim] = []
        warnings: list[str] = []
        for variant, bundle in zip(manifest.variants, bundles, strict=True):
            if bundle.variant_id != variant.variant_id:
                raise ValidationError("atlas bundle order does not match manifest variants")
            eligible = self.builder._eligible_elements(  # noqa: SLF001 - one runtime/builder seam
                variant,
                manifest.candidate_elements,
            )
            if not eligible:
                if bundle.observations:
                    warnings.append(
                        f"Atlas observations for {variant.variant_id} were retained in their "
                        "source bundle but not promoted to claims because no eligible element "
                        "edge exists."
                    )
                continue
            selected = min(
                eligible,
                key=lambda element: (
                    -element_relevance(variant, element)[0],
                    element.element_id,
                ),
            )
            edge_id = self.builder._edge_id(  # noqa: SLF001 - deterministic builder contract
                variant.variant_id,
                selected.element_id,
                EdgeType.VARIANT_TO_ELEMENT,
            )
            linked = bundle.to_evidence_claims(
                variant=variant,
                context=manifest.context,
                edge_id=edge_id,
            )
            claims.extend(linked)
            if linked and len(eligible) > 1:
                warnings.append(
                    f"Atlas observations for {variant.variant_id} were linked once to "
                    f"highest-relevance element {selected.element_id}; {len(eligible) - 1} "
                    "additional eligible element edge(s) were not duplicated."
                )
        return tuple(claims), tuple(warnings)

    @staticmethod
    def _materialize_adapter_manifest(
        manifest: CaseManifest,
        resolution: AdapterResolutionReport,
        source_addresses: tuple[str, ...],
    ) -> CaseManifest:
        """Merge resolved elements and bind every adapter input into run identity."""

        if type(manifest) is not CaseManifest or type(resolution) is not AdapterResolutionReport:
            raise ValidationError("adapter materialization requires exact typed inputs")
        if resolution.manifest_address != manifest.content_address:
            raise ValidationError("adapter resolution does not belong to its base manifest")
        if len(source_addresses) != len(_ADAPTER_INPUT_VERSION_KEYS):
            raise ValidationError("adapter materialization source closure is incomplete")
        elements = {element.element_id: element for element in manifest.candidate_elements}
        for element in resolution.elements:
            existing = elements.get(element.element_id)
            if existing is not None and canonical_bytes(existing.to_dict()) != canonical_bytes(
                element.to_dict()
            ):
                raise ValidationError(
                    "adapter element conflicts with an existing manifest element: "
                    f"{element.element_id}"
                )
            elements[element.element_id] = element
        additions = dict(zip(_ADAPTER_INPUT_VERSION_KEYS, source_addresses, strict=True))
        versions = dict(manifest.input_versions)
        for key, address in additions.items():
            existing_version = versions.get(key)
            if existing_version is not None and existing_version != address:
                raise ValidationError(f"manifest input_versions reserves adapter key: {key}")
            versions[key] = address
        return replace(
            manifest,
            candidate_elements=tuple(elements[key] for key in sorted(elements)),
            input_versions=dict(sorted(versions.items())),
        )

    def evaluate(
        self,
        manifest: CaseManifest,
        *,
        live_reference: bool = False,
        rna_consequences: Iterable[RNAConsequenceEvidence] = (),
        adapter_ids: tuple[str, ...] = (),
    ) -> Dossier:
        """Evaluate a manifest and persist its immutable output."""

        if type(live_reference) is not bool:
            raise ValidationError("live_reference must be an exact boolean")
        if type(adapter_ids) is not tuple or any(type(item) is not str for item in adapter_ids):
            raise ValidationError("adapter_ids must be an exact tuple of strings")
        if adapter_ids and self.adapter_registry is None:
            raise ValidationError("adapter_ids require a configured AdapterRegistry")
        self._validate_manifest_contract(manifest, "case manifest")
        rna_rows = self.builder.validate_inputs(
            manifest,
            rna_consequences=rna_consequences,
        )
        self._enforce_policy_texts((manifest.case_id, manifest.requested_by), "manifest")
        submitted_input_address = manifest.content_address
        build_manifest = manifest
        source_records: dict[str, Mapping[str, Any]] = {}
        source_receipts: tuple[Mapping[str, Any], ...] = ()
        source_bundle_addresses: tuple[str, ...] = ()
        reference_bundle_addresses: tuple[str, ...] = ()
        reference_receipt_count = 0
        atlas_bundle_addresses: tuple[str, ...] = ()
        atlas_event_warnings: tuple[str, ...] = ()
        runtime_warnings: tuple[str, ...] = ()
        atlas_claims: tuple[EvidenceClaim, ...] = ()
        adapter_claims: tuple[EvidenceClaim, ...] = ()
        adapter_resolution: AdapterResolutionReport | None = None
        adapter_claim_report: AdapterClaimCollectionReport | None = None
        adapter_source_addresses: tuple[str, ...] = ()
        enrichment: EnrichmentResult | None = None
        if live_reference:
            retriever = self.reference_retriever or PublicReferenceRetriever(
                cache_root=Path(self.store.root) / "source-cache"
            )
            self.reference_retriever = retriever
            enrichment = retriever.enrich_manifest(manifest)
            build_manifest = enrichment.manifest
            self._validate_manifest_contract(build_manifest, "enriched case manifest")
            self.builder.validate_inputs(
                build_manifest,
                rna_consequences=rna_rows,
            )
            reference_records = tuple(bundle.to_dict() for bundle in enrichment.bundles)
            reference_bundle_addresses = tuple(content_hash(record) for record in reference_records)
            source_records.update(zip(reference_bundle_addresses, reference_records, strict=True))
            source_receipts = tuple(
                receipt.to_dict() for bundle in enrichment.bundles for receipt in bundle.receipts
            )
            reference_receipt_count = len(source_receipts)
            runtime_warnings = enrichment.warnings
            if self.atlas_retriever is not None or isinstance(retriever, PublicReferenceRetriever):
                atlas_retriever = self.atlas_retriever or PublicAtlasRetriever(retriever)
                atlas_bundles = tuple(
                    (
                        atlas_retriever.retrieve(
                            variant,
                            build_manifest.context,
                            query=AtlasQuery(
                                variant_id=variant.variant_id,
                                window_bp=getattr(retriever, "window_bp", 2_000),
                            ),
                        )
                        if isinstance(atlas_retriever, PublicAtlasRetriever)
                        else atlas_retriever.retrieve(variant, build_manifest.context)
                    )
                    for variant in build_manifest.variants
                )
                atlas_records = tuple(bundle.to_dict() for bundle in atlas_bundles)
                atlas_bundle_addresses = tuple(content_hash(record) for record in atlas_records)
                source_records.update(zip(atlas_bundle_addresses, atlas_records, strict=True))
                source_receipts += tuple(
                    receipt.to_dict() for bundle in atlas_bundles for receipt in bundle.receipts
                )
                atlas_claims, atlas_link_warnings = self._link_atlas_claims(
                    build_manifest,
                    atlas_bundles,
                )
                atlas_warnings = tuple(
                    warning for bundle in atlas_bundles for warning in bundle.warnings
                )
                atlas_event_warnings = tuple(dict.fromkeys(atlas_warnings + atlas_link_warnings))
                runtime_warnings = tuple(
                    dict.fromkeys(runtime_warnings + atlas_event_warnings)
                )
        if adapter_ids:
            registry = self.adapter_registry
            if registry is None or type(registry) is not AdapterRegistry:
                raise ValidationError("adapter registry configuration is invalid")
            adapter_base_manifest = build_manifest
            adapter_resolution = registry.resolve_manifest(adapter_base_manifest, adapter_ids)
            adapter_claim_report = registry.collect_claims(
                adapter_base_manifest,
                adapter_resolution,
            )
            adapter_records = (
                adapter_base_manifest.to_dict(),
                adapter_claim_report.registry_snapshot.to_dict(),
                adapter_resolution.to_dict(),
                adapter_claim_report.to_dict(),
            )
            adapter_source_addresses = tuple(content_hash(record) for record in adapter_records)
            for address, record in zip(
                adapter_source_addresses,
                adapter_records,
                strict=True,
            ):
                existing = source_records.get(address)
                if existing is not None and canonical_bytes(existing) != canonical_bytes(record):
                    raise ValidationError("adapter source address collides with another source")
                source_records[address] = record
            build_manifest = self._materialize_adapter_manifest(
                adapter_base_manifest,
                adapter_resolution,
                adapter_source_addresses,
            )
            self._validate_manifest_contract(build_manifest, "adapter-enriched case manifest")
            self.builder.validate_inputs(
                build_manifest,
                rna_consequences=rna_rows,
            )
            adapter_claims = adapter_claim_report.claims
        source_bundle_addresses = tuple(source_records)

        run_id = self._run_id(build_manifest, rna_rows)
        if live_reference and (self.store.runs / f"{run_id}.json").exists():
            conflict = StoreError(f"run already exists: {run_id}")
            raise ValidationError(f"run publication failed: {conflict}") from conflict
        log = EventLog(run_id)
        input_record = build_manifest.to_dict()
        input_address = content_hash(input_record)
        rna_input: dict[str, Any] | None = None
        rna_input_address: str | None = None
        case_received_payload: dict[str, Any] = {
            "input_address": input_address,
            "case_id": manifest.case_id,
        }
        if rna_rows:
            for row in rna_rows:
                validate_rna_consequence(row)
            rna_input = {
                "schema_version": "1.0.0",
                "kind": "rna_consequence_batch",
                "consequences": [
                    item.to_dict() for item in sorted(rna_rows, key=lambda row: row.content_address)
                ],
            }
            self._preflight_rna_input_rows(
                rna_input["consequences"],
                expected_count=len(rna_rows),
            )
            if len(canonical_bytes(rna_input)) > self._rna_input_max_bytes:
                raise ValidationError(
                    "RNA input exceeds the configured persisted byte ceiling of "
                    f"{self._rna_input_max_bytes}"
                )
            rna_input_address = content_hash(rna_input)
            case_received_payload.update(
                {
                    "rna_input_address": rna_input_address,
                    "rna_consequence_count": len(rna_rows),
                }
            )
        log.append(
            "case_received",
            case_received_payload,
            event_id=f"evt-{run_id}-received",
        )
        if live_reference:
            if enrichment is None:  # pragma: no cover - guarded by live preparation
                raise ValidationError("live reference preparation is incomplete")
            log.append(
                "public_reference_enriched",
                {
                    "submitted_input_address": submitted_input_address,
                    "effective_input_address": input_address,
                    "bundle_addresses": list(reference_bundle_addresses),
                    "receipt_count": reference_receipt_count,
                    "warnings": list(enrichment.warnings),
                },
                event_id=f"evt-{run_id}-reference",
            )
            if atlas_bundle_addresses:
                log.append(
                    "public_atlas_collected",
                    {
                        "bundle_addresses": list(atlas_bundle_addresses),
                        "claim_count": len(atlas_claims),
                        "warnings": list(atlas_event_warnings),
                    },
                    event_id=f"evt-{run_id}-atlas",
                )
        if adapter_resolution is not None and adapter_claim_report is not None:
            log.append(
                "adapter_evidence_collected",
                {
                    "adapter_ids": list(adapter_resolution.adapter_ids),
                    "base_input_address": adapter_resolution.manifest_address,
                    "effective_input_address": input_address,
                    "registry_bundle_address": adapter_source_addresses[1],
                    "registry_address": adapter_resolution.registry_address,
                    "resolution_bundle_address": adapter_source_addresses[2],
                    "resolution_address": adapter_resolution.content_address,
                    "claim_collection_bundle_address": adapter_source_addresses[3],
                    "claim_collection_address": adapter_claim_report.content_address,
                    "resolved_element_count": adapter_resolution.element_count,
                    "attribution_count": adapter_claim_report.attribution_count,
                    "claim_count": adapter_claim_report.claim_count,
                    "source_bundle_addresses": list(adapter_source_addresses),
                },
                event_id=f"evt-{run_id}-adapters",
            )
        built = self.builder.build(
            build_manifest,
            run_id,
            rna_consequences=rna_rows,
            retained_owner_address=rna_input_address,
            external_claims=atlas_claims + adapter_claims,
        )
        all_warnings = tuple(dict.fromkeys(tuple(built.warnings) + runtime_warnings))
        log.append(
            "hypotheses_built",
            {
                "hypothesis_count": len(built.hypotheses),
                "claim_count": len(built.claims),
                "warnings": list(all_warnings),
            },
            event_id=f"evt-{run_id}-built",
        )
        experiments = self.planner.plan_many(built.hypotheses)
        log.append(
            "validation_routes_planned",
            {"experiment_count": len(experiments)},
            event_id=f"evt-{run_id}-planned",
        )
        declared_source_addresses = (
            source_bundle_addresses
            if rna_input_address is None
            else (rna_input_address, *source_bundle_addresses)
        )
        dossier = self._make_dossier(
            manifest=build_manifest,
            run_id=run_id,
            input_address=input_address,
            hypotheses=built.hypotheses,
            claims=built.claims,
            experiments=experiments,
            review=None,
            status=ResearchStatus.REVIEW_REQUIRED,
            event_head=log.head,
            warnings=all_warnings,
            source_receipts=source_receipts,
            source_bundle_addresses=declared_source_addresses,
        )
        self._validate_dossier_contract(dossier, "draft dossier")
        decision = self._policy_dossier_decision(dossier, "draft dossier")
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.violations))
        log.append(
            "dossier_created", {"dossier_id": dossier.dossier_id}, event_id=f"evt-{run_id}-dossier"
        )
        dossier = self._readdress(replace(dossier, event_head=log.head))
        self._validate_dossier_contract(dossier, "final dossier")
        if not live_reference:
            reused = self._reuse_untouched_offline_draft(dossier, log)
            if reused is not None:
                return reused
        for address, source_record in source_records.items():
            if self.store.store.put_at(address, source_record) != address:
                raise ValidationError("source bundle address changed during evaluation")
        if self.store.store.put(input_record) != input_address:
            raise ValidationError("manifest input address changed during evaluation")
        if rna_input is not None:
            expected_rna_address = case_received_payload["rna_input_address"]
            if self.store.store.put(rna_input) != expected_rna_address:
                raise ValidationError("RNA input address changed during evaluation")
        try:
            self._persist(build_manifest, log, dossier, input_address)
        except ValidationError as exc:
            cause = exc.__cause__
            exact_create_conflict = (
                not live_reference
                and type(cause) is StoreError
                and str(cause) == f"run already exists: {run_id}"
            )
            if not exact_create_conflict:
                raise
            reused = self._reuse_untouched_offline_draft(dossier, log)
            if reused is None:  # pragma: no cover - create conflict requires an index
                raise
            return reused
        self._logs[run_id] = log
        return dossier

    def review(self, dossier: Dossier, review: ReviewDecision) -> Dossier:
        """Attach a review decision and create a new immutable dossier snapshot."""

        self._validate_dossier_contract(dossier, "source dossier")
        persisted, staged_log, run_record = self._load_current_snapshot(dossier.run_id)
        if canonical_bytes(dossier.to_dict()) != canonical_bytes(persisted.to_dict()):
            raise ValidationError("dossier is not the current persisted run snapshot")
        return self._review_candidate(
            dossier,
            review,
            staged_log=staged_log,
            expected_run=run_record,
        )

    def review_run(self, run_id: str, review: ReviewDecision) -> Dossier:
        """Reopen a persisted run, attach a review, and persist a new snapshot."""

        dossier, staged_log, run_record = self._load_current_snapshot(run_id)
        return self._review_candidate(
            dossier,
            review,
            staged_log=staged_log,
            expected_run=run_record,
        )

    def _review_candidate(
        self,
        dossier: Dossier,
        review: ReviewDecision,
        *,
        staged_log: EventLog,
        expected_run: dict[str, Any],
    ) -> Dossier:
        """Build and commit one review against a detached, verified event log."""

        self._require_exact_policy()
        self._validate_review_input(dossier, review)
        self._append_snapshot_predecessor_binding(staged_log, expected_run)
        staged_log.append("review_recorded", review.to_dict(), event_id=review.review_id)
        status = (
            ResearchStatus.RELEASED_RESEARCH
            if review.state is ReviewState.ACCEPTED
            else ResearchStatus.REVIEWED
        )
        updated = self._make_dossier(
            manifest=None,
            run_id=dossier.run_id,
            input_address=dossier.input_address,
            hypotheses=dossier.hypotheses,
            claims=dossier.evidence,
            experiments=dossier.experiments,
            review=review,
            status=status,
            event_head=staged_log.head,
            warnings=dossier.warnings,
            case_id=dossier.case_id,
            created_at=dossier.created_at,
            source_receipts=dossier.source_receipts,
            source_bundle_addresses=dossier.source_bundle_addresses,
        )
        self._validate_dossier_contract(updated, "reviewed dossier")
        decision = self._policy_dossier_decision(updated, "reviewed dossier")
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.violations))
        if review.state is ReviewState.ACCEPTED:
            self._check_release(updated, "release gate")
        self._persist(
            None,
            staged_log,
            updated,
            dossier.input_address,
            expected_run=expected_run,
        )
        self._logs[dossier.run_id] = staged_log
        return updated

    def _validate_review_input(self, dossier: Dossier, review: ReviewDecision) -> None:
        """Reject forged, oversized, or snapshot-incomplete reviews before staging."""

        validator = self._require_exact_validator(self.validator, "runtime validator")
        if type(review) is not ReviewDecision:
            raise ValidationError("review must be an exact ReviewDecision")
        if type(review.state) is not ReviewState:
            raise ValidationError("review state must be an exact ReviewState")
        scalar_values = (
            review.review_id,
            review.case_id,
            review.reviewer,
            review.rationale,
            review.created_at,
        )
        if any(type(value) is not str for value in scalar_values):
            raise ValidationError("review scalar fields must be exact strings")
        if type(review.reviewed_hypothesis_ids) is not tuple or any(
            type(value) is not str for value in review.reviewed_hypothesis_ids
        ):
            raise ValidationError("reviewed_hypothesis_ids must be an exact tuple of strings")
        if type(review.checked_claim_ids) is not tuple or any(
            type(value) is not str for value in review.checked_claim_ids
        ):
            raise ValidationError("checked_claim_ids must be an exact tuple of strings")
        if len(review.reviewed_hypothesis_ids) > len(dossier.hypotheses):
            raise ValidationError("review names more hypotheses than the current snapshot contains")
        if len(review.checked_claim_ids) > len(dossier.evidence):
            raise ValidationError("review names more claims than the current snapshot contains")
        all_strings = (
            *scalar_values,
            *review.reviewed_hypothesis_ids,
            *review.checked_claim_ids,
        )
        limits = validator.limits
        if any(len(value) > limits.max_string_characters for value in all_strings):
            raise ValidationError("review contains a string that exceeds validation limits")
        if sum(len(value) for value in all_strings) > limits.max_total_characters:
            raise ValidationError("review strings exceed aggregate validation limits")
        try:
            raw = review.to_dict()
            canonical = ReviewDecision.from_dict(raw, persisted=True)
            if canonical_bytes(raw) != canonical_bytes(canonical.to_dict()):
                raise ValidationError("review does not round-trip exactly")
        except Exception as exc:  # noqa: BLE001 - hostile review objects fail closed
            raise ValidationError("review is not an exact canonical ReviewDecision") from exc
        if review.case_id != dossier.case_id:
            raise ValidationError("review case_id does not match dossier")
        known_hypotheses = {hypothesis.hypothesis_id for hypothesis in dossier.hypotheses}
        reviewed_hypotheses = set(review.reviewed_hypothesis_ids)
        unknown_hypotheses = reviewed_hypotheses - known_hypotheses
        if unknown_hypotheses:
            raise ValidationError(f"review names unknown hypotheses: {sorted(unknown_hypotheses)}")
        known_claims = {claim.evidence_id for claim in dossier.evidence}
        checked_claims = set(review.checked_claim_ids)
        unknown_claims = checked_claims - known_claims
        if unknown_claims:
            raise ValidationError(f"review names unknown claims: {sorted(unknown_claims)}")
        if review.state is ReviewState.ACCEPTED:
            if reviewed_hypotheses != known_hypotheses:
                raise ValidationError(
                    "accepted review must cover every hypothesis in the current snapshot"
                )
            if checked_claims != known_claims:
                raise ValidationError(
                    "accepted review must cover every evidence claim in the current snapshot"
                )

    def _persisted_object_max_bytes(self) -> int:
        validator = self._require_exact_validator(self.validator, "runtime validator")
        return validator.limits.max_canonical_bytes

    @property
    def persisted_object_max_bytes(self) -> int:
        """Return the revalidated canonical-object ceiling used by runtime loaders."""

        return self._persisted_object_max_bytes()

    def load_manifest(self, input_address: str) -> CaseManifest:
        """Load one bounded, address-closed, exact persisted case manifest."""

        try:
            raw = self.store.store.get_verified(
                input_address,
                max_bytes=self._persisted_object_max_bytes(),
            )
            if type(raw) is not dict:
                raise ValidationError("persisted manifest input must be an exact object")
            manifest = CaseManifest.from_dict(raw)
            if (
                manifest.content_address != input_address
                or canonical_bytes(manifest.to_dict()) != canonical_bytes(raw)
            ):
                raise ValidationError("persisted manifest input does not round-trip exactly")
            self._validate_manifest_contract(manifest, "persisted manifest input")
            return manifest
        except Exception as exc:  # noqa: BLE001 - stored inputs are hostile
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(
                "persisted manifest input object is missing or invalid"
            ) from exc

    def load_event_log(self, event_address: str) -> EventLog:
        """Load one bounded, address-closed, exact persisted event log."""

        try:
            raw = self.store.store.get_verified(
                event_address,
                max_bytes=MAX_EVENT_RECORD_BYTES,
            )
            if type(raw) is not dict:
                raise ValidationError("persisted event record must be an exact object")
            log = EventLog.from_record(raw, expected_address=event_address)
            if not log.verify() or canonical_bytes(log.to_record()) != canonical_bytes(raw):
                raise ValidationError("persisted event record does not round-trip exactly")
            return log
        except Exception as exc:  # noqa: BLE001 - stored events are hostile
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("persisted event record is missing or invalid") from exc

    def load_dossier(self, dossier_address: str) -> Dossier:
        """Load one bounded, canonical, exact persisted dossier snapshot."""

        try:
            raw = self.store.store.get_canonical(
                dossier_address,
                max_bytes=self._persisted_object_max_bytes(),
            )
            if type(raw) is not dict:
                raise ValidationError("persisted dossier must be an exact object")
            dossier = Dossier.from_dict(raw)
            if (
                dossier.content_address != dossier_address
                or self._dossier_address(dossier) != dossier_address
                or canonical_bytes(dossier.to_dict()) != canonical_bytes(raw)
            ):
                raise ValidationError("persisted dossier does not round-trip exactly")
            self._validate_dossier_contract(dossier, "persisted dossier")
            return dossier
        except Exception as exc:  # noqa: BLE001 - stored dossiers are hostile
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(
                "persisted dossier is missing or invalid; run has invalid persisted artifacts"
            ) from exc

    def load_run_snapshot(self, run_id: str) -> VerifiedRunSnapshot:
        """Load the current typed run closure and require complete replay integrity."""

        # Keep an absent/invalid run index distinguishable from corruption of an
        # existing run's referenced immutable objects.
        run_record = self.get_run(run_id)
        return self._load_run_snapshot_record(run_id, run_record)

    def load_run_snapshot_at(
        self,
        run_id: str,
        *,
        event_address: str,
        dossier_address: str,
    ) -> VerifiedRunSnapshot:
        """Reopen one paired immutable snapshot retained in a run's append-only history."""

        selected_event = _runtime_sha256_address(
            event_address,
            "historical snapshot event_address",
        )
        selected_dossier = _runtime_sha256_address(
            dossier_address,
            "historical snapshot dossier_address",
        )
        current = self.get_run(run_id)
        current_snapshot = self._load_run_snapshot_record(run_id, current)
        current_record = current_snapshot.run_record_dict()
        event_history = current_record["event_history"]
        dossier_history = current_record["dossier_history"]
        if type(event_history) is not list or type(dossier_history) is not list:
            raise ValidationError("run history must contain exact address arrays")
        if (
            not event_history
            or not dossier_history
            or len(event_history) != len(set(event_history))
            or len(dossier_history) != len(set(dossier_history))
            or event_history[-1] != current_record["event_address"]
            or dossier_history[-1] != current_record["dossier_address"]
        ):
            raise ValidationError("run histories must be unique and current-ended")
        if len(event_history) > len(dossier_history):
            raise ValidationError("run event and dossier histories cannot be paired")
        # Supported legacy indexes may retain dossiers that predate event-history
        # persistence. Every recorded event still pairs unambiguously with the
        # same-position item in the right-aligned dossier suffix; older dossier-only
        # entries intentionally remain unavailable through this API.
        dossier_offset = len(dossier_history) - len(event_history)
        try:
            event_index = event_history.index(selected_event)
            dossier_index = dossier_history.index(selected_dossier)
        except ValueError as exc:
            raise ValidationError("requested snapshot is absent from the run history") from exc
        if dossier_index != event_index + dossier_offset:
            raise ValidationError("requested event and dossier addresses are not a paired snapshot")
        if (
            selected_event == current_record["event_address"]
            and selected_dossier == current_record["dossier_address"]
        ):
            return current_snapshot
        historical = dict(current_record)
        historical["event_address"] = selected_event
        historical["dossier_address"] = selected_dossier
        historical["event_history"] = event_history[: event_index + 1]
        historical["dossier_history"] = dossier_history[: dossier_index + 1]
        selected_snapshot = self._load_run_snapshot_record(run_id, historical)
        selected_events = selected_snapshot.event_log.to_record()["events"]
        current_events = current_snapshot.event_log.to_record()["events"]
        if (
            len(selected_events) >= len(current_events)
            or canonical_bytes(selected_events)
            != canonical_bytes(current_events[: len(selected_events)])
        ):
            raise ValidationError(
                "requested historical event log is not an ancestor of the current run"
            )
        successor = current_events[len(selected_events)]
        if type(successor) is not dict or successor.get(
            "event_type"
        ) != "snapshot_predecessor_bound":
            raise ValidationError(
                "requested historical snapshot has no authenticated successor binding"
            )
        bound_pair = self._snapshot_predecessor_pair(successor, run_id=run_id)
        if bound_pair != (selected_event, selected_dossier):
            raise ValidationError(
                "requested historical snapshot does not match its successor binding"
            )
        return selected_snapshot

    @staticmethod
    def _snapshot_predecessor_pair(
        event: Mapping[str, Any],
        *,
        run_id: str,
        expected_event_address: str | None = None,
    ) -> tuple[str, str]:
        """Validate one canonical predecessor event and return its bound pair."""

        if (
            type(event) is not dict
            or event.get("event_type") != "snapshot_predecessor_bound"
            or type(event.get("payload")) is not dict
        ):
            raise ValidationError("snapshot predecessor binding has a non-canonical shape")
        payload = event["payload"]
        if set(payload) != _SNAPSHOT_PREDECESSOR_FIELDS:
            raise ValidationError("snapshot predecessor binding has a non-canonical shape")
        previous_event = _runtime_sha256_address(
            payload.get("previous_event_address"),
            "snapshot predecessor previous_event_address",
        )
        previous_dossier = _runtime_sha256_address(
            payload.get("previous_dossier_address"),
            "snapshot predecessor previous_dossier_address",
        )
        body = {
            "version": _SNAPSHOT_PREDECESSOR_VERSION,
            "run_id": run_id,
            "previous_event_address": previous_event,
            "previous_dossier_address": previous_dossier,
        }
        expected_binding = content_hash(body, prefix="snapshot-predecessor")
        binding_digest = expected_binding.rsplit(":", 1)[1]
        expected_event_id = f"evt-{run_id}-predecessor-{binding_digest[:20]}"
        if (
            payload.get("version") != _SNAPSHOT_PREDECESSOR_VERSION
            or payload.get("run_id") != run_id
            or payload.get("binding_address") != expected_binding
            or event.get("event_id") != expected_event_id
        ):
            raise ValidationError("snapshot predecessor binding does not verify")
        if (
            expected_event_address is not None
            and previous_event != expected_event_address
        ):
            raise ValidationError(
                "snapshot predecessor binding does not address its exact event prefix"
            )
        return previous_event, previous_dossier

    def _validate_retained_snapshot_history(
        self,
        run_id: str,
        run_record: Mapping[str, Any],
        log: EventLog,
    ) -> None:
        """Authenticate the retained modern history suffix from binding events."""

        event_history = run_record["event_history"]
        dossier_history = run_record["dossier_history"]
        dossier_offset = len(dossier_history) - len(event_history)
        retained_pairs = tuple(
            zip(event_history, dossier_history[dossier_offset:], strict=True)
        )
        event_rows = log.to_record()["events"]
        empty_record = canonical_bytes({"events": [], "run_id": run_id})
        record_prefix, marker, record_suffix = empty_record.partition(b"[]")
        if marker != b"[]":  # pragma: no cover - canonical serializer invariant
            raise ValidationError("cannot derive the canonical event-record envelope")
        prefix_hasher = hashlib.sha256(record_prefix + b"[")
        record_tail = b"]" + record_suffix

        bindings: list[tuple[str, str]] = []
        binding_indexes: list[int] = []
        for index, event in enumerate(event_rows):
            if event.get("event_type") == "snapshot_predecessor_bound":
                prefix_probe = prefix_hasher.copy()
                prefix_probe.update(record_tail)
                expected_prefix_address = f"sha256:{prefix_probe.hexdigest()}"
                pair = self._snapshot_predecessor_pair(
                    event,
                    run_id=run_id,
                    expected_event_address=expected_prefix_address,
                )
                if index + 1 >= len(event_rows) or event_rows[index + 1].get(
                    "event_type"
                ) not in _SNAPSHOT_SUCCESSOR_EVENT_TYPES:
                    raise ValidationError(
                        "snapshot predecessor binding must immediately precede one transition"
                    )
                if binding_indexes and index != binding_indexes[-1] + 2:
                    raise ValidationError(
                        "modern snapshot transitions must form one contiguous event suffix"
                    )
                bindings.append(pair)
                binding_indexes.append(index)
            if index:
                prefix_hasher.update(b",")
            prefix_hasher.update(canonical_bytes(event))

        if not bindings:
            return
        if binding_indexes[-1] != len(event_rows) - 2:
            raise ValidationError(
                "modern snapshot transitions must end at the current event head"
            )
        modern_pairs = (*bindings, (run_record["event_address"], run_record["dossier_address"]))
        if len(modern_pairs) != len(set(modern_pairs)):
            raise ValidationError("modern snapshot predecessor pairs must be unique")

        overlap = min(len(retained_pairs), len(modern_pairs))
        if retained_pairs[-overlap:] != modern_pairs[-overlap:]:
            raise ValidationError(
                "retained run history does not match its authenticated modern suffix"
            )

    def _validate_persisted_review_events(
        self,
        dossier: Dossier,
        log: EventLog,
    ) -> None:
        """Close typed review and assignment events over the current dossier."""

        latest_review: ReviewDecision | None = None
        for event in log.all():
            if event.event_type == "review_recorded":
                raw_review = event.to_dict()["payload"]
                try:
                    review = ReviewDecision.from_dict(raw_review, persisted=True)
                except (TypeError, ValueError, ValidationError) as exc:
                    raise ValidationError(
                        "persisted review event payload is not a canonical ReviewDecision"
                    ) from exc
                if (
                    canonical_bytes(review.to_dict()) != canonical_bytes(raw_review)
                    or event.event_id != review.review_id
                    or review.case_id != dossier.case_id
                ):
                    raise ValidationError(
                        "persisted review event does not match its canonical identity"
                    )
                self._validate_review_input(dossier, review)
                latest_review = review
            elif event.event_type == "review_assigned":
                if latest_review is not None and latest_review.state in {
                    ReviewState.ACCEPTED,
                    ReviewState.REJECTED,
                }:
                    raise ValidationError(
                        "persisted assignment cannot follow a terminal review decision"
                    )
                self._validate_persisted_assignment_event(dossier, event.to_dict())

        if (latest_review is None) != (dossier.review is None):
            raise ValidationError(
                "persisted dossier review presence does not match its event history"
            )
        if latest_review is not None and (
            dossier.review is None
            or canonical_bytes(latest_review.to_dict())
            != canonical_bytes(dossier.review.to_dict())
        ):
            raise ValidationError(
                "persisted dossier review does not match the latest review event"
            )

    def _validate_persisted_assignment_event(
        self,
        dossier: Dossier,
        event: Mapping[str, Any],
    ) -> None:
        """Validate the complete addressed payload of one assignment event."""

        if type(event) is not dict or type(event.get("payload")) is not dict:
            raise ValidationError("persisted assignment event must be an exact object")
        payload = event["payload"]
        if set(payload) != _REVIEW_ASSIGNMENT_FIELDS or any(
            type(payload.get(field)) is not str for field in _REVIEW_ASSIGNMENT_FIELDS
        ):
            raise ValidationError("persisted assignment event has a non-canonical payload")
        required = ("assignment_id", "run_id", "case_id", "reviewer", "queue_id", "created_at")
        if any(not payload[field].strip() for field in required):
            raise ValidationError("persisted assignment event has an empty required field")
        if any(fragment in payload["assignment_id"] for fragment in ("/", "\\", "..")):
            raise ValidationError("persisted assignment event has an unsafe identifier")
        try:
            created_at = datetime.fromisoformat(payload["created_at"])
        except ValueError as exc:
            raise ValidationError(
                "persisted assignment created_at must be an ISO 8601 timestamp"
            ) from exc
        if (
            created_at.tzinfo is None
            or created_at.utcoffset() != timedelta(0)
            or created_at.isoformat() != payload["created_at"]
        ):
            raise ValidationError(
                "persisted assignment created_at must use canonical UTC spelling"
            )
        body = {key: value for key, value in payload.items() if key != "content_address"}
        if (
            event.get("event_id") != payload["assignment_id"]
            or payload["run_id"] != dossier.run_id
            or payload["case_id"] != dossier.case_id
            or payload["content_address"]
            != content_hash(body, prefix="review-assignment")
        ):
            raise ValidationError(
                "persisted assignment event does not match its canonical identity"
            )
        self._enforce_policy_texts(tuple(body.values()), "persisted review assignment")

    @staticmethod
    def _append_snapshot_predecessor_binding(
        log: EventLog,
        expected_run: Mapping[str, Any],
    ) -> None:
        """Bind the predecessor event/dossier pair into the immutable successor log."""

        if type(log) is not EventLog or type(expected_run) is not dict:
            raise ValidationError("snapshot predecessor binding requires exact runtime inputs")
        run_id = expected_run.get("run_id")
        if type(run_id) is not str or log.run_id != run_id:
            raise ValidationError("snapshot predecessor binding run_id is inconsistent")
        event_address = _runtime_sha256_address(
            expected_run.get("event_address"),
            "snapshot predecessor event_address",
        )
        dossier_address = _runtime_sha256_address(
            expected_run.get("dossier_address"),
            "snapshot predecessor dossier_address",
        )
        if log.record_address != event_address:
            raise ValidationError(
                "snapshot predecessor event address does not match the staged log"
            )
        body = {
            "version": _SNAPSHOT_PREDECESSOR_VERSION,
            "run_id": run_id,
            "previous_event_address": event_address,
            "previous_dossier_address": dossier_address,
        }
        binding_address = content_hash(body, prefix="snapshot-predecessor")
        log.append(
            "snapshot_predecessor_bound",
            body | {"binding_address": binding_address},
            event_id=(
                f"evt-{run_id}-predecessor-"
                f"{binding_address.rsplit(':', 1)[1][:20]}"
            ),
        )

    def _load_run_snapshot_record(
        self,
        run_id: str,
        run_record: Mapping[str, Any],
    ) -> VerifiedRunSnapshot:
        """Hydrate and semantically verify one current-ended run record."""

        if type(run_record) is not dict:
            raise ValidationError("verified run record must be an exact object")
        try:
            event_address = run_record["event_address"]
            dossier_address = run_record["dossier_address"]
            input_address = run_record["input_address"]
            log = self.load_event_log(event_address)
            dossier = self.load_dossier(dossier_address)
            manifest = self.load_manifest(input_address)
            event_record = log.to_record()
            dossier_record = dossier.to_dict()
            replay = ReplayVerifier().verify(run_record, event_record, dossier_record)
            if not replay.event_chain_valid or not replay.stored_dossier_matches_address:
                raise ValidationError("persisted run failed replay integrity")
            if dossier.run_id != run_id or log.run_id != run_id or replay.run_id != run_id:
                raise ValidationError("persisted run identifier is inconsistent")
            if dossier.event_head != log.head:
                raise ValidationError("persisted dossier does not close over the event log")
            self._validate_persisted_run_inputs(
                dossier=dossier,
                log=log,
                input_record=manifest.to_dict(),
                input_address=input_address,
            )
            snapshot = VerifiedRunSnapshot(
                run_record=run_record,
                manifest=manifest,
                event_record=event_record,
                dossier=dossier,
                replay=replay,
            )
            self._validate_retained_snapshot_history(run_id, snapshot.run_record, log)
            return snapshot
        except Exception as exc:  # noqa: BLE001 - persisted hostile data must fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("cannot load a run with invalid persisted artifacts") from exc

    def _load_current_snapshot(
        self,
        run_id: str,
    ) -> tuple[Dossier, EventLog, dict[str, Any]]:
        """Load a detached, replay-verified current snapshot without touching `_logs`."""

        snapshot = self.load_run_snapshot(run_id)
        return snapshot.dossier, snapshot.event_log, snapshot.run_record_dict()

    def _validate_persisted_run_inputs(
        self,
        *,
        dossier: Dossier,
        log: EventLog,
        input_record: object,
        input_address: str,
    ) -> None:
        """Close the persisted event lineage over canonical manifest and RNA inputs."""

        if type(input_record) is not dict:
            raise ValidationError("persisted manifest input must be an exact object")
        try:
            manifest = CaseManifest.from_dict(input_record)
        except Exception as exc:  # noqa: BLE001 - stored inputs fail closed
            raise ValidationError("persisted manifest input is not canonical") from exc
        if canonical_bytes(manifest.to_dict()) != canonical_bytes(input_record):
            raise ValidationError("persisted manifest input does not round-trip exactly")
        self._validate_manifest_contract(manifest, "persisted manifest input")

        events = log.all()
        case_events = tuple(event for event in events if event.event_type == "case_received")
        if (
            not events
            or len(case_events) != 1
            or case_events[0] is not events[0]
            or case_events[0].event_id != f"evt-{dossier.run_id}-received"
        ):
            raise ValidationError("persisted event log must begin with one canonical case receipt")
        payload = case_events[0].payload
        base_fields = {"input_address", "case_id"}
        rna_fields = {"rna_input_address", "rna_consequence_count"}
        fields = set(payload)
        if fields not in (base_fields, base_fields | rna_fields):
            raise ValidationError("persisted case receipt has a non-canonical payload shape")
        if (
            type(payload.get("input_address")) is not str
            or payload["input_address"] != input_address
            or type(payload.get("case_id")) is not str
            or payload["case_id"] != dossier.case_id
            or manifest.case_id != dossier.case_id
        ):
            raise ValidationError("persisted case receipt does not match its manifest and dossier")

        self._validate_persisted_review_events(dossier, log)

        rna_rows: tuple[RNAConsequenceEvidence, ...] = ()
        rna_address: str | None = None
        if fields == base_fields | rna_fields:
            rna_address = payload["rna_input_address"]
            rna_count = payload["rna_consequence_count"]
            if type(rna_address) is not str:
                raise ValidationError("persisted RNA input address must be an exact string")
            if (
                type(rna_count) is not int
                or rna_count <= 0
                or rna_count > _MAX_RUNTIME_RNA_CONSEQUENCES
            ):
                raise ValidationError("persisted RNA input count is outside runtime limits")
            try:
                rna_record = self.store.store.get_verified(
                    rna_address,
                    max_bytes=self._rna_input_max_bytes,
                )
            except StoreError as exc:
                raise ValidationError("persisted RNA input object is missing or invalid") from exc
            if type(rna_record) is not dict or set(rna_record) != {
                "schema_version",
                "kind",
                "consequences",
            }:
                raise ValidationError("persisted RNA input object has a non-canonical shape")
            if (
                rna_record["schema_version"] != "1.0.0"
                or rna_record["kind"] != "rna_consequence_batch"
                or type(rna_record["consequences"]) is not list
                or len(rna_record["consequences"]) != rna_count
            ):
                raise ValidationError("persisted RNA input object disagrees with its receipt")
            raw_rows = self._preflight_rna_input_rows(
                rna_record["consequences"],
                expected_count=rna_count,
            )
            try:
                rows = tuple(
                    validate_rna_consequence(RNAConsequenceEvidence.from_mapping(row))
                    for row in raw_rows
                )
            except Exception as exc:  # noqa: BLE001 - stored RNA rows fail closed
                raise ValidationError("persisted RNA input rows are not canonical") from exc
            if len(rows) != rna_count:
                raise ValidationError("persisted RNA input rows must be exact objects")
            expected_rows = tuple(sorted(rows, key=lambda row: row.content_address))
            if (
                len({row.content_address for row in rows}) != len(rows)
                or rows != expected_rows
                or canonical_bytes(rna_record["consequences"])
                != canonical_bytes([row.to_dict() for row in rows])
            ):
                raise ValidationError("persisted RNA input object is not canonical or addressed")
            rna_rows = rows

        rna_claims = tuple(
            claim for claim in dossier.evidence if claim.channel == RNA_CONSEQUENCE_CHANNEL
        )
        owner_references = tuple(
            claim for claim in dossier.evidence if "retained_owner_address" in claim.payload
        )
        if rna_address is None:
            if rna_claims or owner_references:
                raise ValidationError(
                    "persisted dossier contains RNA ownership without a recorded RNA input"
                )
        else:
            if rna_address not in dossier.source_bundle_addresses:
                raise ValidationError(
                    "persisted dossier does not declare its recorded RNA input owner"
                )
            if any(claim.channel != RNA_CONSEQUENCE_CHANNEL for claim in owner_references):
                raise ValidationError("retained RNA ownership appears on a non-RNA claim")
            recorded_rna_rows = {row.content_address: row for row in rna_rows}
            for claim in rna_claims:
                try:
                    rna_claim_public_projection(claim)
                    claimed_consequence = validate_rna_consequence(
                        RNAConsequenceEvidence.from_mapping(claim.payload["rna_consequence"])
                    )
                except Exception as exc:  # noqa: BLE001 - persisted claims fail closed
                    raise ValidationError("persisted RNA claim is not canonical") from exc
                if (
                    claim.depends_on != (rna_address,)
                    or claim.payload.get("retained_owner_address") != rna_address
                ):
                    raise ValidationError(
                        "persisted RNA claim is not bound to its recorded input owner"
                    )
                recorded_consequence = recorded_rna_rows.get(claimed_consequence.content_address)
                if (
                    recorded_consequence is None
                    or claimed_consequence.to_dict() != recorded_consequence.to_dict()
                ):
                    raise ValidationError(
                        "persisted RNA claim consequence is not present in its recorded input"
                    )

        self._validate_persisted_source_closure(
            manifest=manifest,
            dossier=dossier,
            events=events,
            rna_address=rna_address,
        )

        if self._run_id(manifest, rna_rows) != dossier.run_id:
            raise ValidationError("persisted inputs do not reproduce the run identifier")

    @staticmethod
    def _source_event_addresses(
        payload: Mapping[str, Any],
        field_name: str,
        label: str,
    ) -> tuple[str, ...]:
        raw = payload.get(field_name)
        if not isinstance(raw, list):
            raise ValidationError(f"{label} source addresses must be an exact array")
        values = tuple(
            _runtime_sha256_address(item, f"{label} source address") for item in raw
        )
        if len(values) != len(set(values)):
            raise ValidationError(f"{label} source addresses must be unique")
        return values

    def _validate_persisted_source_closure(
        self,
        *,
        manifest: CaseManifest,
        dossier: Dossier,
        events: tuple[Any, ...],
        rna_address: str | None,
    ) -> None:
        """Require every declared source object and adapter derivation to replay exactly."""

        records: dict[str, dict[str, Any]] = {}
        for address in dossier.source_bundle_addresses:
            try:
                raw = self.store.store.get_verified(
                    address,
                    max_bytes=self._persisted_object_max_bytes(),
                )
            except StoreError as exc:
                raise ValidationError(
                    f"persisted source object is missing or invalid: {address}"
                ) from exc
            if type(raw) is not dict:
                raise ValidationError("persisted source objects must be exact JSON objects")
            records[address] = raw

        declared: list[str] = []
        if rna_address is not None:
            declared.append(rna_address)
        event_specs = (
            ("public_reference_enriched", "bundle_addresses", "reference"),
            ("public_atlas_collected", "bundle_addresses", "atlas"),
            ("adapter_evidence_collected", "source_bundle_addresses", "adapter"),
        )
        selected_events: dict[str, Any] = {}
        for event_type, address_field, label in event_specs:
            matching = tuple(event for event in events if event.event_type == event_type)
            if len(matching) > 1:
                raise ValidationError(f"persisted run contains duplicate {label} source events")
            if not matching:
                continue
            event = matching[0]
            event_suffix = "adapters" if label == "adapter" else label
            expected_event_id = f"evt-{dossier.run_id}-{event_suffix}"
            if event.event_id != expected_event_id:
                raise ValidationError(f"persisted {label} source event identity is invalid")
            selected_events[event_type] = event
            declared.extend(
                self._source_event_addresses(event.payload, address_field, label)
            )
        if tuple(declared) != dossier.source_bundle_addresses:
            raise ValidationError(
                "persisted dossier source bundle declarations do not match its event lineage"
            )

        adapter_event = selected_events.get("adapter_evidence_collected")
        has_adapter_versions = any(
            key in manifest.input_versions for key in _ADAPTER_INPUT_VERSION_KEYS
        )
        if adapter_event is None:
            if has_adapter_versions:
                raise ValidationError(
                    "persisted manifest declares adapter inputs without an adapter event"
                )
            return
        if not has_adapter_versions:
            raise ValidationError("persisted adapter event is absent from manifest identity")
        self._validate_persisted_adapter_closure(
            manifest=manifest,
            dossier=dossier,
            event=adapter_event,
            records=records,
        )

    def _validate_persisted_adapter_closure(
        self,
        *,
        manifest: CaseManifest,
        dossier: Dossier,
        event: Any,
        records: Mapping[str, dict[str, Any]],
    ) -> None:
        payload = event.payload
        if set(payload) != _ADAPTER_EVENT_FIELDS:
            raise ValidationError("persisted adapter event has a non-canonical payload shape")
        source_addresses = self._source_event_addresses(
            payload,
            "source_bundle_addresses",
            "adapter",
        )
        if len(source_addresses) != len(_ADAPTER_INPUT_VERSION_KEYS):
            raise ValidationError("persisted adapter source closure is incomplete")
        base_address, registry_address, resolution_address, claims_address = source_addresses
        expected_version_addresses = dict(
            zip(_ADAPTER_INPUT_VERSION_KEYS, source_addresses, strict=True)
        )
        if any(
            manifest.input_versions.get(key) != address
            for key, address in expected_version_addresses.items()
        ):
            raise ValidationError("persisted adapter sources are not bound into manifest identity")
        scalar_addresses = (
            ("base_input_address", base_address),
            ("effective_input_address", manifest.content_address),
            ("registry_bundle_address", registry_address),
            ("resolution_bundle_address", resolution_address),
            ("claim_collection_bundle_address", claims_address),
        )
        if any(payload.get(field) != expected for field, expected in scalar_addresses):
            raise ValidationError("persisted adapter event source addresses are inconsistent")
        try:
            base_record = records[base_address]
            registry_record = records[registry_address]
            resolution_record = records[resolution_address]
            claims_record = records[claims_address]
            base_manifest = CaseManifest.from_dict(base_record)
            registry_snapshot = AdapterRegistrySnapshot.from_dict(registry_record)
            resolution = AdapterResolutionReport.from_dict(resolution_record)
            claim_report = AdapterClaimCollectionReport.from_dict(claims_record)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("persisted adapter source records are invalid") from exc
        typed_records = (
            (base_manifest.to_dict(), base_record),
            (registry_snapshot.to_dict(), registry_record),
            (resolution.to_dict(), resolution_record),
            (claim_report.to_dict(), claims_record),
        )
        if any(
            canonical_bytes(typed) != canonical_bytes(raw) for typed, raw in typed_records
        ):
            raise ValidationError("persisted adapter source records do not round-trip exactly")
        adapter_ids = payload.get("adapter_ids")
        if not isinstance(adapter_ids, list) or any(
            type(item) is not str for item in adapter_ids
        ):
            raise ValidationError("persisted adapter event adapter_ids must be an exact array")
        if (
            tuple(adapter_ids) != resolution.adapter_ids
            or claim_report.adapter_ids != resolution.adapter_ids
            or resolution.manifest_address != base_address
            or claim_report.manifest_address != base_address
            or resolution.registry_address != registry_snapshot.content_address
            or claim_report.registry_snapshot != registry_snapshot
            or claim_report.registry_address != resolution.registry_address
            or claim_report.resolution_address != resolution.content_address
            or payload.get("registry_address") != resolution.registry_address
            or payload.get("resolution_address") != resolution.content_address
            or payload.get("claim_collection_address") != claim_report.content_address
        ):
            raise ValidationError("persisted adapter reports do not form one provenance closure")
        counters = (
            ("resolved_element_count", resolution.element_count),
            ("attribution_count", claim_report.attribution_count),
            ("claim_count", claim_report.claim_count),
        )
        if any(type(payload.get(field)) is not int for field, _expected in counters) or any(
            payload.get(field) != expected for field, expected in counters
        ):
            raise ValidationError("persisted adapter event counters are inconsistent")
        expected_manifest = self._materialize_adapter_manifest(
            base_manifest,
            resolution,
            source_addresses,
        )
        if canonical_bytes(expected_manifest.to_dict()) != canonical_bytes(manifest.to_dict()):
            raise ValidationError("persisted adapter resolution does not reproduce the manifest")
        evidence_by_id = {claim.evidence_id: claim for claim in dossier.evidence}
        edge_claims = {
            claim_id
            for hypothesis in dossier.hypotheses
            for edge in hypothesis.edges
            for claim_id in edge.claim_ids
        }
        for claim in claim_report.claims:
            persisted = evidence_by_id.get(claim.evidence_id)
            if (
                persisted is None
                or canonical_bytes(persisted.to_dict()) != canonical_bytes(claim.to_dict())
                or claim.evidence_id not in edge_claims
            ):
                raise ValidationError(
                    "persisted adapter claim is absent from the dossier hypothesis graph"
                )

    @staticmethod
    def _preflight_rna_input_rows(
        raw_rows: object,
        *,
        expected_count: int,
    ) -> list[dict[str, Any]]:
        """Bound nested RNA collections before typed hydration can allocate from them."""

        if (
            type(expected_count) is not int
            or expected_count <= 0
            or expected_count > _MAX_RUNTIME_RNA_CONSEQUENCES
            or type(raw_rows) is not list
            or len(raw_rows) != expected_count
        ):
            raise ValidationError("RNA input rows disagree with the bounded expected count")
        checked: list[dict[str, Any]] = []
        for index, row in enumerate(raw_rows):
            if type(row) is not dict:
                raise ValidationError(f"RNA input row {index} must be an exact object")
            if set(row) != _RNA_CONSEQUENCE_RECORD_FIELDS:
                raise ValidationError(f"RNA input row {index} has a non-canonical shape")
            reason_codes = row.get("reason_codes")
            if type(reason_codes) is not list or len(reason_codes) > _MAX_RUNTIME_RNA_REASON_CODES:
                raise ValidationError(
                    f"RNA input row {index} reason_codes exceeds its collection limit"
                )
            if any(
                type(code) is not str
                or not code
                or len(code) > _MAX_RUNTIME_RNA_REASON_CODE_CHARACTERS
                for code in reason_codes
            ):
                raise ValidationError(
                    f"RNA input row {index} reason_codes must be bounded exact strings"
                )
            if len(canonical_bytes(row)) > _MAX_RUNTIME_RNA_ROW_BYTES:
                raise ValidationError(
                    f"RNA input row {index} exceeds {_MAX_RUNTIME_RNA_ROW_BYTES} bytes"
                )
            checked.append(row)
        return checked

    @staticmethod
    def _dossier_reuse_projection(dossier: Dossier) -> dict[str, Any]:
        """Project scientific output while omitting only runtime-generated identity fields."""

        projection = dossier.to_dict()
        if type(projection) is not dict:
            raise ValidationError("dossier reuse projection must be an exact object")
        try:
            for field_name in ("created_at", "event_head", "content_address"):
                projection.pop(field_name)
            evidence = projection["evidence"]
            if type(evidence) is not list:
                raise TypeError("dossier evidence projection must be an array")
            for claim in evidence:
                if type(claim) is not dict:
                    raise TypeError("dossier evidence projection entries must be objects")
                claim.pop("created_at")
        except (KeyError, TypeError) as exc:
            raise ValidationError("dossier reuse projection is malformed") from exc
        return projection

    @staticmethod
    def _event_reuse_projection(log: EventLog) -> dict[str, Any]:
        """Project event semantics while omitting timestamps and their hash links."""

        record = log.to_record()
        if type(record) is not dict or set(record) != {"run_id", "events"}:
            raise ValidationError("event reuse projection must be an exact record")
        rows = record["events"]
        if type(rows) is not list:
            raise ValidationError("event reuse projection events must be an exact array")
        events: list[dict[str, Any]] = []
        try:
            for row in rows:
                if type(row) is not dict:
                    raise TypeError("event reuse projection entries must be objects")
                projected = dict(row)
                for field_name in ("created_at", "previous_hash", "event_hash"):
                    projected.pop(field_name)
                events.append(projected)
        except (KeyError, TypeError) as exc:
            raise ValidationError("event reuse projection is malformed") from exc
        return {"run_id": record["run_id"], "events": events}

    def _reuse_untouched_offline_draft(
        self,
        candidate: Dossier,
        candidate_log: EventLog,
    ) -> Dossier | None:
        """Reuse only a replay-valid, never-advanced equivalent offline draft."""

        run_path = self.store.runs / f"{candidate.run_id}.json"
        if not run_path.exists():
            return None

        persisted, persisted_log, run_record = self._load_current_snapshot(candidate.run_id)
        event_history = run_record.get("event_history")
        dossier_history = run_record.get("dossier_history")
        untouched = (
            type(event_history) is list
            and event_history == [run_record["event_address"]]
            and type(dossier_history) is list
            and dossier_history == [run_record["dossier_address"]]
            and persisted.status is ResearchStatus.REVIEW_REQUIRED
            and persisted.review is None
            and not any(
                event.event_type in {"review_assigned", "review_recorded"}
                for event in persisted_log.all()
            )
        )
        equivalent = untouched and canonical_bytes(
            self._dossier_reuse_projection(candidate)
        ) == canonical_bytes(self._dossier_reuse_projection(persisted))
        equivalent = equivalent and canonical_bytes(
            self._event_reuse_projection(candidate_log)
        ) == canonical_bytes(self._event_reuse_projection(persisted_log))
        if not equivalent:
            conflict = StoreError(f"run already exists: {candidate.run_id}")
            raise ValidationError(f"run publication failed: {conflict}") from conflict

        self._logs[candidate.run_id] = persisted_log
        return persisted

    @staticmethod
    def _require_valid(report: ValidationReport, label: str) -> None:
        """Raise one bounded deterministic error for an invalid validation report."""

        if type(report) is not ValidationReport:
            raise ValidationError(f"{label} returned a non-canonical validation report")
        try:
            checked = ValidationReport(report.valid, report.issues)
            canonical_issues = tuple(
                ValidationIssue(
                    issue.code,
                    issue.severity,
                    issue.message,
                    issue.path,
                    issue.remediation,
                )
                for issue in checked.issues
            )
            canonical = ValidationReport(checked.valid, canonical_issues)
        except Exception as exc:  # noqa: BLE001 - mutated reports fail closed
            raise ValidationError(f"{label} returned an invalid validation report") from exc
        if canonical.valid:
            return
        displayed = canonical.issues[:16]
        details = "; ".join(f"{issue.path}: {issue.code}" for issue in displayed)
        if len(canonical.issues) > len(displayed):
            details += f"; and {len(canonical.issues) - len(displayed)} more issue(s)"
        raise ValidationError(f"{label} failed contract validation: {details}")

    def _validate_manifest_contract(self, manifest: CaseManifest, label: str) -> None:
        validator = self._require_exact_validator(self.validator, "runtime validator")
        try:
            report = validator.validate_manifest(manifest)
        except Exception as exc:  # noqa: BLE001 - replaced dependencies fail closed
            raise ValidationError(f"{label} validation failed safely") from exc
        self._require_valid(report, label)

    def _validate_dossier_contract(self, dossier: Dossier, label: str) -> None:
        validator = self._require_exact_validator(self.validator, "runtime validator")
        try:
            report = validator.validate_dossier(dossier)
        except Exception as exc:  # noqa: BLE001 - replaced dependencies fail closed
            raise ValidationError(f"{label} validation failed safely") from exc
        self._require_valid(report, label)

    @staticmethod
    def _require_exact_validator(
        validator: object,
        label: str,
    ) -> ContractValidator:
        if type(validator) is not ContractValidator:
            raise ValidationError(f"{label} must be an exact ContractValidator")
        try:
            state = vars(validator)
            if type(state) is not dict or set(state) != {"limits"}:
                raise ValidationError(f"{label} has non-canonical instance state")
            canonical = ContractValidator(limits=validator.limits)
            if canonical.limits != validator.limits:
                raise ValidationError(f"{label} limits are not canonical")
        except Exception as exc:  # noqa: BLE001 - forged exact instances fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(f"{label} is mutated or invalid") from exc
        return validator

    def _check_release(self, dossier: Dossier, label: str) -> None:
        self._require_exact_policy()
        if type(self.release_gate) is not ReleaseGate:
            raise ValidationError("runtime release_gate must be an exact ReleaseGate")
        try:
            state = vars(self.release_gate)
            if type(state) is not dict or set(state) != {"policy", "validator"}:
                raise ValidationError("runtime release_gate has non-canonical instance state")
            if self.release_gate.policy is not self.policy:
                raise ValidationError("runtime release_gate is not bound to the runtime policy")
            self._require_exact_validator(
                self.release_gate.validator,
                "runtime release_gate validator",
            )
        except Exception as exc:  # noqa: BLE001 - forged exact instances fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime release_gate is mutated or invalid") from exc
        try:
            report = self.release_gate.check(dossier)
        except Exception as exc:  # noqa: BLE001 - replaced dependencies fail closed
            raise ValidationError(f"{label} evaluation failed safely") from exc
        self._require_valid(report, label)

    def _require_exact_policy(self) -> None:
        if type(self.policy) is not ResearchPolicy:
            raise ValidationError("runtime policy must be an exact ResearchPolicy")
        try:
            state = vars(self.policy)
            if type(state) is not dict or set(state) != {"limits"}:
                raise ValidationError("runtime policy has non-canonical instance state")
            canonical = ResearchPolicy(limits=self.policy.limits)
            if canonical.limits != self.policy.limits:
                raise ValidationError("runtime policy limits are not canonical")
            if (
                type(self.release_gate) is ReleaseGate
                and self.release_gate.policy is not self.policy
            ):
                raise ValidationError("runtime policy was replaced after release gate construction")
        except Exception as exc:  # noqa: BLE001 - forged exact policy instances fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime policy is mutated or invalid") from exc

    @staticmethod
    def _require_policy_decision(decision: PolicyDecision, label: str) -> PolicyDecision:
        if type(decision) is not PolicyDecision:
            raise ValidationError(f"{label} returned a non-canonical policy decision")
        try:
            raw = decision.to_dict()
            canonical = PolicyDecision(
                decision.allowed,
                decision.policy_version,
                decision.violations,
                decision.warnings,
            )
            if canonical.to_dict() != raw:
                raise ValidationError("policy decision does not round-trip exactly")
        except Exception as exc:  # noqa: BLE001 - mutated decisions fail closed
            raise ValidationError(f"{label} returned an invalid policy decision") from exc
        return canonical

    def _enforce_policy_texts(self, texts: Iterable[str], label: str) -> PolicyDecision:
        self._require_exact_policy()
        try:
            decision = self.policy.inspect_texts(texts)
        except Exception as exc:  # noqa: BLE001 - mutated policies fail closed
            raise ValidationError(f"{label} policy evaluation failed safely") from exc
        canonical = self._require_policy_decision(decision, label)
        if not canonical.allowed:
            raise PolicyViolation("; ".join(canonical.violations))
        return canonical

    def _policy_dossier_decision(self, dossier: Dossier, label: str) -> PolicyDecision:
        self._require_exact_policy()
        try:
            decision = self.policy.validate_dossier(dossier)
        except Exception as exc:  # noqa: BLE001 - mutated policies fail closed
            raise ValidationError(f"{label} policy evaluation failed safely") from exc
        return self._require_policy_decision(decision, label)

    def assign_review(
        self,
        run_id: str,
        *,
        assignment_id: str,
        reviewer: str,
        queue_id: str = "default-review",
        due_at: str | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Append a durable reviewer assignment and create a new snapshot.

        Assignment is operational metadata, but it is still part of the
        replayable event chain.  The dossier is re-addressed with the new event
        head so the current run pointer and snapshot history remain coherent.
        """

        resolved_due_at = "" if due_at is None else due_at
        fields = {
            "run_id": run_id,
            "assignment_id": assignment_id,
            "reviewer": reviewer,
            "queue_id": queue_id,
            "due_at": resolved_due_at,
            "note": note,
        }
        if any(type(value) is not str for value in fields.values()):
            raise ValidationError("review assignment fields must be exact strings")
        for name in ("run_id", "assignment_id", "reviewer", "queue_id"):
            value = fields[name]
            if not value.strip():
                raise ValidationError(f"{name} must not be empty")
        if any(char in assignment_id for char in ("/", "\\", "..")):
            raise ValidationError("assignment_id contains an unsafe path fragment")
        self._enforce_policy_texts(tuple(fields.values()), "review assignment")
        dossier, log, run_record = self._load_current_snapshot(run_id)
        if dossier.review is not None and dossier.review.state in {
            ReviewState.ACCEPTED,
            ReviewState.REJECTED,
        }:
            raise ValidationError("cannot assign a completed review")
        if any(event.event_id == assignment_id for event in log.all()):
            raise ValidationError("assignment_id already exists in the run event chain")
        self._append_snapshot_predecessor_binding(log, run_record)
        assignment_body = {
            "assignment_id": assignment_id,
            "run_id": run_id,
            "case_id": dossier.case_id,
            "reviewer": reviewer,
            "queue_id": queue_id,
            "due_at": resolved_due_at,
            "note": note,
            "created_at": utc_now().isoformat(),
        }
        assignment = dict(assignment_body)
        assignment["content_address"] = content_hash(
            assignment_body,
            prefix="review-assignment",
        )
        log.append(
            "review_assigned",
            assignment,
            event_id=assignment_id,
        )
        updated = self._readdress(replace(dossier, event_head=log.head))
        self._validate_dossier_contract(updated, "assigned dossier")
        event_address, _ = self._persist(
            None,
            log,
            updated,
            dossier.input_address,
            expected_run=run_record,
        )
        self._logs[run_id] = log
        response_body = {
            "assignment": assignment,
            "dossier": updated.to_dict(),
            "event_address": event_address,
            "accepted": True,
        }
        return response_body | {
            "content_address": content_hash(response_body, prefix="review-assignment-response")
        }

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Read the run index without rehydrating mutable objects."""

        return self.store.get_run(run_id)

    def get_dossier(self, dossier_address: str) -> dict[str, Any]:
        """Read an immutable dossier by its content address."""

        return self.load_dossier(dossier_address).to_dict()

    @staticmethod
    def _run_id(
        manifest: CaseManifest,
        rna_consequences: tuple[RNAConsequenceEvidence, ...] = (),
    ) -> str:
        payload: dict[str, Any] = {
            "input": manifest.content_address,
            "requested_by": manifest.requested_by,
        }
        if rna_consequences:
            payload["rna_consequences"] = sorted(item.content_address for item in rna_consequences)
        digest = content_hash(payload).split(":", 1)[1]
        return f"run-{digest[:24]}"

    @staticmethod
    def _dossier_address(dossier: Dossier) -> str:
        payload = {
            key: value for key, value in dossier.to_dict().items() if key != "content_address"
        }
        return content_hash(payload)

    def _make_dossier(
        self,
        *,
        manifest: CaseManifest | None,
        run_id: str,
        input_address: str,
        hypotheses: Iterable[Hypothesis],
        claims: Iterable[EvidenceClaim],
        experiments: Iterable[ExperimentOption],
        review: ReviewDecision | None,
        status: ResearchStatus,
        event_head: str,
        warnings: Iterable[str],
        case_id: str | None = None,
        created_at: str | None = None,
        source_receipts: tuple[Mapping[str, Any], ...] = (),
        source_bundle_addresses: tuple[str, ...] = (),
    ) -> Dossier:
        resolved_case_id = case_id
        if resolved_case_id is None:
            if manifest is None:
                raise ValidationError("manifest or case_id is required to build a dossier")
            resolved_case_id = manifest.case_id
        draft = Dossier(
            dossier_id=f"dos-{run_id}",
            case_id=resolved_case_id,
            run_id=run_id,
            created_at=created_at or utc_now().isoformat(),
            input_address=input_address,
            hypotheses=tuple(hypotheses),
            evidence=tuple(claims),
            experiments=tuple(experiments),
            review=review,
            research_use_only=True,
            policy_version=self.policy.version,
            event_head=event_head,
            content_address="pending",
            status=status,
            warnings=tuple(warnings),
            source_receipts=tuple(source_receipts),
            source_bundle_addresses=tuple(source_bundle_addresses),
        )
        return self._readdress(draft)

    def _readdress(self, dossier: Dossier) -> Dossier:
        pending = replace(dossier, content_address="pending")
        return replace(pending, content_address=self._dossier_address(pending))

    def _persist(
        self,
        manifest: CaseManifest | None,
        log: EventLog,
        dossier: Dossier,
        input_address: str,
        *,
        expected_run: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        if type(log) is not EventLog or not log.verify():
            raise ValidationError("cannot persist an invalid event log")
        if log.run_id != dossier.run_id:
            raise ValidationError("dossier run_id does not match the event log")
        if dossier.event_head != log.head:
            raise ValidationError("dossier event_head does not match the event log")
        if dossier.input_address != input_address:
            raise ValidationError("dossier input_address does not match the run input")
        if expected_run is not None and expected_run.get("input_address") != input_address:
            raise ValidationError("expected run input_address does not match the dossier")
        self._validate_dossier_contract(dossier, "persisted dossier")
        if dossier.status is ResearchStatus.RELEASED_RESEARCH:
            self._check_release(dossier, "release gate")
        try:
            event_address = self.store.store.put(log.to_record())
            dossier_address = self.store.store.put_at(dossier.content_address, dossier.to_dict())
            if expected_run is None:
                self.store.create_run(
                    log.run_id,
                    input_address=input_address,
                    event_address=event_address,
                    dossier_address=dossier_address,
                )
            else:
                self.store.advance_run(
                    log.run_id,
                    expected_run=expected_run,
                    event_address=event_address,
                    dossier_address=dossier_address,
                )
        except StoreError as exc:
            raise ValidationError(f"run publication failed: {exc}") from exc
        return event_address, dossier_address
