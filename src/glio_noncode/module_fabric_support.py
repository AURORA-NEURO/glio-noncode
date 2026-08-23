"""Conservative helpers for module-fabric parsing, resolution, and projection."""

from __future__ import annotations

import importlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from .errors import ValidationError
from .module_fabric_contracts import (
    FabricReferenceKind,
    FabricReferenceReceipt,
    FabricReferenceState,
    FabricRole,
    FabricState,
    MODULE_FABRIC_CONTEXT_KEY,
    MODULE_FABRIC_DOMAIN_IDS,
)
from .serialization import content_hash, jsonable, require_non_empty


_CAPABILITY_RE = re.compile(r"^GNC-(D\d{2})-C(\d{2})$")
_REFERENCE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_PRIVATE_KEYS = frozenset(
    {
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
        "contact_name",
        "email",
        "phone",
    }
)


@dataclass(frozen=True, slots=True)
class ParsedReference:
    reference: str
    module_name: str
    symbol_name: str | None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceResolution:
    parsed: ParsedReference
    state: FabricReferenceState
    detail: str
    module: ModuleType | None = None
    symbol: Any = None

    @property
    def receipt(self) -> FabricReferenceReceipt:
        body = {
            "reference": self.parsed.reference,
            "kind": FabricReferenceKind.IMPLEMENTATION,
            "module_name": self.parsed.module_name,
            "symbol_name": self.parsed.symbol_name,
            "state": self.state,
            "detail": self.detail,
        }
        return FabricReferenceReceipt(**body, content_address=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return {
            "parsed": self.parsed.to_dict(),
            "state": self.state.value,
            "detail": self.detail,
            "receipt": self.receipt.to_dict(),
        }


def parse_reference(reference: str) -> ParsedReference:
    """Split a module or module-symbol reference at its longest valid boundary."""

    value = require_non_empty(str(reference), "reference")
    if not _REFERENCE_RE.fullmatch(value):
        raise ValidationError(f"invalid dotted reference: {value!r}")
    parts = value.split(".")
    if len(parts) == 1:
        return ParsedReference(value, value, None)
    return ParsedReference(value, ".".join(parts[:-1]), parts[-1])


def resolve_reference(reference: str) -> ReferenceResolution:
    """Resolve a module or module attribute without executing arbitrary code."""

    value = require_non_empty(str(reference), "reference")
    if not _REFERENCE_RE.fullmatch(value):
        raise ValidationError(f"invalid dotted reference: {value!r}")
    try:
        module = importlib.import_module(value)
        parsed = ParsedReference(value, value, None)
        return ReferenceResolution(parsed, FabricReferenceState.RESOLVED, f"imported module {value}", module, module)
    except (ImportError, ModuleNotFoundError, SyntaxError, TypeError, ValueError):
        pass
    parsed = parse_reference(value)
    module: ModuleType | None = None
    module_name = parsed.module_name
    symbol_name = parsed.symbol_name
    try:
        module = importlib.import_module(module_name)
        if symbol_name is None:
            detail = f"imported module {module_name}"
            return ReferenceResolution(parsed, FabricReferenceState.RESOLVED, detail, module, module)
        if not hasattr(module, symbol_name):
            return ReferenceResolution(
                parsed,
                FabricReferenceState.FAILED,
                f"module {module_name} has no attribute {symbol_name}",
                module,
                None,
            )
        symbol = getattr(module, symbol_name)
        detail = f"resolved {symbol_name} from {module_name}"
        return ReferenceResolution(parsed, FabricReferenceState.RESOLVED, detail, module, symbol)
    except (ImportError, ModuleNotFoundError, AttributeError, SyntaxError, TypeError, ValueError) as exc:
        return ReferenceResolution(
            parsed,
            FabricReferenceState.FAILED,
            f"{type(exc).__name__}: {exc}",
            module,
            None,
        )


def reference_receipt(
    reference: str,
    kind: FabricReferenceKind,
) -> FabricReferenceReceipt:
    """Resolve one reference and attach the declared implementation/test kind."""

    resolution = resolve_reference(reference)
    body = {
        "reference": resolution.parsed.reference,
        "kind": kind,
        "module_name": resolution.parsed.module_name,
        "symbol_name": resolution.parsed.symbol_name,
        "state": resolution.state,
        "detail": resolution.detail,
    }
    return FabricReferenceReceipt(**body, content_address=content_hash(body))


def reference_set_receipts(
    references: Iterable[str],
    kind: FabricReferenceKind,
) -> tuple[FabricReferenceReceipt, ...]:
    return tuple(reference_receipt(reference, kind) for reference in references)


def reference_failures(receipts: Iterable[FabricReferenceReceipt]) -> tuple[str, ...]:
    return tuple(
        f"{receipt.kind.value}:{receipt.reference}:{receipt.detail}"
        for receipt in receipts
        if receipt.state is FabricReferenceState.FAILED
    )


def all_resolved(receipts: Iterable[FabricReferenceReceipt]) -> bool:
    return all(item.state is FabricReferenceState.RESOLVED for item in receipts)


def parse_capability_id(value: str) -> tuple[str, int]:
    match = _CAPABILITY_RE.fullmatch(str(value).strip())
    if match is None:
        raise ValidationError(f"invalid capability ID: {value!r}")
    return match.group(1), int(str(value).rsplit("C", 1)[1])


def is_valid_domain_id(value: str) -> bool:
    return str(value) in MODULE_FABRIC_DOMAIN_IDS


def exact_context(value: Any) -> bool:
    return isinstance(value, str) and value == MODULE_FABRIC_CONTEXT_KEY


def safe_json(value: Any) -> Any:
    """Project values while refusing private subject keys and raw object types."""

    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key)
            if normalized.lower() in _PRIVATE_KEYS:
                raise ValidationError(f"private field is not allowed in module-fabric output: {normalized}")
            output[normalized] = safe_json(item)
        return output
    if isinstance(value, (list, tuple)):
        return [safe_json(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValidationError(f"unsupported value in module-fabric projection: {type(value).__name__}")


def contains_private_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(str(key).lower() in _PRIVATE_KEYS or contains_private_key(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(contains_private_key(item) for item in value)
    return False


def public_source_ids(source_ids: Iterable[str], known: Iterable[str]) -> bool:
    allowed = set(known)
    values = tuple(str(item) for item in source_ids)
    return bool(values) and set(values).issubset(allowed)


def distinct(values: Iterable[str]) -> bool:
    items = tuple(values)
    return len(items) == len(set(items))


def context_mismatch(value: Any) -> bool:
    return isinstance(value, str) and value != MODULE_FABRIC_CONTEXT_KEY


def parse_fixture_text(text: str) -> Mapping[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"module-fabric fixture is not valid JSON: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ValidationError("module-fabric fixture root must be an object")
    return value


def sorted_issue_codes(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(str(item) for item in values if str(item).strip())))


def expected_role_state(role: FabricRole) -> FabricState:
    return FabricState.ACCEPTED if role is FabricRole.POSITIVE else FabricState.REVIEW


def summarize_states(states: Iterable[FabricState]) -> dict[str, int]:
    result = {state.value: 0 for state in FabricState}
    for state in states:
        result[state.value] += 1
    return result


__all__ = [
    "ParsedReference",
    "ReferenceResolution",
    "all_resolved",
    "contains_private_key",
    "context_mismatch",
    "distinct",
    "exact_context",
    "expected_role_state",
    "is_valid_domain_id",
    "parse_capability_id",
    "parse_fixture_text",
    "parse_reference",
    "public_source_ids",
    "reference_failures",
    "reference_receipt",
    "reference_set_receipts",
    "resolve_reference",
    "safe_json",
    "sorted_issue_codes",
    "summarize_states",
]
