"""Orchestration for case evaluation, review, replay, and local persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from .atlas import AtlasQuery, PublicAtlasRetriever
from .data_sources import EnrichmentResult, PublicReferenceRetriever
from .errors import PolicyViolation, StoreError, ValidationError
from .events import EventLog
from .experiments import ExperimentPlanner
from .hypotheses import HypothesisBuilder
from .models import (
    CaseManifest,
    Dossier,
    ResearchStatus,
    ReviewDecision,
    ReviewState,
)
from .policy import ResearchPolicy
from .replay import ReplayVerifier
from .serialization import content_hash, utc_now
from .storage import RunStore


class CaseRuntime:
    """Coordinate typed inputs, deterministic builders, policy, and storage."""

    def __init__(
        self,
        data_root: str | Path = ".glio",
        *,
        reference_retriever: PublicReferenceRetriever | None = None,
        atlas_retriever: PublicAtlasRetriever | None = None,
    ) -> None:
        self.store = RunStore(data_root)
        self.builder = HypothesisBuilder()
        self.planner = ExperimentPlanner()
        self.policy = ResearchPolicy()
        self.reference_retriever = reference_retriever
        self.atlas_retriever = atlas_retriever
        self._logs: dict[str, EventLog] = {}

    def evaluate(self, manifest: CaseManifest, *, live_reference: bool = False) -> Dossier:
        """Evaluate a manifest and persist its immutable output."""

        self.policy.enforce_texts((manifest.case_id, manifest.requested_by))
        run_id = self._run_id(manifest)
        log = EventLog(run_id)
        self._logs[run_id] = log
        input_address = self.store.store.put(manifest.to_dict())
        log.append(
            "case_received",
            {"input_address": input_address, "case_id": manifest.case_id},
            event_id=f"evt-{run_id}-received",
        )
        build_manifest = manifest
        enrichment: EnrichmentResult | None = None
        source_receipts: tuple[Mapping[str, Any], ...] = ()
        source_bundle_addresses: tuple[str, ...] = ()
        runtime_warnings: tuple[str, ...] = ()
        atlas_claims = ()
        if live_reference:
            retriever = self.reference_retriever or PublicReferenceRetriever(
                cache_root=Path(self.store.root) / "source-cache"
            )
            self.reference_retriever = retriever
            enrichment = retriever.enrich_manifest(manifest)
            build_manifest = enrichment.manifest
            source_bundle_addresses = tuple(
                self.store.store.put(bundle.to_dict()) for bundle in enrichment.bundles
            )
            source_receipts = tuple(
                receipt.to_dict() for bundle in enrichment.bundles for receipt in bundle.receipts
            )
            runtime_warnings = enrichment.warnings
            log.append(
                "public_reference_enriched",
                {
                    "bundle_addresses": list(source_bundle_addresses),
                    "receipt_count": len(source_receipts),
                    "warnings": list(runtime_warnings),
                },
                event_id=f"evt-{run_id}-reference",
            )
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
                atlas_claims = tuple(
                    claim
                    for variant, bundle in zip(build_manifest.variants, atlas_bundles, strict=True)
                    for claim in bundle.to_evidence_claims(
                        variant=variant,
                        context=build_manifest.context,
                        edge_id=f"atlas:{variant.variant_id}",
                    )
                )
                source_bundle_addresses += tuple(
                    self.store.store.put(bundle.to_dict()) for bundle in atlas_bundles
                )
                source_receipts += tuple(
                    receipt.to_dict() for bundle in atlas_bundles for receipt in bundle.receipts
                )
                atlas_warnings = tuple(
                    warning for bundle in atlas_bundles for warning in bundle.warnings
                )
                runtime_warnings = tuple(dict.fromkeys(runtime_warnings + atlas_warnings))
                log.append(
                    "public_atlas_collected",
                    {
                        "bundle_addresses": list(source_bundle_addresses),
                        "claim_count": len(atlas_claims),
                        "warnings": list(atlas_warnings),
                    },
                    event_id=f"evt-{run_id}-atlas",
                )
        built = self.builder.build(build_manifest, run_id)
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
        dossier = self._make_dossier(
            manifest=build_manifest,
            run_id=run_id,
            input_address=input_address,
            hypotheses=built.hypotheses,
            claims=tuple(built.claims) + tuple(atlas_claims),
            experiments=experiments,
            review=None,
            status=ResearchStatus.REVIEW_REQUIRED,
            event_head=log.head,
            warnings=all_warnings,
            source_receipts=source_receipts,
            source_bundle_addresses=source_bundle_addresses,
        )
        decision = self.policy.validate_dossier(dossier)
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.violations))
        log.append(
            "dossier_created", {"dossier_id": dossier.dossier_id}, event_id=f"evt-{run_id}-dossier"
        )
        dossier = self._readdress(replace(dossier, event_head=log.head))
        self._persist(manifest, log, dossier, input_address)
        return dossier

    def review(self, dossier: Dossier, review: ReviewDecision) -> Dossier:
        """Attach a review decision and create a new immutable dossier snapshot."""

        if dossier.case_id != review.case_id:
            raise ValidationError("review case_id does not match dossier")
        known_hypotheses = {hypothesis.hypothesis_id for hypothesis in dossier.hypotheses}
        unknown_hypotheses = set(review.reviewed_hypothesis_ids) - known_hypotheses
        if unknown_hypotheses:
            raise ValidationError(f"review names unknown hypotheses: {sorted(unknown_hypotheses)}")
        known_claims = {claim.evidence_id for claim in dossier.evidence}
        unknown_claims = set(review.checked_claim_ids) - known_claims
        if unknown_claims:
            raise ValidationError(f"review names unknown claims: {sorted(unknown_claims)}")
        log = self._logs.get(dossier.run_id)
        if log is None:
            try:
                run_record = self.get_run(dossier.run_id)
            except StoreError:
                log = EventLog(dossier.run_id)
                log.append(
                    "replayed_from_dossier",
                    {"dossier_id": dossier.dossier_id},
                    event_id=f"evt-{dossier.run_id}-replayed",
                )
            else:
                try:
                    event_record = self.store.store.get(str(run_record["event_address"]))
                    log = EventLog.from_record(event_record)
                except (KeyError, ValueError) as exc:
                    raise ValidationError("cannot continue a run with an invalid event record") from exc
                if not log.verify():
                    raise ValidationError("cannot continue a run with an invalid event chain")
            self._logs[dossier.run_id] = log
        log.append("review_recorded", review.to_dict(), event_id=review.review_id)
        status = (
            ResearchStatus.RELEASED_RESEARCH
            if review.state == ReviewState.ACCEPTED
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
            event_head=log.head,
            warnings=dossier.warnings,
            case_id=dossier.case_id,
            created_at=dossier.created_at,
            source_receipts=dossier.source_receipts,
            source_bundle_addresses=dossier.source_bundle_addresses,
        )
        decision = self.policy.validate_dossier(updated)
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.violations))
        updated = self._readdress(updated)
        self._persist(None, log, updated, dossier.input_address)
        return updated

    def review_run(self, run_id: str, review: ReviewDecision) -> Dossier:
        """Reopen a persisted run, attach a review, and persist a new snapshot."""

        run_record = self.get_run(run_id)
        event_record = self.store.store.get(str(run_record["event_address"]))
        stored = self.get_dossier(str(run_record["dossier_address"]))
        replay = ReplayVerifier().verify(run_record, event_record, stored)
        if (
            not replay.event_chain_valid
            or not replay.stored_dossier_matches_address
            or not self.store.store.exists(str(run_record["input_address"]))
        ):
            raise ValidationError("cannot review a run that fails replay integrity")
        self._logs[run_id] = EventLog.from_record(event_record)
        dossier = Dossier.from_dict(stored)
        if dossier.run_id != run_id:
            raise ValidationError("stored dossier run_id does not match requested run")
        return self.review(dossier, review)

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Read the run index without rehydrating mutable objects."""

        return self.store.get_run(run_id)

    def get_dossier(self, dossier_address: str) -> dict[str, Any]:
        """Read an immutable dossier by its content address."""

        return self.store.store.get(dossier_address)

    @staticmethod
    def _run_id(manifest: CaseManifest) -> str:
        digest = content_hash(
            {"input": manifest.content_address, "requested_by": manifest.requested_by}
        ).split(":", 1)[1]
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
        hypotheses,
        claims,
        experiments,
        review,
        status: ResearchStatus,
        event_head: str,
        warnings,
        case_id: str | None = None,
        created_at: str | None = None,
        source_receipts: tuple[Mapping[str, Any], ...] = (),
        source_bundle_addresses: tuple[str, ...] = (),
    ) -> Dossier:
        draft = Dossier(
            dossier_id=f"dos-{run_id}",
            case_id=case_id or manifest.case_id,
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

    def _persist(self, manifest, log: EventLog, dossier: Dossier, input_address: str) -> None:
        event_address = self.store.store.put(log.to_record())
        dossier_address = self.store.store.put_at(dossier.content_address, dossier.to_dict())
        self.store.save_run(
            log.run_id,
            input_address=input_address,
            event_address=event_address,
            dossier_address=dossier_address,
        )
