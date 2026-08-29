"""Pairwise package agreement matrix for a package-registry federation.

The federation receipt answers whether the complete peer set is acceptable.
This module answers the more operational question: which peer pairs agree on
which package observations, and where does a missing or divergent observation
enter the evidence graph?  The matrix is deterministic, bounded, addressable,
and deliberately derived only from the federation receipt.
"""

from __future__ import annotations

import csv
import io
from itertools import combinations
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-matrix-v1"
BOUNDARY = federation_model.BOUNDARY + "_matrix"
MATRIX_PREFIX = federation_model.FEDERATION_PREFIX + "-matrix"
OBSERVATION_PREFIX = federation_model.FEDERATION_PREFIX + "-matrix-observation"
MAX_PEERS = federation_model.MAX_PEERS
MAX_PACKAGES = federation_model.MAX_PACKAGES
MAX_OBSERVATIONS = MAX_PEERS * (MAX_PEERS - 1) // 2
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "federation-conservation",
    "peer-conservation",
    "pair-conservation",
    "observation-conservation",
    "ordinal-conservation",
    "package-conservation",
    "count-conservation",
    "ratio-conservation",
    "state-conservation",
    "evidence-conservation",
    "address-conservation",
    "mapping-round-trip",
    "content-address",
    "path-free",
)


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512)
    if not value.startswith(prefix + ":") or "/" in value or "\\" in value:
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 1:
        raise ValidationError(f"{field} must be a ratio between zero and one")
    rounded = round(float(value), 6)
    if rounded != value and abs(rounded - float(value)) > 0.000001:
        raise ValidationError(f"{field} has excessive precision")
    return rounded


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(labels)) != len(labels):
        raise ValidationError(f"{field} must not contain duplicates")
    return tuple(sorted(labels))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    addresses = tuple(_text(item, field, 512) for item in _sequence(value, field, maximum))
    if len(set(addresses)) != len(addresses) or any("/" in item or "\\" in item for item in addresses):
        raise ValidationError(f"{field} must contain unique path-free addresses")
    return tuple(sorted(addresses))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "\\" not in value and "/" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


def _pair_key(left_peer_id: str, right_peer_id: str) -> tuple[str, str]:
    left_peer_id = _label(left_peer_id, "left peer ID")
    right_peer_id = _label(right_peer_id, "right peer ID")
    if left_peer_id == right_peer_id:
        raise ValidationError("matrix pair peers must be distinct")
    return tuple(sorted((left_peer_id, right_peer_id)))


def _comparison_ratio(matching: int, divergent: int, left_only: int, right_only: int) -> float:
    denominator = matching + divergent + left_only + right_only
    return 1.0 if denominator == 0 else round(matching / denominator, 6)


class RegistryFederationMatrixObservation:
    """One unordered peer-pair comparison."""

    FIELDS = (
        "ordinal",
        "left_peer_id",
        "right_peer_id",
        "package_ids",
        "common_package_count",
        "matching_package_count",
        "divergent_package_count",
        "left_only_count",
        "right_only_count",
        "agreement_ratio",
        "state",
        "detail",
        "evidence_addresses",
        "content_address",
    )

    def __init__(self, ordinal: int, left_peer_id: str, right_peer_id: str, package_ids: Sequence[str], common_package_count: int, matching_package_count: int, divergent_package_count: int, left_only_count: int, right_only_count: int, agreement_ratio: float, state: str, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "matrix observation ordinal", MAX_OBSERVATIONS, positive=True)
        self.left_peer_id, self.right_peer_id = _pair_key(left_peer_id, right_peer_id)
        self.package_ids = _labels(package_ids, "matrix observation package IDs", MAX_PACKAGES)
        self.common_package_count = _count(common_package_count, "common package count", MAX_PACKAGES)
        self.matching_package_count = _count(matching_package_count, "matching package count", self.common_package_count)
        self.divergent_package_count = _count(divergent_package_count, "divergent package count", self.common_package_count)
        self.left_only_count = _count(left_only_count, "left-only package count", MAX_PACKAGES)
        self.right_only_count = _count(right_only_count, "right-only package count", MAX_PACKAGES)
        self.agreement_ratio = _ratio(agreement_ratio, "agreement ratio")
        if self.common_package_count != self.matching_package_count + self.divergent_package_count:
            raise ValidationError("matrix common package counts are not conserved")
        if len(self.package_ids) != self.common_package_count + self.left_only_count + self.right_only_count:
            raise ValidationError("matrix package union is not conserved")
        if self.agreement_ratio != _comparison_ratio(self.matching_package_count, self.divergent_package_count, self.left_only_count, self.right_only_count):
            raise ValidationError("matrix agreement ratio is not conserved")
        if state not in federation_model.STATES:
            raise ValidationError("matrix observation state is unsupported")
        self.state = state
        if self.state == "consistent" and self.divergent_package_count + self.left_only_count + self.right_only_count:
            raise ValidationError("consistent matrix observation contains differences")
        if self.state == "conflicted" and self.divergent_package_count + self.left_only_count + self.right_only_count == 0:
            raise ValidationError("conflicted matrix observation has no difference")
        self.detail = _text(detail, "matrix observation detail")
        self.evidence_addresses = _addresses(evidence_addresses, "matrix evidence addresses", MAX_PACKAGES + 2)
        self.content_address = _address(content_address, "matrix observation content address", OBSERVATION_PREFIX)
        if not self.content_address.endswith(":pending") and address_observation(self) != self.content_address:
            raise ValidationError("matrix observation content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("matrix observation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationMatrixObservation:
        value = _mapping(value, "matrix observation")
        _strict(value, set(cls.FIELDS), "matrix observation")
        return cls(*(value[field] for field in cls.FIELDS))


def address_observation(value: RegistryFederationMatrixObservation) -> str:
    if not isinstance(value, RegistryFederationMatrixObservation):
        raise ValidationError("matrix observation address requires a typed observation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVATION_PREFIX)


class RegistryFederationMatrix:
    """The complete unordered peer-pair agreement matrix."""

    FIELDS = (
        "matrix_id",
        "federation_id",
        "federation_address",
        "peer_ids",
        "observations",
        "pair_count",
        "matching_pair_count",
        "divergent_pair_count",
        "agreement_ratio",
        "state",
        "content_address",
    )

    def __init__(self, matrix_id: str, federation_id: str, federation_address: str, peer_ids: Sequence[str], observations: Sequence[RegistryFederationMatrixObservation], pair_count: int, matching_pair_count: int, divergent_pair_count: int, agreement_ratio: float, state: str, content_address: str) -> None:
        self.matrix_id = _label(matrix_id, "matrix ID")
        self.federation_id = _label(federation_id, "matrix federation ID")
        self.federation_address = _address(federation_address, "matrix federation address", federation_model.FEDERATION_PREFIX)
        self.peer_ids = _labels(peer_ids, "matrix peer IDs", MAX_PEERS)
        self.observations = tuple(observations)
        if len(self.observations) > MAX_OBSERVATIONS or any(not isinstance(item, RegistryFederationMatrixObservation) for item in self.observations):
            raise ValidationError("matrix observations are outside the bound")
        self.pair_count = _count(pair_count, "matrix pair count", MAX_OBSERVATIONS)
        self.matching_pair_count = _count(matching_pair_count, "matrix matching pair count", self.pair_count)
        self.divergent_pair_count = _count(divergent_pair_count, "matrix divergent pair count", self.pair_count)
        self.agreement_ratio = _ratio(agreement_ratio, "matrix agreement ratio")
        if len(self.peer_ids) < 1:
            raise ValidationError("matrix requires at least one peer")
        expected_pairs = len(self.peer_ids) * (len(self.peer_ids) - 1) // 2
        actual_pairs = tuple((item.left_peer_id, item.right_peer_id) for item in self.observations)
        if self.pair_count != expected_pairs or len(self.observations) != self.pair_count or actual_pairs != tuple(sorted(actual_pairs)) or set(actual_pairs) != set(combinations(self.peer_ids, 2)):
            raise ValidationError("matrix pair conservation failed")
        if self.matching_pair_count != sum(item.state == "consistent" for item in self.observations) or self.divergent_pair_count != sum(item.state == "conflicted" for item in self.observations):
            raise ValidationError("matrix pair states are not conserved")
        matching = sum(item.matching_package_count for item in self.observations)
        divergent = sum(item.divergent_package_count for item in self.observations)
        left_only = sum(item.left_only_count for item in self.observations)
        right_only = sum(item.right_only_count for item in self.observations)
        if self.agreement_ratio != _comparison_ratio(matching, divergent, left_only, right_only):
            raise ValidationError("matrix agreement ratio is not conserved")
        expected_state = "consistent" if self.divergent_pair_count == 0 else "conflicted"
        if state != expected_state:
            raise ValidationError("matrix state is not conserved")
        self.state = state
        self.content_address = _address(content_address, "matrix content address", MATRIX_PREFIX)
        if not self.content_address.endswith(":pending") and address_matrix(self) != self.content_address:
            raise ValidationError("matrix content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("matrix crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"matrix_id": self.matrix_id, "federation_id": self.federation_id, "federation_address": self.federation_address, "peer_ids": self.peer_ids, "observations": tuple(item.to_dict() for item in self.observations), "pair_count": self.pair_count, "matching_pair_count": self.matching_pair_count, "divergent_pair_count": self.divergent_pair_count, "agreement_ratio": self.agreement_ratio, "state": self.state, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"peer_ids", "observations"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationMatrix:
        value = _mapping(value, "federation matrix")
        _strict(value, set(cls.FIELDS), "federation matrix")
        peers = tuple(value["peer_ids"]) if isinstance(value["peer_ids"], list) else value["peer_ids"]
        observations = tuple(value["observations"]) if isinstance(value["observations"], list) else value["observations"]
        return cls(value["matrix_id"], value["federation_id"], value["federation_address"], peers, tuple(RegistryFederationMatrixObservation.from_mapping(item) for item in observations), value["pair_count"], value["matching_pair_count"], value["divergent_pair_count"], value["agreement_ratio"], value["state"], value["content_address"])


def address_matrix(value: RegistryFederationMatrix) -> str:
    if not isinstance(value, RegistryFederationMatrix):
        raise ValidationError("matrix address requires a typed matrix")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MATRIX_PREFIX)


def _peer_package_map(peer: Any) -> dict[str, str]:
    return dict(zip(peer.package_ids, peer.package_addresses, strict=True))


def _observation(ordinal: int, left: Any, right: Any) -> RegistryFederationMatrixObservation:
    left_map = _peer_package_map(left)
    right_map = _peer_package_map(right)
    left_ids = set(left_map)
    right_ids = set(right_map)
    common_ids = left_ids & right_ids
    matching_ids = {package_id for package_id in common_ids if left_map[package_id] == right_map[package_id]}
    divergent_ids = common_ids - matching_ids
    left_only = left_ids - right_ids
    right_only = right_ids - left_ids
    package_ids = tuple(sorted(left_ids | right_ids))
    evidence = tuple(sorted({left.content_address, right.content_address, *left_map.values(), *right_map.values()}))
    state = "consistent" if not divergent_ids and not left_only and not right_only else "conflicted"
    detail = f"{len(matching_ids)} matching, {len(divergent_ids)} divergent, {len(left_only)} left-only, {len(right_only)} right-only package observations"
    provisional = RegistryFederationMatrixObservation(ordinal, left.peer_id, right.peer_id, package_ids, len(common_ids), len(matching_ids), len(divergent_ids), len(left_only), len(right_only), _comparison_ratio(len(matching_ids), len(divergent_ids), len(left_only), len(right_only)), state, detail, evidence, OBSERVATION_PREFIX + ":pending")
    return RegistryFederationMatrixObservation(provisional.ordinal, provisional.left_peer_id, provisional.right_peer_id, provisional.package_ids, provisional.common_package_count, provisional.matching_package_count, provisional.divergent_package_count, provisional.left_only_count, provisional.right_only_count, provisional.agreement_ratio, provisional.state, provisional.detail, provisional.evidence_addresses, address_observation(provisional))


def build_matrix(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, *, matrix_id: str = "federation-matrix") -> RegistryFederationMatrix:
    value = federation_model.verify_federation(value)
    peer_map = {peer.peer_id: peer for peer in value.peers}
    peer_ids = tuple(sorted(peer_map))
    observations = tuple(_observation(ordinal, peer_map[left], peer_map[right]) for ordinal, (left, right) in enumerate(combinations(peer_ids, 2), start=1))
    matching = sum(item.matching_package_count for item in observations)
    divergent = sum(item.divergent_package_count for item in observations)
    left_only = sum(item.left_only_count for item in observations)
    right_only = sum(item.right_only_count for item in observations)
    provisional = RegistryFederationMatrix(matrix_id, value.federation_id, value.content_address, peer_ids, observations, len(observations), sum(item.state == "consistent" for item in observations), sum(item.state == "conflicted" for item in observations), _comparison_ratio(matching, divergent, left_only, right_only), "consistent" if not any(item.state == "conflicted" for item in observations) else "conflicted", MATRIX_PREFIX + ":pending")
    return RegistryFederationMatrix(provisional.matrix_id, provisional.federation_id, provisional.federation_address, provisional.peer_ids, provisional.observations, provisional.pair_count, provisional.matching_pair_count, provisional.divergent_pair_count, provisional.agreement_ratio, provisional.state, address_matrix(provisional))


def matrix_from_mapping(value: Mapping[str, Any]) -> RegistryFederationMatrix:
    return verify_matrix(RegistryFederationMatrix.from_mapping(value))


def verify_matrix(value: RegistryFederationMatrix) -> RegistryFederationMatrix:
    if not isinstance(value, RegistryFederationMatrix) or (not value.content_address.endswith(":pending") and address_matrix(value) != value.content_address):
        raise ValidationError("federation matrix is not valid")
    return value


def matrix_json(value: RegistryFederationMatrix) -> str:
    return canonical_json(verify_matrix(value).to_dict())


def matrix_csv(value: RegistryFederationMatrix) -> str:
    value = verify_matrix(value)
    stream = io.StringIO()
    fields = ("ordinal", "left_peer_id", "right_peer_id", "package_ids", "common_package_count", "matching_package_count", "divergent_package_count", "left_only_count", "right_only_count", "agreement_ratio", "state", "detail", "evidence_addresses", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.observations:
        record = item.to_dict()
        record["package_ids"] = "|".join(item.package_ids)
        record["evidence_addresses"] = "|".join(item.evidence_addresses)
        writer.writerow(record)
    return stream.getvalue()


def render_matrix_markdown(value: RegistryFederationMatrix) -> str:
    value = verify_matrix(value)
    lines = ["# Package Registry Federation Agreement Matrix", "", f"- Federation: `{value.federation_id}`", f"- State: `{value.state}`", f"- Agreement ratio: `{value.agreement_ratio:.6f}`", f"- Matrix address: `{value.content_address}`", "", "| pair | matching | divergent | left-only | right-only | ratio | state |", "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    lines.extend(f"| `{item.left_peer_id}` ↔ `{item.right_peer_id}` | {item.matching_package_count} | {item.divergent_package_count} | {item.left_only_count} | {item.right_only_count} | {item.agreement_ratio:.6f} | `{item.state}` |" for item in value.observations)
    return "\n".join(lines) + "\n"


def matrix_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationMatrix.FIELDS), "properties": {"matrix_id": {"type": "string"}, "federation_id": {"type": "string"}, "federation_address": {"type": "string", "pattern": "^" + federation_model.FEDERATION_PREFIX + ":"}, "peer_ids": {"type": "array", "minItems": 1, "maxItems": MAX_PEERS}, "observations": {"type": "array", "maxItems": MAX_OBSERVATIONS, "items": observation_schema()}, "pair_count": {"type": "integer", "minimum": 0}, "matching_pair_count": {"type": "integer", "minimum": 0}, "divergent_pair_count": {"type": "integer", "minimum": 0}, "agreement_ratio": {"type": "number", "minimum": 0, "maximum": 1}, "state": {"type": "string", "enum": list(federation_model.STATES)}, "content_address": {"type": "string", "pattern": "^" + MATRIX_PREFIX + ":"}}}


def observation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationMatrixObservation.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "left_peer_id": {"type": "string"}, "right_peer_id": {"type": "string"}, "package_ids": {"type": "array", "maxItems": MAX_PACKAGES}, "common_package_count": {"type": "integer", "minimum": 0}, "matching_package_count": {"type": "integer", "minimum": 0}, "divergent_package_count": {"type": "integer", "minimum": 0}, "left_only_count": {"type": "integer", "minimum": 0}, "right_only_count": {"type": "integer", "minimum": 0}, "agreement_ratio": {"type": "number", "minimum": 0, "maximum": 1}, "state": {"type": "string", "enum": list(federation_model.STATES)}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string", "pattern": "^" + OBSERVATION_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "matrix_prefix": MATRIX_PREFIX, "observation_prefix": OBSERVATION_PREFIX, "query_prefix": QUERY_PREFIX, "result_prefix": RESULT_PREFIX, "row_prefix": ROW_PREFIX, "check_ids": CHECK_IDS, "limits": {"max_peers": MAX_PEERS, "max_packages": MAX_PACKAGES, "max_observations": MAX_OBSERVATIONS}, "features": ("unordered peer-pair comparison", "matching and divergent package counts", "left/right missing observation counts", "bounded agreement ratios", "address-linked pair evidence", "peer and state query filters", "deterministic pagination", "JSON CSV and Markdown exports"), "schemas": ("observation", "matrix", "query", "row", "result")}


QUERY_PREFIX = federation_model.FEDERATION_PREFIX + "-matrix-query"
ROW_PREFIX = federation_model.FEDERATION_PREFIX + "-matrix-query-row"
RESULT_PREFIX = federation_model.FEDERATION_PREFIX + "-matrix-query-result"
MAX_QUERY_ROWS = MAX_OBSERVATIONS
MAX_QUERY_LIMIT = 100


class RegistryFederationMatrixQuery:
    """A replayable filter over pairwise matrix observations."""

    FIELDS = ("query_id", "matrix_address", "peer_id", "state", "offset", "limit", "content_address")

    def __init__(self, query_id: str, matrix_address: str, peer_id: str, state: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "matrix query ID")
        self.matrix_address = _address(matrix_address, "matrix query matrix address", MATRIX_PREFIX)
        self.peer_id = "" if peer_id == "" else _label(peer_id, "matrix query peer ID")
        self.state = "" if state == "" else state
        if self.state and self.state not in federation_model.STATES:
            raise ValidationError("matrix query state is unsupported")
        self.offset = _count(offset, "matrix query offset", MAX_QUERY_ROWS)
        self.limit = _count(limit, "matrix query limit", MAX_QUERY_LIMIT, positive=True)
        self.content_address = _address(content_address, "matrix query content address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("matrix query content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("matrix query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationMatrixQuery:
        value = _mapping(value, "matrix query")
        _strict(value, set(cls.FIELDS), "matrix query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationMatrixQuery) -> str:
    if not isinstance(value, RegistryFederationMatrixQuery):
        raise ValidationError("matrix query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationMatrixQueryRow:
    """A public row projected from one matrix observation."""

    FIELDS = ("ordinal", "row_id", "left_peer_id", "right_peer_id", "state", "common_package_count", "matching_package_count", "divergent_package_count", "left_only_count", "right_only_count", "agreement_ratio", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, row_id: str, left_peer_id: str, right_peer_id: str, state: str, common_package_count: int, matching_package_count: int, divergent_package_count: int, left_only_count: int, right_only_count: int, agreement_ratio: float, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "matrix query row ordinal", MAX_QUERY_ROWS, positive=True)
        self.row_id = _label(row_id, "matrix query row ID")
        self.left_peer_id, self.right_peer_id = _pair_key(left_peer_id, right_peer_id)
        if state not in federation_model.STATES:
            raise ValidationError("matrix query row state is unsupported")
        self.state = state
        self.common_package_count = _count(common_package_count, "matrix query common count", MAX_PACKAGES)
        self.matching_package_count = _count(matching_package_count, "matrix query matching count", self.common_package_count)
        self.divergent_package_count = _count(divergent_package_count, "matrix query divergent count", self.common_package_count)
        self.left_only_count = _count(left_only_count, "matrix query left-only count", MAX_PACKAGES)
        self.right_only_count = _count(right_only_count, "matrix query right-only count", MAX_PACKAGES)
        self.agreement_ratio = _ratio(agreement_ratio, "matrix query row ratio")
        if self.common_package_count != self.matching_package_count + self.divergent_package_count or self.agreement_ratio != _comparison_ratio(self.matching_package_count, self.divergent_package_count, self.left_only_count, self.right_only_count):
            raise ValidationError("matrix query row counts are not conserved")
        self.detail = _text(detail, "matrix query row detail")
        self.evidence_addresses = _addresses(evidence_addresses, "matrix query row evidence", MAX_PACKAGES + 2)
        self.content_address = _address(content_address, "matrix query row content address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_query_row(self) != self.content_address:
            raise ValidationError("matrix query row content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("matrix query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationMatrixQueryRow:
        value = _mapping(value, "matrix query row")
        _strict(value, set(cls.FIELDS), "matrix query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query_row(value: RegistryFederationMatrixQueryRow) -> str:
    if not isinstance(value, RegistryFederationMatrixQueryRow):
        raise ValidationError("matrix query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationMatrixQueryResult:
    """A bounded page with conservation counters for a matrix query."""

    FIELDS = ("query", "matrix_id", "matrix_state", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationMatrixQuery, matrix_id: str, matrix_state: str, rows: Sequence[RegistryFederationMatrixQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryFederationMatrixQuery):
            raise ValidationError("matrix query result query must be typed")
        self.query = query
        self.matrix_id = _label(matrix_id, "matrix query result matrix ID")
        if matrix_state not in federation_model.STATES:
            raise ValidationError("matrix query result state is unsupported")
        self.matrix_state = matrix_state
        self.rows = tuple(rows)
        if len(self.rows) > query.limit or any(not isinstance(row, RegistryFederationMatrixQueryRow) for row in self.rows):
            raise ValidationError("matrix query result rows exceed the requested page")
        self.total_count = _count(total_count, "matrix query total count", MAX_QUERY_ROWS)
        self.matched_count = _count(matched_count, "matrix query matched count", self.total_count)
        self.returned_count = _count(returned_count, "matrix query returned count", query.limit)
        self.next_offset = _count(next_offset, "matrix query next offset", MAX_QUERY_ROWS)
        self.truncated = _bool(truncated, "matrix query truncated flag")
        if self.returned_count != len(self.rows) or self.matched_count < self.returned_count or self.next_offset != (query.offset + self.returned_count if self.truncated else 0) or self.truncated != (self.next_offset > 0) or tuple(row.ordinal for row in self.rows) != tuple(range(1, len(self.rows) + 1)):
            raise ValidationError("matrix query pagination counters are not conserved")
        self.content_address = _address(content_address, "matrix query result content address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_query_result(self) != self.content_address:
            raise ValidationError("matrix query result content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("matrix query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "matrix_id": self.matrix_id, "matrix_state": self.matrix_state, "rows": tuple(row.to_dict() for row in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationMatrixQueryResult:
        value = _mapping(value, "matrix query result")
        _strict(value, set(cls.FIELDS), "matrix query result")
        rows = tuple(value["rows"]) if isinstance(value["rows"], list) else value["rows"]
        return cls(RegistryFederationMatrixQuery.from_mapping(value["query"]), value["matrix_id"], value["matrix_state"], tuple(RegistryFederationMatrixQueryRow.from_mapping(item) for item in rows), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_query_result(value: RegistryFederationMatrixQueryResult) -> str:
    if not isinstance(value, RegistryFederationMatrixQueryResult):
        raise ValidationError("matrix query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def build_query(value: RegistryFederationMatrix, *, query_id: str = "federation-matrix-query", peer_id: str = "", state: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationMatrixQuery:
    value = verify_matrix(value)
    provisional = RegistryFederationMatrixQuery(query_id, value.content_address, peer_id, state, offset, limit, QUERY_PREFIX + ":pending")
    return RegistryFederationMatrixQuery(provisional.query_id, provisional.matrix_address, provisional.peer_id, provisional.state, provisional.offset, provisional.limit, address_query(provisional))


def _query_row(ordinal: int, item: RegistryFederationMatrixObservation) -> RegistryFederationMatrixQueryRow:
    provisional = RegistryFederationMatrixQueryRow(ordinal, f"pair-{item.left_peer_id}-{item.right_peer_id}", item.left_peer_id, item.right_peer_id, item.state, item.common_package_count, item.matching_package_count, item.divergent_package_count, item.left_only_count, item.right_only_count, item.agreement_ratio, item.detail, item.evidence_addresses, ROW_PREFIX + ":pending")
    return RegistryFederationMatrixQueryRow(provisional.ordinal, provisional.row_id, provisional.left_peer_id, provisional.right_peer_id, provisional.state, provisional.common_package_count, provisional.matching_package_count, provisional.divergent_package_count, provisional.left_only_count, provisional.right_only_count, provisional.agreement_ratio, provisional.detail, provisional.evidence_addresses, address_query_row(provisional))


def query_matrix(value: RegistryFederationMatrix, query: RegistryFederationMatrixQuery | None = None, **query_kwargs: Any) -> RegistryFederationMatrixQueryResult:
    value = verify_matrix(value)
    query = build_query(value, **query_kwargs) if query is None else RegistryFederationMatrixQuery.from_mapping(query.to_dict())
    if query.matrix_address != value.content_address:
        raise ValidationError("matrix query address does not match the supplied matrix")
    matched = tuple(item for item in value.observations if (not query.peer_id or query.peer_id in {item.left_peer_id, item.right_peer_id}) and (not query.state or item.state == query.state))
    page = matched[query.offset:query.offset + query.limit]
    rows = tuple(_query_row(index, item) for index, item in enumerate(page, start=1))
    truncated = query.offset + len(page) < len(matched)
    next_offset = query.offset + len(page) if truncated else 0
    provisional = RegistryFederationMatrixQueryResult(query, value.matrix_id, value.state, rows, len(value.observations), len(matched), len(rows), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationMatrixQueryResult(provisional.query, provisional.matrix_id, provisional.matrix_state, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_query_result(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationMatrixQueryResult:
    return verify_query_result(RegistryFederationMatrixQueryResult.from_mapping(value))


def verify_query(value: RegistryFederationMatrixQuery) -> RegistryFederationMatrixQuery:
    if not isinstance(value, RegistryFederationMatrixQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("matrix query is not valid")
    return value


def verify_query_result(value: RegistryFederationMatrixQueryResult) -> RegistryFederationMatrixQueryResult:
    if not isinstance(value, RegistryFederationMatrixQueryResult) or (not value.content_address.endswith(":pending") and address_query_result(value) != value.content_address):
        raise ValidationError("matrix query result is not valid")
    verify_query(value.query)
    return value


def query_json(value: RegistryFederationMatrixQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationMatrixQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    fields = ("ordinal", "row_id", "left_peer_id", "right_peer_id", "state", "common_package_count", "matching_package_count", "divergent_package_count", "left_only_count", "right_only_count", "agreement_ratio", "detail", "evidence_addresses", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        record = row.to_dict()
        record["evidence_addresses"] = "|".join(row.evidence_addresses)
        writer.writerow(record)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationMatrixQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Package Registry Federation Matrix Query", "", f"- Matrix: `{value.matrix_id}`", f"- State: `{value.matrix_state}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Result address: `{value.content_address}`", "", "| pair | state | matching | divergent | left-only | right-only | ratio |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    lines.extend(f"| `{row.left_peer_id}` ↔ `{row.right_peer_id}` | `{row.state}` | {row.matching_package_count} | {row.divergent_package_count} | {row.left_only_count} | {row.right_only_count} | {row.agreement_ratio:.6f} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationMatrixQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "matrix_address": {"type": "string", "pattern": "^" + MATRIX_PREFIX + ":"}, "peer_id": {"type": "string"}, "state": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def query_row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationMatrixQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "row_id": {"type": "string"}, "left_peer_id": {"type": "string"}, "right_peer_id": {"type": "string"}, "state": {"type": "string"}, "common_package_count": {"type": "integer"}, "matching_package_count": {"type": "integer"}, "divergent_package_count": {"type": "integer"}, "left_only_count": {"type": "integer"}, "right_only_count": {"type": "integer"}, "agreement_ratio": {"type": "number"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationMatrixQueryResult.FIELDS), "properties": {"query": query_schema(), "matrix_id": {"type": "string"}, "matrix_state": {"type": "string"}, "rows": {"type": "array", "items": query_row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


__all__ = ["BOUNDARY", "CHECK_IDS", "MATRIX_PREFIX", "MAX_OBSERVATIONS", "OBSERVATION_PREFIX", "QUERY_PREFIX", "RESULT_PREFIX", "ROW_PREFIX", "RegistryFederationMatrix", "RegistryFederationMatrixObservation", "RegistryFederationMatrixQuery", "RegistryFederationMatrixQueryResult", "RegistryFederationMatrixQueryRow", "VERSION", "address_matrix", "address_observation", "address_query", "address_query_result", "address_query_row", "build_matrix", "build_query", "capabilities", "matrix_from_mapping", "matrix_csv", "matrix_json", "matrix_schema", "observation_schema", "query_csv", "query_from_mapping", "query_json", "query_matrix", "query_result_schema", "query_row_schema", "query_schema", "render_matrix_markdown", "render_query_markdown", "verify_matrix", "verify_query", "verify_query_result"]
