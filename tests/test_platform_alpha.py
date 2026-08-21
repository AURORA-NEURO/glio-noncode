from __future__ import annotations

import unittest

from glio_noncode.platform_alpha import (
    DataReferenceRegistry,
    DataReferenceStatus,
    DriftAndOODMonitor,
    DriftMetric,
    EventSourcedExecutionLedger,
    ModelRegistry,
    ModelResolutionState,
    ModelStatus,
    RuntimeAlphaState,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|core|untreated"


class PlatformAlphaTests(unittest.TestCase):
    def test_execution_ledger_replays_valid_order_and_blocks_invalid_transition(self) -> None:
        builder = EventSourcedExecutionLedger()
        ledger = builder.replay(
            [
                {"event_id": "e-1", "kind": "requested", "message": "requested"},
                {"event_id": "e-2", "kind": "planned", "message": "planned"},
                {"event_id": "e-3", "kind": "admitted", "message": "admitted"},
                {"event_id": "e-4", "kind": "started", "message": "started"},
                {"event_id": "e-5", "kind": "completed", "message": "completed"},
            ],
            execution_id="execution-1",
            context_key=CONTEXT,
        )
        self.assertEqual(ledger.state, RuntimeAlphaState.COMPLETED)
        self.assertEqual(ledger.last_sequence, 5)
        self.assertEqual(
            ledger.content_address,
            builder.replay(
                ledger.events, execution_id="execution-1", context_key=CONTEXT
            ).content_address,
        )
        blocked = builder.append(
            ledger,
            {"event_id": "e-6", "kind": "started", "message": "cannot restart"},
        )
        self.assertEqual(blocked.state, RuntimeAlphaState.BLOCKED)
        self.assertEqual(blocked.last_sequence, 5)
        self.assertEqual(blocked.issues[-1].code, "invalid_event_transition")

    def test_model_registry_resolves_contracts_and_context_separately(self) -> None:
        registry = ModelRegistry.from_mappings(
            [
                {
                    "model_id": "model-1",
                    "version": "v1",
                    "model_family": "sequence",
                    "artifact_digest": "sha256:model",
                    "input_contract": "sequence-window",
                    "output_contract": "effect-envelope",
                    "supported_contexts": [CONTEXT],
                    "status": ModelStatus.VALIDATED.value,
                    "source_id": "model-catalog",
                    "license_id": "research",
                    "evaluation_receipt": "sha256:evaluation",
                }
            ]
        ).snapshot
        compatible = registry.resolve(
            "model-1",
            context_key=CONTEXT,
            input_contract="sequence-window",
            output_contract="effect-envelope",
        )
        self.assertEqual(compatible.state, ModelResolutionState.COMPATIBLE)
        out_of_domain = registry.resolve("model-1", context_key=OTHER_CONTEXT)
        self.assertEqual(out_of_domain.state, ModelResolutionState.OUT_OF_DOMAIN)
        blocked = registry.resolve("model-1", context_key=CONTEXT, input_contract="wrong")
        self.assertEqual(blocked.state, ModelResolutionState.BLOCKED)

    def test_data_reference_registry_retains_license_and_coordinate_gates(self) -> None:
        registry = DataReferenceRegistry.from_mappings(
            [
                {
                    "dataset_id": "reference-1",
                    "version": "v1",
                    "reference_kind": "genome",
                    "source_uri": "https://example.test/reference",
                    "checksum": "sha256:reference",
                    "format": "fasta",
                    "schema_hash": "sha256:schema",
                    "supported_contexts": [CONTEXT],
                    "coordinate_system": "GRCh38",
                    "license_id": "research",
                    "status": DataReferenceStatus.AVAILABLE.value,
                    "source_id": "reference-catalog",
                    "retrieval_receipt": "sha256:retrieval",
                }
            ]
        ).snapshot
        resolved = registry.resolve(
            "reference-1",
            context_key=CONTEXT,
            coordinate_system="GRCh38",
            license_id="research",
        )
        self.assertEqual(resolved.state, RuntimeAlphaState.COMPATIBLE)
        mismatch = registry.resolve("reference-1", context_key=CONTEXT, coordinate_system="hg19")
        self.assertEqual(mismatch.state, RuntimeAlphaState.BLOCKED)
        absent = registry.resolve("missing", context_key=CONTEXT)
        self.assertEqual(absent.state, RuntimeAlphaState.ABSTAINED)

    def test_drift_monitor_separates_watch_drift_and_out_of_domain(self) -> None:
        report = DriftAndOODMonitor().evaluate(
            [
                {
                    "observation_id": "obs-watch",
                    "monitor_id": "monitor-1",
                    "feature_id": "feature-watch",
                    "context_key": CONTEXT,
                    "metric": DriftMetric.MEAN_DELTA.value,
                    "reference_value": 0.1,
                    "current_value": 0.25,
                    "watch_threshold": 0.1,
                    "drift_threshold": 0.3,
                    "source_id": "monitor-source",
                },
                {
                    "observation_id": "obs-drift",
                    "monitor_id": "monitor-1",
                    "feature_id": "feature-drift",
                    "context_key": CONTEXT,
                    "metric": DriftMetric.MEAN_DELTA.value,
                    "reference_value": 0.1,
                    "current_value": 0.6,
                    "watch_threshold": 0.1,
                    "drift_threshold": 0.3,
                    "source_id": "monitor-source",
                },
                {
                    "observation_id": "obs-ood",
                    "monitor_id": "monitor-1",
                    "feature_id": "feature-ood",
                    "context_key": CONTEXT,
                    "metric": DriftMetric.MEAN_DELTA.value,
                    "reference_value": 0.1,
                    "current_value": 0.1,
                    "watch_threshold": 0.1,
                    "drift_threshold": 0.3,
                    "in_domain": False,
                    "source_id": "monitor-source",
                },
            ],
            monitor_id="monitor-1",
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, RuntimeAlphaState.OUT_OF_DOMAIN)
        self.assertEqual(report.watch_feature_ids, ("feature-watch",))
        self.assertEqual(report.drifted_feature_ids, ("feature-drift",))
        self.assertEqual(report.out_of_domain_feature_ids, ("feature-ood",))


if __name__ == "__main__":
    unittest.main()
