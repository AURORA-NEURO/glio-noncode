"""Domain 01 scientific-beta variation and annotation contracts.

This module extends the MVP intake boundary without replacing it. It adds four
independent, source-accounted operations:

* Cat-VRS-shaped categorical variation definitions and exact/alias matching;
* VA-Spec-shaped statement/evidence envelopes with provenance completeness;
* lossless multi-allelic decomposition with genotype projections; and
* local-window repeat equivalence enumeration with explicit ambiguity.

The objects are deliberately standards-shaped rather than claiming external
schema conformance. Each operation preserves the original input hash, source
version, context, and unresolved states. Unsupported symbolic or structural
forms abstain instead of being flattened into a point allele.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity import normalize_allele, normalize_chromosome, normalize_variant
from .models import VariantIdentity, VariantKind
from .serialization import content_hash, hash_bytes, jsonable, require_non_empty, utc_now


class BetaState(StrEnum):
    """Shared non-clinical state vocabulary for the beta operations."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class VariantBetaIssue:
    """Line- or object-addressable issue retained with an input hash."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    raw_record: Mapping[str, Any] = field(default_factory=dict)
    severity: str = "error"

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CategoricalVariationDefinition:
    """A Cat-VRS-shaped categorical variation definition.

    ``member_variation_ids`` may contain VRS identifiers, local canonical IDs,
    or external identifiers. ``rules`` carries machine-readable membership
    constraints; the normalizer only evaluates declared identifiers and aliases
    and never infers membership from a scientific label alone.
    """

    category_id: str
    label: str
    definition: str
    member_variation_ids: tuple[str, ...]
    rules: Mapping[str, Any]
    source_id: str
    source_version: str
    raw_hash: str
    aliases: tuple[str, ...] = ()
    ontology_terms: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def __post_init__(self) -> None:
        for name in (
            "category_id",
            "label",
            "definition",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.member_variation_ids and not self.rules:
            raise ValidationError("categorical definition needs members or rules")
        if len(self.member_variation_ids) != len(set(self.member_variation_ids)):
            raise ValidationError("categorical member variation IDs must be unique")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_source_id: str = "categorical-input",
        fallback_source_version: str = "unspecified",
        raw_hash_value: str | None = None,
    ) -> CategoricalVariationDefinition:
        if not isinstance(raw, Mapping):
            raise ValidationError("categorical definition must be a mapping")
        members_raw = raw.get("member_variation_ids", raw.get("members", ()))
        aliases_raw = raw.get("aliases", ())
        terms_raw = raw.get("ontology_terms", raw.get("terms", ()))
        return cls(
            category_id=str(raw.get("category_id", raw.get("id", ""))),
            label=str(raw.get("label", "")),
            definition=str(raw.get("definition", raw.get("description", ""))),
            member_variation_ids=_text_tuple(members_raw),
            rules=_mapping_value(raw.get("rules", {})),
            source_id=str(raw.get("source_id", fallback_source_id)),
            source_version=str(
                raw.get("source_version", raw.get("version", fallback_source_version))
            ),
            raw_hash=str(raw_hash_value or raw.get("raw_hash") or content_hash(dict(raw))),
            aliases=_text_tuple(aliases_raw),
            ontology_terms=_text_tuple(terms_raw),
            created_at=str(raw.get("created_at", utc_now().isoformat())),
        )

    @property
    def vrs_object(self) -> dict[str, Any]:
        """Return a standards-shaped object without asserting schema validation."""

        return {
            "type": "CategoricalVariation",
            "id": self.category_id,
            "label": self.label,
            "definition": self.definition,
            "members": list(self.member_variation_ids),
            "rules": jsonable(self.rules),
            "extensions": {
                "aliases": list(self.aliases),
                "ontology_terms": list(self.ontology_terms),
                "source_id": self.source_id,
                "source_version": self.source_version,
                "raw_hash": self.raw_hash,
            },
        }

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"vrs_object": self.vrs_object}


@dataclass(frozen=True, slots=True)
class CategoricalCatalogBatch:
    """Parsed categorical definitions with malformed-row quarantine."""

    source_id: str
    source_version: str
    input_hash: str
    definitions: tuple[CategoricalVariationDefinition, ...]
    issues: tuple[VariantBetaIssue, ...]
    content_address: str

    @property
    def state(self) -> BetaState:
        if not self.definitions:
            return BetaState.ABSTAINED
        return BetaState.PARTIAL if self.issues else BetaState.SUPPORTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"state": self.state.value}


class CategoricalCatalogParser:
    """Parse JSON or delimited categorical definitions losslessly."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> CategoricalCatalogBatch:
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            return self.parse_json(text, source_id=source_id, source_version=source_version)
        if selected not in {"tsv", "csv"}:
            raise ValidationError(f"unsupported categorical catalog format: {selected}")
        delimiter = "\t" if selected == "tsv" else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if reader.fieldnames is None:
            issue = VariantBetaIssue(
                "missing_header",
                "categorical catalog has no header",
                hash_bytes(text.encode("utf-8")),
                row_number=1,
            )
            return self._batch(source_id, source_version, text, (), (issue,))
        lines = text.splitlines()
        rows = []
        for row_number, row in enumerate(reader, start=2):
            raw_line = lines[row_number - 1] if row_number - 1 < len(lines) else ""
            rows.append((row_number, row, hash_bytes(raw_line.encode("utf-8"))))
        return self._resolve_rows(source_id, source_version, text, rows)

    def parse_json(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
    ) -> CategoricalCatalogBatch:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            issue = VariantBetaIssue(
                "invalid_json",
                f"categorical catalog JSON could not be decoded: {exc.msg}",
                hash_bytes(text.encode("utf-8")),
            )
            return self._batch(source_id, source_version, text, (), (issue,))
        rows_raw = (
            payload.get("categories", payload.get("definitions"))
            if isinstance(payload, Mapping)
            else payload
        )
        if isinstance(payload, Mapping) and rows_raw is None:
            rows_raw = [payload]
        if not isinstance(rows_raw, list):
            issue = VariantBetaIssue(
                "invalid_shape",
                "categorical catalog JSON must be an object or list of definitions",
                content_hash(payload),
            )
            return self._batch(source_id, source_version, text, (), (issue,))
        rows = tuple(
            (
                index,
                item,
                content_hash(item) if isinstance(item, Mapping) else content_hash({"raw": item}),
            )
            for index, item in enumerate(rows_raw, start=1)
        )
        return self._resolve_rows(source_id, source_version, text, rows)

    def _resolve_rows(
        self,
        source_id: str,
        source_version: str,
        text: str,
        rows: Iterable[tuple[int, Any, str]],
    ) -> CategoricalCatalogBatch:
        definitions: list[CategoricalVariationDefinition] = []
        issues: list[VariantBetaIssue] = []
        seen: set[str] = set()
        for row_number, row, raw_hash in rows:
            if not isinstance(row, Mapping):
                issues.append(
                    VariantBetaIssue(
                        "row_not_object", "categorical row is not an object", raw_hash, row_number
                    )
                )
                continue
            try:
                definition = CategoricalVariationDefinition.from_mapping(
                    row,
                    fallback_source_id=source_id,
                    fallback_source_version=source_version,
                    raw_hash_value=raw_hash,
                )
            except ValidationError as exc:
                issues.append(
                    VariantBetaIssue(
                        "invalid_definition", str(exc), raw_hash, row_number, dict(row)
                    )
                )
                continue
            if definition.category_id in seen:
                issues.append(
                    VariantBetaIssue(
                        "duplicate_category_id",
                        f"categorical category ID is duplicated: {definition.category_id}",
                        raw_hash,
                        row_number,
                        dict(row),
                    )
                )
                continue
            seen.add(definition.category_id)
            definitions.append(definition)
        return self._batch(source_id, source_version, text, tuple(definitions), tuple(issues))

    @staticmethod
    def _batch(
        source_id: str,
        source_version: str,
        text: str,
        definitions: tuple[CategoricalVariationDefinition, ...],
        issues: tuple[VariantBetaIssue, ...],
    ) -> CategoricalCatalogBatch:
        body = {
            "source_id": source_id,
            "source_version": source_version,
            "input_hash": hash_bytes(text.encode("utf-8")),
            "definitions": definitions,
            "issues": issues,
        }
        return CategoricalCatalogBatch(
            source_id=source_id,
            source_version=source_version,
            input_hash=body["input_hash"],
            definitions=definitions,
            issues=issues,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class CategoricalMatch:
    """One explicit categorical match and its match basis."""

    definition: CategoricalVariationDefinition
    match_basis: tuple[str, ...]
    matched_identifiers: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CategoricalNormalizationReport:
    """Category normalization result with no silent label-based coercion."""

    input_id: str
    input_hash: str
    state: BetaState
    candidates: tuple[CategoricalMatch, ...]
    selected_category_id: str | None
    issues: tuple[VariantBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CatVRSNormalizer:
    """Match categorical inputs against a declared, versioned catalog."""

    def __init__(self, definitions: Iterable[CategoricalVariationDefinition] = ()) -> None:
        values = tuple(definitions)
        ids = tuple(item.category_id for item in values)
        if len(ids) != len(set(ids)):
            raise ValidationError("categorical category IDs must be unique")
        self._definitions = values

    def normalize(
        self,
        raw: CategoricalVariationDefinition | Mapping[str, Any] | str,
        *,
        definitions: Iterable[CategoricalVariationDefinition] | None = None,
    ) -> CategoricalNormalizationReport:
        input_hash = content_hash(
            raw.to_dict() if isinstance(raw, CategoricalVariationDefinition) else raw
        )
        payload: Mapping[str, Any]
        if isinstance(raw, CategoricalVariationDefinition):
            payload = raw.to_dict()
        elif isinstance(raw, str):
            payload = {"category_id": raw}
        elif isinstance(raw, Mapping):
            payload = raw
        else:
            return self._report(
                str(raw),
                input_hash,
                BetaState.INVALID,
                (),
                (),
                ("input must be a mapping or category ID",),
            )
        catalog = tuple(definitions) if definitions is not None else self._definitions
        if not catalog and payload.get("category_id"):
            try:
                inline = CategoricalVariationDefinition.from_mapping(payload)
            except ValidationError:
                inline = None
            if inline is not None:
                catalog = (inline,)
        identifiers = (
            _text_tuple(
                (payload.get("category_id", ""), payload.get("id", ""), payload.get("label", ""))
            )
            + _text_tuple(payload.get("aliases", ()))
            + _text_tuple(payload.get("member_variation_ids", payload.get("members", ())))
        )
        candidates: list[CategoricalMatch] = []
        issues: list[VariantBetaIssue] = []
        for definition in catalog:
            basis: list[str] = []
            matched: list[str] = []
            lower_identifiers = {item.casefold() for item in identifiers}
            if definition.category_id.casefold() in lower_identifiers:
                basis.append("exact_category_id")
                matched.append(definition.category_id)
            for alias in definition.aliases + definition.ontology_terms:
                if alias.casefold() in lower_identifiers:
                    basis.append("declared_alias_or_term")
                    matched.append(alias)
            for member in definition.member_variation_ids:
                if member.casefold() in lower_identifiers:
                    basis.append("declared_member_variation_id")
                    matched.append(member)
            if basis:
                body = {
                    "definition": definition,
                    "match_basis": tuple(dict.fromkeys(basis)),
                    "matched_identifiers": tuple(dict.fromkeys(matched)),
                }
                candidates.append(
                    CategoricalMatch(
                        definition=definition,
                        match_basis=body["match_basis"],
                        matched_identifiers=body["matched_identifiers"],
                        content_address=content_hash(body),
                    )
                )
        if not candidates:
            issues.append(
                VariantBetaIssue(
                    "category_not_resolved",
                    "no declared category, alias, term, or member variation matched the input",
                    input_hash,
                    severity="warning",
                )
            )
            state = BetaState.ABSTAINED
            selected = None
        elif len(candidates) > 1:
            state = BetaState.AMBIGUOUS
            selected = None
        else:
            state = BetaState.SUPPORTED
            selected = candidates[0].definition.category_id
        return self._report(
            str(payload.get("category_id", payload.get("id", "unidentified-category"))),
            input_hash,
            state,
            tuple(candidates),
            tuple(issues),
            (
                "Categorical matching uses only declared identifiers and aliases; "
                "it does not infer scientific membership.",
            ),
            selected=selected,
        )

    @staticmethod
    def _report(
        input_id: str,
        input_hash: str,
        state: BetaState,
        candidates: tuple[CategoricalMatch, ...],
        issues: tuple[VariantBetaIssue, ...],
        warnings: tuple[str, ...],
        *,
        selected: str | None = None,
    ) -> CategoricalNormalizationReport:
        body = {
            "input_id": input_id,
            "input_hash": input_hash,
            "state": state,
            "candidates": candidates,
            "selected": selected,
            "issues": issues,
            "warnings": warnings,
        }
        return CategoricalNormalizationReport(
            input_id=input_id,
            input_hash=input_hash,
            state=state,
            candidates=candidates,
            selected_category_id=selected,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


class AnnotationState(StrEnum):
    """State for a VA-Spec-shaped annotation envelope."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    ABSTAINED = "abstained"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class AnnotationEvidenceLine:
    """Evidence Line-shaped provenance attached to one or more statements."""

    evidence_id: str
    evidence_type: str
    source_id: str
    source_version: str
    raw_hash: str
    state: AnnotationState
    summary: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "evidence_type",
            "source_id",
            "source_version",
            "raw_hash",
            "summary",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AnnotationStatement:
    """Statement-shaped assertion whose evidence and context remain addressable."""

    statement_id: str
    subject_id: str
    predicate: str
    object_value: Any
    object_type: str
    context_key: str
    state: AnnotationState
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    method_id: str
    summary: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "statement_id",
            "subject_id",
            "predicate",
            "object_type",
            "context_key",
            "method_id",
            "summary",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if (
            not self.evidence_ids
            and not self.source_ids
            and self.state == AnnotationState.SUPPORTED
        ):
            raise ValidationError("supported annotation statement requires evidence or source IDs")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_id: str,
        context_key: str,
    ) -> AnnotationStatement:
        if not isinstance(raw, Mapping):
            raise ValidationError("annotation statement must be a mapping")
        return cls(
            statement_id=str(raw.get("statement_id", raw.get("id", fallback_id))),
            subject_id=str(raw.get("subject_id", raw.get("subject", ""))),
            predicate=str(raw.get("predicate", "")),
            object_value=raw.get("object_value", raw.get("object")),
            object_type=str(raw.get("object_type", "unspecified")),
            context_key=str(raw.get("context_key", context_key)),
            state=AnnotationState(str(raw.get("state", AnnotationState.SUPPORTED.value))),
            evidence_ids=_text_tuple(raw.get("evidence_ids", raw.get("evidence", ()))),
            source_ids=_text_tuple(raw.get("source_ids", raw.get("source_id", ()))),
            method_id=str(raw.get("method_id", raw.get("method", "declared_input"))),
            summary=str(raw.get("summary", raw.get("description", ""))),
            attributes=dict(raw.get("attributes", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VAAnnotationEnvelope:
    """VA-Spec-shaped annotation bundle with statement/evidence integrity checks."""

    annotation_id: str
    specification: str
    specification_version: str
    profile: str
    subject: Mapping[str, Any]
    context_key: str
    statements: tuple[AnnotationStatement, ...]
    evidence_lines: tuple[AnnotationEvidenceLine, ...]
    state: AnnotationState
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "annotation_id",
            "specification",
            "specification_version",
            "profile",
            "context_key",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.subject.get("id") and not self.subject.get("type"):
            raise ValidationError("annotation subject needs an id or type")

    @property
    def va_spec_object(self) -> dict[str, Any]:
        return {
            "id": self.annotation_id,
            "type": "Statement",
            "profile": self.profile,
            "subject": jsonable(self.subject),
            "statements": [statement.to_dict() for statement in self.statements],
            "evidence_lines": [line.to_dict() for line in self.evidence_lines],
            "extensions": {
                "specification": self.specification,
                "specification_version": self.specification_version,
                "context_key": self.context_key,
                "state": self.state.value,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"va_spec_object": self.va_spec_object}


class VAAnnotationEnvelopeBuilder:
    """Build statement/evidence envelopes and surface missing provenance."""

    def build(
        self,
        annotation_id: str,
        subject: Mapping[str, Any],
        statements: Iterable[AnnotationStatement],
        evidence_lines: Iterable[AnnotationEvidenceLine] = (),
        *,
        context_key: str,
        profile: str = "glio-noncode.research.statement",
        specification_version: str = "1.0-shaped",
    ) -> VAAnnotationEnvelope:
        require_non_empty(annotation_id, "annotation_id")
        require_non_empty(context_key, "context_key")
        if not isinstance(subject, Mapping) or not (subject.get("id") or subject.get("type")):
            raise ValidationError("annotation subject must expose an id or type")
        statement_values = tuple(statements)
        evidence_values = tuple(evidence_lines)
        statement_ids = tuple(statement.statement_id for statement in statement_values)
        evidence_ids = tuple(line.evidence_id for line in evidence_values)
        if len(statement_ids) != len(set(statement_ids)):
            raise ValidationError("annotation statement IDs must be unique")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValidationError("annotation evidence IDs must be unique")
        evidence_by_id = {line.evidence_id: line for line in evidence_values}
        warnings: list[str] = []
        missing_evidence: set[str] = set()
        context_mismatch: set[str] = set()
        subject_mismatch: set[str] = set()
        subject_id = str(subject.get("id", ""))
        for statement in statement_values:
            if statement.context_key != context_key:
                context_mismatch.add(statement.statement_id)
            if subject_id and statement.subject_id != subject_id:
                subject_mismatch.add(statement.statement_id)
            if any(evidence_id not in evidence_by_id for evidence_id in statement.evidence_ids):
                missing_evidence.add(statement.statement_id)
            if (
                statement.state == AnnotationState.SUPPORTED
                and not statement.evidence_ids
                and not statement.source_ids
            ):
                missing_evidence.add(statement.statement_id)
        predicate_values: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for statement in statement_values:
            if statement.state == AnnotationState.SUPPORTED:
                key = (statement.subject_id, statement.predicate)
                predicate_values[key][
                    json.dumps(jsonable(statement.object_value), sort_keys=True)
                ].append(statement.statement_id)
        contradictory = tuple(
            sorted(key for key, values in predicate_values.items() if len(values) > 1)
        )
        if not statement_values:
            state = AnnotationState.ABSTAINED
            warnings.append("no annotation statements were supplied")
        elif context_mismatch or subject_mismatch:
            state = AnnotationState.OUT_OF_DOMAIN
            if context_mismatch:
                warnings.append("one or more statements use a context outside the envelope")
            if subject_mismatch:
                warnings.append("one or more statements target a subject outside the envelope")
        elif contradictory:
            state = AnnotationState.CONTRADICTORY
            warnings.append("conflicting supported statements were retained without averaging")
        elif missing_evidence:
            state = AnnotationState.PARTIAL
            warnings.append("one or more statements have unresolved evidence references")
        elif any(statement.state == AnnotationState.ABSTAINED for statement in statement_values):
            state = AnnotationState.ABSTAINED
        elif all(statement.state == AnnotationState.SUPPORTED for statement in statement_values):
            state = AnnotationState.SUPPORTED
        else:
            state = AnnotationState.PARTIAL
        body = {
            "annotation_id": annotation_id,
            "specification": "GA4GH VA-Spec-shaped",
            "specification_version": specification_version,
            "profile": profile,
            "subject": subject,
            "context_key": context_key,
            "statements": statement_values,
            "evidence_lines": evidence_values,
            "state": state,
            "warnings": tuple(warnings),
        }
        return VAAnnotationEnvelope(
            annotation_id=annotation_id,
            specification="GA4GH VA-Spec-shaped",
            specification_version=specification_version,
            profile=profile,
            subject=dict(subject),
            context_key=context_key,
            statements=statement_values,
            evidence_lines=evidence_values,
            state=state,
            warnings=tuple(warnings),
            limitations=(
                "This envelope is a local research adapter and is not a clinical interpretation.",
                "VA-Spec-shaped serialization requires external schema validation "
                "before interchange.",
            ),
            content_address=content_hash(body),
        )

    def build_from_mappings(
        self,
        annotation_id: str,
        subject: Mapping[str, Any],
        statements: Iterable[Mapping[str, Any]],
        evidence_lines: Iterable[Mapping[str, Any]] = (),
        *,
        context_key: str,
        profile: str = "glio-noncode.research.statement",
        specification_version: str = "1.0-shaped",
    ) -> VAAnnotationEnvelope:
        statement_values = tuple(
            AnnotationStatement.from_mapping(
                row,
                fallback_id=f"{annotation_id}:statement:{index}",
                context_key=context_key,
            )
            for index, row in enumerate(statements, start=1)
        )
        evidence_values = tuple(
            AnnotationEvidenceLine(
                evidence_id=str(
                    row.get("evidence_id", row.get("id", f"{annotation_id}:evidence:{index}"))
                ),
                evidence_type=str(row.get("evidence_type", row.get("type", "source"))),
                source_id=str(row.get("source_id", "")),
                source_version=str(row.get("source_version", row.get("version", "unspecified"))),
                raw_hash=str(row.get("raw_hash", content_hash(dict(row)))),
                state=AnnotationState(str(row.get("state", AnnotationState.SUPPORTED.value))),
                summary=str(row.get("summary", row.get("description", ""))),
                attributes=dict(row.get("attributes", {})),
            )
            for index, row in enumerate(evidence_lines, start=1)
        )
        return self.build(
            annotation_id,
            subject,
            statement_values,
            evidence_values,
            context_key=context_key,
            profile=profile,
            specification_version=specification_version,
        )


@dataclass(frozen=True, slots=True)
class GenotypeProjection:
    """Allele-specific view of a multi-allelic genotype."""

    original_genotype: str
    allele_tokens: tuple[int | None, ...]
    target_alt_index: int
    target_copy_count: int | None
    other_alt_indices: tuple[int, ...]
    phased: bool
    state: BetaState
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DecomposedAllele:
    """One lossless alternate allele child of a multi-allelic record."""

    parent_id: str
    allele_index: int
    original_alternate: str
    variant: VariantIdentity
    genotype_projection: GenotypeProjection | None
    source_id: str
    source_version: str
    parent_raw_hash: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MultiAllelicDecomposition:
    """Decomposition output with parent record and every issue retained."""

    parent_id: str
    input_hash: str
    state: BetaState
    alternates: tuple[str, ...]
    children: tuple[DecomposedAllele, ...]
    issues: tuple[VariantBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MultiAllelicDecomposer:
    """Split alternate alleles while preserving genotype and parent lineage."""

    def decompose(
        self,
        raw: Mapping[str, Any],
        *,
        genome_build: str = "GRCh38",
        source_id: str = "multiallelic-input",
        source_version: str = "unspecified",
    ) -> MultiAllelicDecomposition:
        input_hash = content_hash(dict(raw))
        issues: list[VariantBetaIssue] = []
        try:
            chromosome = normalize_chromosome(str(raw.get("chromosome", raw.get("chrom", ""))))
            position = int(raw.get("position", raw.get("pos", raw.get("start", 0))))
            reference = normalize_allele(str(raw.get("reference", raw.get("ref", ""))))
            alternates = _alternates(
                raw.get("alternates", raw.get("alts", raw.get("alternate", raw.get("alt"))))
            )
            parent_id = str(
                raw.get(
                    "variant_id",
                    raw.get("id", f"{genome_build}:{chromosome}:{position}:multiallelic"),
                )
            )
            if position < 1 or not alternates:
                raise ValidationError(
                    "multi-allelic input requires a positive position and at least one alternate"
                )
        except (TypeError, ValueError, ValidationError) as exc:
            issue = VariantBetaIssue("invalid_parent", str(exc), input_hash, raw_record=dict(raw))
            return MultiAllelicDecomposition(
                parent_id=str(raw.get("variant_id", "invalid")),
                input_hash=input_hash,
                state=BetaState.INVALID,
                alternates=(),
                children=(),
                issues=(issue,),
                warnings=(),
                content_address=content_hash({"input_hash": input_hash, "issue": issue}),
            )
        genotype = raw.get("genotype", raw.get("gt"))
        projection_values = (
            self._projections(str(genotype), len(alternates), issues)
            if genotype is not None
            else (None,) * len(alternates)
        )
        if genotype is not None and any(
            projection is not None and projection.state == BetaState.ABSTAINED
            for projection in projection_values
        ):
            issues.append(
                VariantBetaIssue(
                    "genotype_projection_abstained",
                    "one or more allele projections contain missing or invalid genotype tokens",
                    input_hash,
                    severity="warning",
                )
            )
        children: list[DecomposedAllele] = []
        for allele_index, alternate in enumerate(alternates, start=1):
            try:
                if alternate.startswith("<") or "[" in alternate or "]" in alternate:
                    raise ValidationError(
                        "symbolic or breakend alternate requires a structural decomposer"
                    )
                variant = normalize_variant(
                    {
                        "notation": f"{chromosome}:{position}:{reference}>{alternate}",
                        "genome_build": genome_build,
                        "variant_id": f"{parent_id}:alt:{allele_index}",
                        "origin": raw.get("origin", "uncertain"),
                        "sample_id": raw.get("sample_id", "unspecified"),
                        "annotations": {
                            "parent_id": parent_id,
                            "allele_index": allele_index,
                            "original_alternate": alternate,
                        },
                    },
                    default_build=genome_build,
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    VariantBetaIssue(
                        "invalid_alternate",
                        f"alternate {allele_index}: {exc}",
                        input_hash,
                        raw_record={"alternate": alternate, "allele_index": allele_index},
                    )
                )
                continue
            projection = projection_values[allele_index - 1]
            body = {
                "parent_id": parent_id,
                "allele_index": allele_index,
                "original_alternate": alternate,
                "variant": variant,
                "genotype_projection": projection,
                "source_id": source_id,
                "source_version": source_version,
                "parent_raw_hash": input_hash,
            }
            children.append(
                DecomposedAllele(
                    parent_id=parent_id,
                    allele_index=allele_index,
                    original_alternate=alternate,
                    variant=variant,
                    genotype_projection=projection,
                    source_id=source_id,
                    source_version=source_version,
                    parent_raw_hash=input_hash,
                    content_address=content_hash(body),
                )
            )
        if not children:
            state = BetaState.ABSTAINED
        elif issues:
            state = BetaState.PARTIAL
        elif len(set(alternates)) != len(alternates):
            state = BetaState.PARTIAL
            issues.append(
                VariantBetaIssue(
                    "duplicate_alternate",
                    "duplicate alternate alleles were retained as separate indexed inputs",
                    input_hash,
                    severity="warning",
                )
            )
        else:
            state = BetaState.SUPPORTED
        body = {
            "parent_id": parent_id,
            "input_hash": input_hash,
            "alternates": alternates,
            "children": children,
            "issues": issues,
            "state": state,
        }
        return MultiAllelicDecomposition(
            parent_id=parent_id,
            input_hash=input_hash,
            state=state,
            alternates=alternates,
            children=tuple(children),
            issues=tuple(issues),
            warnings=(
                "Decomposition creates allele-specific research objects; it does not infer "
                "phasing or clinical significance.",
            ),
            content_address=content_hash(body),
        )

    @staticmethod
    def _projections(
        genotype: str,
        alternate_count: int,
        issues: list[VariantBetaIssue],
    ) -> tuple[GenotypeProjection | None, ...]:
        separator = "|" if "|" in genotype else "/"
        phased = "|" in genotype
        tokens_raw = genotype.split(separator)
        tokens: list[int | None] = []
        for token in tokens_raw:
            if token in {".", ""}:
                tokens.append(None)
                continue
            try:
                value = int(token)
            except ValueError:
                issues.append(
                    VariantBetaIssue(
                        "invalid_genotype",
                        f"genotype token is not an allele index: {token}",
                        content_hash(genotype),
                        severity="warning",
                    )
                )
                tokens.append(None)
                continue
            if value < 0 or value > alternate_count:
                issues.append(
                    VariantBetaIssue(
                        "genotype_allele_out_of_range",
                        f"genotype allele index {value} exceeds alternate count {alternate_count}",
                        content_hash(genotype),
                        severity="warning",
                    )
                )
                tokens.append(None)
            else:
                tokens.append(value)
        values = tuple(tokens)
        output: list[GenotypeProjection] = []
        for target in range(1, alternate_count + 1):
            missing = any(value is None for value in values)
            count = None if missing else sum(value == target for value in values)
            others = tuple(
                sorted(
                    {
                        value
                        for value in values
                        if value is not None and value > 0 and value != target
                    }
                )
            )
            output.append(
                GenotypeProjection(
                    original_genotype=genotype,
                    allele_tokens=values,
                    target_alt_index=target,
                    target_copy_count=count,
                    other_alt_indices=others,
                    phased=phased,
                    state=BetaState.ABSTAINED if missing else BetaState.SUPPORTED,
                    reason=(
                        "one or more genotype alleles are missing or invalid"
                        if missing
                        else "allele-specific copy count projected from declared genotype"
                    ),
                )
            )
        return tuple(output)


class RepeatNormalizationState(StrEnum):
    """State for local repeat-equivalence normalization."""

    SUPPORTED = "supported"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class RepeatPlacement:
    """One locally equivalent placement discovered by sequence replay."""

    start: int
    end: int
    shift_from_input: int
    reference_subsequence: str
    alternate_subsequence: str
    edited_sequence_hash: str
    local_window_hash: str
    equivalence_basis: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RepeatNormalizationReport:
    """Repeat-aware normalization output with every equivalent placement."""

    input_id: str
    input_hash: str
    state: RepeatNormalizationState
    variant: VariantIdentity | None
    placements: tuple[RepeatPlacement, ...]
    selected_placement: RepeatPlacement | None
    reference_start: int | None
    reference_sequence_hash: str | None
    issues: tuple[VariantBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RepeatAwareNormalizer:
    """Enumerate local equivalent edits by replaying them against the sequence."""

    def normalize(
        self,
        raw: VariantIdentity | Mapping[str, Any] | str,
        *,
        reference_sequence: str,
        reference_start: int,
        max_shift_bp: int = 50,
        genome_build: str = "GRCh38",
    ) -> RepeatNormalizationReport:
        input_hash = content_hash(raw.to_dict() if isinstance(raw, VariantIdentity) else raw)
        try:
            variant = self._coerce(raw, genome_build)
        except (TypeError, ValueError, ValidationError) as exc:
            issue = VariantBetaIssue("invalid_variant", str(exc), input_hash)
            return self._report(
                str(raw),
                input_hash,
                RepeatNormalizationState.INVALID,
                None,
                (),
                None,
                reference_start,
                None,
                (issue,),
            )
        sequence = reference_sequence.upper()
        sequence_hash = hash_bytes(sequence.encode("utf-8"))
        if reference_start < 1 or not sequence or max_shift_bp < 0:
            issue = VariantBetaIssue(
                "invalid_reference_window", "reference window or shift bound is invalid", input_hash
            )
            return self._report(
                variant.variant_id,
                input_hash,
                RepeatNormalizationState.ABSTAINED,
                variant,
                (),
                None,
                reference_start,
                sequence_hash,
                (issue,),
            )
        if (
            variant.kind in {VariantKind.BREAKEND, VariantKind.CNV, VariantKind.HAPLOTYPE}
            or "<" in variant.alternate
        ):
            issue = VariantBetaIssue(
                "unsupported_variant_class",
                "repeat-aware local normalization supports SNVs and literal indels only",
                input_hash,
            )
            return self._report(
                variant.variant_id,
                input_hash,
                RepeatNormalizationState.ABSTAINED,
                variant,
                (),
                None,
                reference_start,
                sequence_hash,
                (issue,),
            )
        offset = variant.start - reference_start
        ref_end = offset + len(variant.reference)
        if offset < 0 or ref_end > len(sequence):
            issue = VariantBetaIssue(
                "variant_outside_window",
                "variant reference allele is outside the supplied sequence window",
                input_hash,
            )
            return self._report(
                variant.variant_id,
                input_hash,
                RepeatNormalizationState.ABSTAINED,
                variant,
                (),
                None,
                reference_start,
                sequence_hash,
                (issue,),
            )
        observed_reference = sequence[offset:ref_end]
        if observed_reference != variant.reference:
            issue = VariantBetaIssue(
                "reference_mismatch",
                f"reference allele {variant.reference} does not match supplied "
                f"sequence {observed_reference}",
                input_hash,
            )
            return self._report(
                variant.variant_id,
                input_hash,
                RepeatNormalizationState.ABSTAINED,
                variant,
                (),
                None,
                reference_start,
                sequence_hash,
                (issue,),
            )
        if variant.kind != VariantKind.INDEL:
            placement = self._placement(variant, sequence, reference_start)
            return self._report(
                variant.variant_id,
                input_hash,
                RepeatNormalizationState.SUPPORTED,
                variant,
                (placement,),
                placement,
                reference_start,
                sequence_hash,
                (),
            )
        original_edit = sequence[:offset] + variant.alternate + sequence[ref_end:]
        low = max(reference_start, variant.start - max_shift_bp)
        high = min(
            reference_start + len(sequence) - len(variant.reference),
            variant.start + max_shift_bp,
        )
        placements: list[RepeatPlacement] = []
        for candidate_start in range(low, high + 1):
            candidate_offset = candidate_start - reference_start
            candidate_end = candidate_offset + len(variant.reference)
            if sequence[candidate_offset:candidate_end] != variant.reference:
                continue
            edited = sequence[:candidate_offset] + variant.alternate + sequence[candidate_end:]
            if edited != original_edit:
                continue
            candidate = replace(
                variant,
                start=candidate_start,
                end=candidate_start + len(variant.reference) - 1,
            )
            placements.append(self._placement(candidate, sequence, reference_start, variant.start))
        placements = sorted(placements, key=lambda item: (item.start, item.end))
        if not placements:
            issue = VariantBetaIssue(
                "no_equivalent_placement",
                "the supplied edit could not be replayed in the reference window",
                input_hash,
            )
            return self._report(
                variant.variant_id,
                input_hash,
                RepeatNormalizationState.ABSTAINED,
                variant,
                (),
                None,
                reference_start,
                sequence_hash,
                (issue,),
            )
        state = (
            RepeatNormalizationState.AMBIGUOUS
            if len(placements) > 1
            else RepeatNormalizationState.SUPPORTED
        )
        selected = placements[0] if len(placements) == 1 else None
        warnings = (
            "Equivalence is proven only within the supplied local sequence window and shift bound.",
        )
        return self._report(
            variant.variant_id,
            input_hash,
            state,
            variant,
            tuple(placements),
            selected,
            reference_start,
            sequence_hash,
            (),
            warnings=warnings,
        )

    @staticmethod
    def _coerce(
        raw: VariantIdentity | Mapping[str, Any] | str,
        genome_build: str,
    ) -> VariantIdentity:
        if isinstance(raw, VariantIdentity):
            return raw
        if isinstance(raw, str):
            return normalize_variant(
                {"notation": raw, "genome_build": genome_build},
                default_build=genome_build,
            )
        if not isinstance(raw, Mapping):
            raise ValidationError(
                "repeat normalization input must be a variant, mapping, or notation"
            )
        if "notation" in raw:
            return normalize_variant(raw, default_build=genome_build)
        chromosome = normalize_chromosome(str(raw.get("chromosome", raw.get("chrom", ""))))
        position = int(raw.get("position", raw.get("pos", raw.get("start", 0))))
        reference = normalize_allele(str(raw.get("reference", raw.get("ref", ""))))
        alternate = normalize_allele(str(raw.get("alternate", raw.get("alt", ""))))
        if position < 1:
            raise ValidationError("repeat normalization position must be positive")
        return normalize_variant(
            {
                "notation": f"{chromosome}:{position}:{reference}>{alternate}",
                "genome_build": str(raw.get("genome_build", genome_build)),
                "variant_id": str(raw.get("variant_id", raw.get("id", ""))) or None,
            },
            default_build=genome_build,
        )

    @staticmethod
    def _placement(
        variant: VariantIdentity,
        sequence: str,
        reference_start: int,
        input_start: int | None = None,
    ) -> RepeatPlacement:
        offset = variant.start - reference_start
        ref_end = offset + len(variant.reference)
        edited = sequence[:offset] + variant.alternate + sequence[ref_end:]
        return RepeatPlacement(
            start=variant.start,
            end=variant.end,
            shift_from_input=variant.start
            - (input_start if input_start is not None else variant.start),
            reference_subsequence=variant.reference,
            alternate_subsequence=variant.alternate,
            edited_sequence_hash=hash_bytes(edited.encode("utf-8")),
            local_window_hash=hash_bytes(sequence.encode("utf-8")),
            equivalence_basis="reference substring matched and edited window replayed identically",
        )

    @staticmethod
    def _report(
        input_id: str,
        input_hash: str,
        state: RepeatNormalizationState,
        variant: VariantIdentity | None,
        placements: tuple[RepeatPlacement, ...],
        selected: RepeatPlacement | None,
        reference_start: int | None,
        sequence_hash: str | None,
        issues: tuple[VariantBetaIssue, ...],
        *,
        warnings: tuple[str, ...] = (),
    ) -> RepeatNormalizationReport:
        body = {
            "input_id": input_id,
            "input_hash": input_hash,
            "state": state,
            "variant": variant,
            "placements": placements,
            "selected": selected,
            "reference_start": reference_start,
            "reference_sequence_hash": sequence_hash,
            "issues": issues,
            "warnings": warnings,
        }
        return RepeatNormalizationReport(
            input_id=input_id,
            input_hash=input_hash,
            state=state,
            variant=variant,
            placements=placements,
            selected_placement=selected,
            reference_start=reference_start,
            reference_sequence_hash=sequence_hash,
            issues=issues,
            warnings=warnings,
            content_address=content_hash(body),
        )


def _text_tuple(value: Any) -> tuple[str, ...]:
    """Normalize scalar/list/pipe-delimited text while preserving order."""

    if value is None:
        return ()
    if isinstance(value, str):
        values = value.replace(";", "|").replace(",", "|").split("|")
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        values = [str(item) for item in value]
    else:
        values = [str(value)]
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


def _alternates(value: Any) -> tuple[str, ...]:
    values = _text_tuple(value)
    if not values:
        return ()
    return tuple(
        value if value.startswith("<") or "[" in value or "]" in value else normalize_allele(value)
        for value in values
    )


def _mapping_value(value: Any) -> dict[str, Any]:
    """Coerce a mapping or JSON object cell into a JSON-safe mapping."""

    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


__all__ = [
    "AnnotationEvidenceLine",
    "AnnotationState",
    "AnnotationStatement",
    "BetaState",
    "CatVRSNormalizer",
    "CategoricalCatalogBatch",
    "CategoricalCatalogParser",
    "CategoricalMatch",
    "CategoricalNormalizationReport",
    "CategoricalVariationDefinition",
    "DecomposedAllele",
    "GenotypeProjection",
    "MultiAllelicDecomposition",
    "MultiAllelicDecomposer",
    "RepeatAwareNormalizer",
    "RepeatNormalizationReport",
    "RepeatNormalizationState",
    "RepeatPlacement",
    "VAAnnotationEnvelope",
    "VAAnnotationEnvelopeBuilder",
    "VariantBetaIssue",
]
