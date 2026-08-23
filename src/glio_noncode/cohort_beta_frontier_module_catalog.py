"""Module catalog for the deeply layered C05-C08 implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierModuleEntry:
    module_id: str
    operation: str
    layer: str
    purpose: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    blocking_checks: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierModuleCatalog:
    entries: tuple[CohortBetaFrontierModuleEntry, ...]
    layer_count: int
    operation_count: int
    accepted: bool
    content_address: str

    def for_operation(self, operation: str) -> tuple[CohortBetaFrontierModuleEntry, ...]:
        return tuple(item for item in self.entries if item.operation == operation)

    def for_layer(self, layer: str) -> tuple[CohortBetaFrontierModuleEntry, ...]:
        return tuple(item for item in self.entries if item.layer == layer)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _entry(module_id: str, operation: str, layer: str, purpose: str, inputs: tuple[str, ...], outputs: tuple[str, ...], checks: tuple[str, ...]) -> CohortBetaFrontierModuleEntry:
    body = {"module_id": module_id, "operation": operation, "layer": layer, "purpose": purpose, "inputs": inputs, "outputs": outputs, "blocking_checks": checks}
    return CohortBetaFrontierModuleEntry(module_id, operation, layer, purpose, inputs, outputs, checks, content_hash(body, prefix="module-entry"))


def default_cohort_beta_frontier_module_catalog() -> CohortBetaFrontierModuleCatalog:
    entries = (
        _entry("public_data", "C05", "boundary", "define public aggregate source receipts and pseudonymous fixture rows", ("source URLs", "context key", "aggregate rows"), ("fixture", "data audit"), ("source closure", "sixteen paths")),
        _entry("adapters", "C05", "boundary", "validate recurrence payload shape before execution", ("fixture payload",), ("adapter result",), ("required fields",)),
        _entry("schema", "C05", "contract", "declare recurrence fields and null policies", ("operation definition",), ("schema report",), ("required fields",)),
        _entry("fixture_eval", "C05", "execution", "run recurrence and hotspot tester across four paths", ("typed observations",), ("state result",), ("expected state", "context gate")),
        _entry("metrics", "C05", "measurement", "count supported and control states", ("evaluation rows",), ("operation metric",), ("four rows")),
        _entry("lineage", "C05", "trace", "connect source receipts to inputs and outputs", ("fixture", "evaluation"), ("lineage graph",), ("edge closure",)),
        _entry("provenance", "C05", "trace", "retain public source versions and addresses", ("sources", "evaluation"), ("provenance graph",), ("node closure",)),
        _entry("policy", "C05", "policy", "publish supported recurrence and hold controls", ("evaluation", "contracts"), ("policy decisions",), ("state ceiling",)),
        _entry("quality_gate", "C05", "release", "block release on mismatch or missing lineage", ("fixture", "evaluation", "lineage"), ("quality gate",), ("reconciliation",)),
        _entry("replay", "C05", "release", "prove identical input produces identical addresses", ("fixture",), ("replay receipt",), ("address equality",)),
        _entry("public_data_c06", "C06", "boundary", "define callable regions and burden observations", ("region receipts", "variant rows"), ("burden payload",), ("callable bases",)),
        _entry("fixture_eval_c06", "C06", "execution", "run regional burden comparator across controls", ("regions", "observations"), ("burden result",), ("exact overlap",)),
        _entry("comparator_c06", "C06", "measurement", "record numerator and callable denominator", ("burden result",), ("comparator receipt",), ("denominator receipt",)),
        _entry("policy_c06", "C06", "policy", "hold burden without a declared comparator", ("burden result",), ("policy decision",), ("partial state",)),
        _entry("public_data_c07", "C07", "boundary", "define observed and matched-control feature rows", ("feature receipts",), ("functional payload",), ("support bounds",)),
        _entry("fixture_eval_c07", "C07", "execution", "run feature-level convergence and tie handling", ("functional rows",), ("functional result",), ("control visibility",)),
        _entry("comparator_c07", "C07", "measurement", "record feature support contrast", ("functional result",), ("comparator receipt",), ("feature namespace",)),
        _entry("policy_c07", "C07", "policy", "keep no-control feature summaries in review", ("functional result",), ("policy decision",), ("partial state",)),
        _entry("public_data_c08", "C08", "boundary", "define versioned pathway and regulon membership rows", ("set receipts",), ("set payload",), ("set namespace",)),
        _entry("fixture_eval_c08", "C08", "execution", "run set convergence and direction conflict handling", ("set rows",), ("set result",), ("direction retention",)),
        _entry("comparator_c08", "C08", "measurement", "record observed and control gene membership", ("set result",), ("comparator receipt",), ("set version",)),
        _entry("policy_c08", "C08", "policy", "quarantine contradictory leading directions", ("set result",), ("policy decision",), ("contradiction state",)),
        _entry("claims", "C05-C08", "boundary", "attach allowed and prohibited claim ceiling", ("contracts",), ("claim boundary", "claim ledger"), ("prohibited claims",)),
        _entry("safety", "C05-C08", "control", "enforce context, state, comparator, and source rules", ("evaluation", "policy"), ("safety report",), ("all findings accepted",)),
        _entry("publication", "C05-C08", "projection", "separate public summary, review, and operations artifacts", ("evaluation", "policy"), ("publication plan",), ("four publishable rows",)),
        _entry("access_model", "C05-C08", "projection", "control field access by audience and disposition", ("requests", "roles"), ("access report",), ("unknown field deny",)),
        _entry("monitoring", "C05-C08", "operations", "monitor acceptance, sources, controls, and review load", ("metrics", "fixture audit"), ("monitoring report",), ("stop thresholds",)),
        _entry("provenance_ledger", "C05-C08", "trace", "chain source and runtime events in append-only order", ("sources", "stages"), ("ledger",), ("head continuity",)),
        _entry("benchmark", "C05-C08", "operations", "bound workload units for the deterministic fixture", ("evaluation",), ("benchmark report",), ("work budget",)),
        _entry("calibration", "C05-C08", "boundary", "record calibration requirements without fabricating p-values", ("comparator report",), ("calibration report",), ("missing requirements visible",)),
        _entry("sampling", "C05-C08", "measurement", "document units, denominators, inclusions, and exclusions", ("evaluation",), ("sampling report",), ("denominator text",)),
        _entry("evidence_matrix", "C05-C08", "review", "present cross-operation coverage for navigation", ("fixture", "evaluation"), ("evidence matrix",), ("sixteen cells",)),
        _entry("change_control", "C05-C08", "operations", "route schema, fixture, and threshold changes", ("change requests",), ("change decisions",), ("breaking changes held",)),
        _entry("redaction", "C05-C08", "projection", "mask row keys and retain source context by audience", ("record mapping",), ("redaction result",), ("context retained",)),
        _entry("report", "C05-C08", "projection", "render bounded metrics and claim ceiling", ("metrics", "release"), ("markdown report",), ("claim ceiling",)),
        _entry("runtime", "C05-C08", "release", "execute ordered stages and return a content-addressed report", ("fixture",), ("runtime report",), ("all stages accepted",)),
    )
    layers = {item.layer for item in entries}
    operations = {item.operation for item in entries}
    return CohortBetaFrontierModuleCatalog(entries, len(layers), len(operations), len(entries) >= 32 and layers >= {"boundary", "contract", "execution", "measurement", "trace", "policy", "release", "projection", "control", "operations", "review"}, content_hash(entries, prefix="module-catalog"))


def module_catalog_summary(catalog: CohortBetaFrontierModuleCatalog) -> Mapping[str, Any]:
    return {"entry_count": len(catalog.entries), "layer_count": catalog.layer_count, "operation_count": catalog.operation_count, "by_layer": {layer: len(catalog.for_layer(layer)) for layer in sorted({item.layer for item in catalog.entries})}, "by_operation": {operation: len(catalog.for_operation(operation)) for operation in sorted({item.operation for item in catalog.entries})}, "accepted": catalog.accepted}


__all__ = ["CohortBetaFrontierModuleCatalog", "CohortBetaFrontierModuleEntry", "default_cohort_beta_frontier_module_catalog", "module_catalog_summary"]
