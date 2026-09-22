"""Shared VCF field-validation helpers for both variant-intake paths."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .errors import ValidationError

_FORMAT_KEY = re.compile(r"[A-Za-z_][0-9A-Za-z_.]*")
_FLOAT_VALUE = re.compile(
    r"(?:[-+]?(?:[0-9]*\.[0-9]+|[0-9]+)(?:[eE][-+]?[0-9]+)?|[-+]?(?:INF|INFINITY|NAN))",
    re.IGNORECASE,
)
_INTEGER_VALUE = re.compile(r"[+-]?[0-9]+")
_MAX_PHASED_GENOTYPE_PLOIDY = 32
_MAX_PHASED_GENOTYPE_TEXT_LENGTH = 512


@dataclass(frozen=True, slots=True)
class InfoFieldDefinition:
    """The schema-bearing part of one VCF INFO header definition."""

    identifier: str
    number: str
    value_type: str


@dataclass(frozen=True, slots=True)
class FormatFieldDefinition:
    """The schema-bearing part of one VCF FORMAT header definition."""

    identifier: str
    number: str
    value_type: str


def has_duplicate_sample_ids(sample_ids: Sequence[str]) -> bool:
    """Return whether a variant header assigns one sample ID to multiple columns."""

    return len(sample_ids) != len(set(sample_ids))


def has_duplicate_format_keys(format_keys: Sequence[str]) -> bool:
    """Return whether a record assigns one FORMAT key to multiple fields."""

    return len(format_keys) != len(set(format_keys))


def format_key_issue(format_keys: Sequence[str]) -> str | None:
    """Return the VCF-format issue code for malformed or unsafe FORMAT keys."""

    if has_duplicate_format_keys(format_keys):
        return "duplicate_format_key"
    if any(_FORMAT_KEY.fullmatch(key) is None for key in format_keys):
        return "invalid_format_key"
    if "GT" in format_keys and format_keys[0] != "GT":
        return "genotype_format_key_not_first"
    return None


def sample_value_issue(format_keys: Sequence[str], sample_text: str) -> str | None:
    """Return an issue code when the VCF sample cell is malformed."""

    if not sample_text:
        return "sample_data_missing"
    if sample_text == ".":
        return None
    values = sample_text.split(":")
    if any(not value for value in values):
        return "sample_data_empty_field"
    if len(values) > len(format_keys):
        return "sample_data_excess_fields"
    return None


def parse_info_fields(value: str) -> tuple[dict[str, object], str | None]:
    """Parse a VCF INFO field without inferring undeclared value types.

    Values remain lexical strings (or lists of strings for comma-delimited
    values); flag fields map to ``True``. This is intentionally the same in
    both the small-file and streaming importers so provenance does not depend
    on which intake surface handled the file.
    """

    if value == ".":
        return {}, None
    if not value:
        return {}, "empty_info_field"

    parsed: dict[str, object] = {}
    for item in value.split(";"):
        if not item:
            return {}, "empty_info_field"
        key, separator, raw_value = item.partition("=")
        if key != "1000G" and _FORMAT_KEY.fullmatch(key) is None:
            return {}, "invalid_info_key"
        if key in parsed:
            return {}, "duplicate_info_key"
        if not separator:
            parsed[key] = True
            continue
        if not raw_value or "=" in raw_value:
            return {}, "invalid_info_value"
        values = raw_value.split(",")
        if any(not part for part in values):
            return {}, "invalid_info_value"
        parsed[key] = values if len(values) > 1 else values[0]
    return parsed, None


def parse_info_definition(
    line: str,
) -> tuple[InfoFieldDefinition | None, str | None, str | None]:
    """Parse the required INFO ID/Number/Type schema from a VCF header line."""

    prefix = "##INFO=<"
    if not line.startswith(prefix) or not line.endswith(">"):
        return None, "invalid_info_definition", None
    parsed_attributes = _parse_structured_attributes(line[len(prefix) : -1])
    if parsed_attributes is None:
        return None, "invalid_info_definition", None
    attributes, quoted_attributes = parsed_attributes
    identifier = attributes.get("ID")
    number = attributes.get("Number")
    value_type = attributes.get("Type")
    description = attributes.get("Description")
    if (
        not identifier
        or (identifier != "1000G" and _FORMAT_KEY.fullmatch(identifier) is None)
        or not number
        or not value_type
        or description is None
        or "Description" not in quoted_attributes
    ):
        return None, "invalid_info_definition", identifier
    if value_type not in {"Integer", "Float", "Flag", "Character", "String"}:
        return None, "invalid_info_definition", identifier
    if number not in {"A", "R", "G", "."}:
        if re.fullmatch(r"[0-9]+", number) is None:
            return None, "invalid_info_definition", identifier
        number = number.lstrip("0") or "0"
        if len(number) > 10 or (len(number) == 10 and number > str(2**31 - 1)):
            return None, "invalid_info_definition", identifier
    if value_type == "Flag" and number != "0":
        return None, "invalid_info_definition", identifier
    if identifier is None:
        return None, "invalid_info_definition", None
    return InfoFieldDefinition(identifier, number, value_type), None, identifier


def _parse_structured_attributes(
    value: str,
) -> tuple[dict[str, str], frozenset[str]] | None:
    """Split a VCF structured-header body while respecting quoted commas."""

    parts: list[str] = []
    start = 0
    quoted = False
    escaped = False
    for index, character in enumerate(value):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character == ",":
            parts.append(value[start:index])
            start = index + 1
    if quoted or escaped:
        return None
    parts.append(value[start:])

    attributes: dict[str, str] = {}
    quoted_attributes: set[str] = set()
    for part in parts:
        key, separator, raw_value = part.partition("=")
        if not separator or not key or not raw_value or key in attributes:
            return None
        if raw_value.startswith('"'):
            if not raw_value.endswith('"'):
                return None
            decoded = _decode_header_string(raw_value[1:-1])
            if decoded is None:
                return None
            raw_value = decoded
            quoted_attributes.add(key)
        elif '"' in raw_value:
            return None
        attributes[key] = raw_value
    return attributes, frozenset(quoted_attributes)


def _decode_header_string(value: str) -> str | None:
    decoded: list[str] = []
    escaped = False
    for character in value:
        if escaped:
            if character not in {'"', "\\"}:
                return None
            decoded.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            return None
        else:
            decoded.append(character)
    return None if escaped else "".join(decoded)


def register_info_definition(
    line: str,
    definitions: dict[str, InfoFieldDefinition],
    invalid_definitions: set[str],
) -> str | None:
    """Add one schema declaration, invalidating duplicate identifiers."""

    definition, issue, identifier = parse_info_definition(line)
    if issue is not None:
        if identifier:
            definitions.pop(identifier, None)
            invalid_definitions.add(identifier)
        return issue
    if definition is None:
        return "invalid_info_definition"
    identifier = definition.identifier
    if identifier in definitions or identifier in invalid_definitions:
        definitions.pop(identifier, None)
        invalid_definitions.add(identifier)
        return "duplicate_info_definition"
    definitions[identifier] = definition
    return None


def parse_format_definition(
    line: str,
) -> tuple[FormatFieldDefinition | None, str | None, str | None]:
    """Parse the required FORMAT ID/Number/Type schema from a VCF header line."""

    prefix = "##FORMAT=<"
    if not line.startswith(prefix) or not line.endswith(">"):
        return None, "invalid_format_definition", None
    parsed_attributes = _parse_structured_attributes(line[len(prefix) : -1])
    if parsed_attributes is None:
        return None, "invalid_format_definition", None
    attributes, quoted_attributes = parsed_attributes
    identifier = attributes.get("ID")
    number = attributes.get("Number")
    value_type = attributes.get("Type")
    description = attributes.get("Description")
    if (
        not identifier
        or _FORMAT_KEY.fullmatch(identifier) is None
        or not number
        or value_type not in {"Integer", "Float", "Character", "String"}
        or description is None
        or "Description" not in quoted_attributes
    ):
        return None, "invalid_format_definition", identifier
    if number not in {"A", "R", "G", ".", "P", "M", "LA", "LR", "LG"}:
        if re.fullmatch(r"[0-9]+", number) is None:
            return None, "invalid_format_definition", identifier
        number = number.lstrip("0") or "0"
        if number == "0" or len(number) > 10 or (
            len(number) == 10 and number > str(2**31 - 1)
        ):
            return None, "invalid_format_definition", identifier
    if identifier == "GT" and (number != "1" or value_type != "String"):
        return None, "invalid_format_definition", identifier
    return FormatFieldDefinition(identifier, number, value_type), None, identifier


def register_format_definition(
    line: str,
    definitions: dict[str, FormatFieldDefinition],
    invalid_definitions: set[str],
) -> str | None:
    """Add one FORMAT schema declaration, invalidating duplicate identifiers."""

    definition, issue, identifier = parse_format_definition(line)
    if issue is not None:
        if identifier:
            definitions.pop(identifier, None)
            invalid_definitions.add(identifier)
        return issue
    if definition is None:
        return "invalid_format_definition"
    identifier = definition.identifier
    if identifier in definitions or identifier in invalid_definitions:
        definitions.pop(identifier, None)
        invalid_definitions.add(identifier)
        return "duplicate_format_definition"
    definitions[identifier] = definition
    return None


def sample_format_values(
    format_keys: Sequence[str], sample_text: str
) -> dict[str, str]:
    """Map one structurally validated sample cell to its raw FORMAT strings."""

    if sample_text == ".":
        return dict.fromkeys(format_keys, ".")
    values = sample_text.split(":")
    return {
        key: values[index] if index < len(values) else "."
        for index, key in enumerate(format_keys)
    }


def validate_format_values(
    values: Mapping[str, object],
    definitions: Mapping[str, FormatFieldDefinition],
    invalid_definitions: set[str],
    alternate_count: int,
    *,
    typed_values: bool = False,
) -> str | None:
    """Check selected-sample FORMAT types and context-dependent cardinalities.

    VCF text values are lexical strings; BCF values are already decoded into
    native typed scalars/vectors. ``typed_values`` preserves that distinction
    so a numeric BCF payload cannot pass a declared String field merely by
    being stringified during validation.
    """

    if (
        isinstance(alternate_count, bool)
        or not isinstance(alternate_count, int)
        or alternate_count < 0
    ):
        raise ValidationError("alternate_count must be a non-negative integer")
    genotype = values.get("GT")
    ploidy = _genotype_ploidy(genotype)
    local_alternate_indices = _local_alternate_indices(values.get("LAA"), alternate_count)
    if local_alternate_indices is False:
        return "format_number_mismatch"
    local_alternate_count = (
        len(local_alternate_indices)
        if isinstance(local_alternate_indices, tuple)
        else None
    )

    for identifier, value in values.items():
        if identifier in invalid_definitions:
            return "invalid_format_definition"
        definition = definitions.get(identifier)
        if definition is None:
            continue
        if typed_values:
            if value is None:
                continue
            parts = list(value) if isinstance(value, (list, tuple)) else [value]
        else:
            if value is None:
                value = "."
            if not isinstance(value, str):
                return "format_type_mismatch"
            if value == ".":
                continue
            parts = value.split(",")
            if any(not part for part in parts):
                return "format_type_mismatch"
        if identifier == "LAA" and not _valid_local_alternate_indices(
            [_local_index_token(part) for part in parts], alternate_count
        ):
            return "format_number_mismatch"
        if definition.number in {"LA", "LR", "LG"} and local_alternate_count is None:
            return "format_number_mismatch"

        expected_count = _format_value_count(
            definition.number,
            alternate_count=alternate_count,
            ploidy=ploidy,
            local_alternate_count=local_alternate_count,
        )
        if expected_count is not None and len(parts) != expected_count:
            return "format_number_mismatch"
        if not all(
            part is None
            or part == "."
            or _format_item_matches_type(
                part,
                definition.value_type,
                typed_values=typed_values,
            )
            for part in parts
        ):
            return "format_type_mismatch"
    return None


def _genotype_ploidy(genotype: object) -> int | None:
    if not isinstance(genotype, str) or not genotype or genotype == ".":
        return None
    alleles = re.split(r"[/|]", genotype)
    if genotype[0] in "/|" and alleles[0] == "":
        alleles[0] = "."
    if any(not allele for allele in alleles):
        return None
    return len(alleles)


def _local_alternate_indices(value: object, alternate_count: int) -> tuple[int, ...] | bool | None:
    if value is None or value == ".":
        return None
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, int) and not isinstance(value, bool):
        return (value,) if 1 <= value <= alternate_count else False
    elif isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            if isinstance(item, int) and not isinstance(item, bool):
                if not 1 <= item <= alternate_count:
                    return False
                parts.append(str(item))
            elif isinstance(item, str):
                parts.append(item)
            else:
                return False
    else:
        return False
    if not _valid_local_alternate_indices(parts, alternate_count):
        return False
    return tuple(int(part.lstrip("+").lstrip("0")) for part in parts)


def _valid_local_alternate_indices(parts: Sequence[str], alternate_count: int) -> bool:
    if not parts:
        return False
    maximum = str(alternate_count)
    indices: list[str] = []
    for part in parts:
        if _INTEGER_VALUE.fullmatch(part) is None or part.startswith("-"):
            return False
        index = part.lstrip("+").lstrip("0")
        if (
            not index
            or len(index) > len(maximum)
            or (len(index) == len(maximum) and index > maximum)
        ):
            return False
        indices.append(index)
    return len(indices) == len(set(indices))


def _local_index_token(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return value if isinstance(value, str) else ""


def _format_item_matches_type(value: object, value_type: str, *, typed_values: bool) -> bool:
    if not typed_values:
        return isinstance(value, str) and _info_value_matches_type(value, value_type)
    if value_type == "Integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "Float":
        return isinstance(value, float)
    if value_type == "Character":
        return isinstance(value, str) and len(value) == 1
    if value_type == "String":
        return isinstance(value, str)
    return False


def _format_value_count(
    number: str,
    *,
    alternate_count: int,
    ploidy: int | None,
    local_alternate_count: int | None,
) -> int | None:
    if number == "A":
        return alternate_count
    if number == "R":
        return alternate_count + 1
    if number in {"G", "P", "LG"} and ploidy is None:
        return None
    if number == "G":
        return math.comb(alternate_count + ploidy, ploidy)
    if number == "P":
        return ploidy
    if number in {"LA", "LR", "LG"}:
        if local_alternate_count is None:
            return None
        if number == "LA":
            return local_alternate_count
        if number == "LR":
            return local_alternate_count + 1
        return math.comb(local_alternate_count + ploidy, ploidy)
    # Number=M cardinality is defined by base-modification context that this
    # intake does not model. Validate its value type, but leave cardinality to
    # a context-aware modified-base consumer.
    if number in {".", "M"}:
        return None
    return int(number)


def validate_info_values(
    info: dict[str, object],
    definitions: dict[str, InfoFieldDefinition],
    invalid_definitions: set[str],
    alternate_count: int,
) -> str | None:
    """Check declared INFO type and cardinality while preserving source text.

    Unknown (undeclared) INFO fields remain available as lexical provenance.
    Number=G cardinality is not checked because INFO is site-scoped and does
    not identify a single sample ploidy.
    """

    if (
        isinstance(alternate_count, bool)
        or not isinstance(alternate_count, int)
        or alternate_count < 0
    ):
        raise ValidationError("alternate_count must be a non-negative integer")
    for identifier, value in info.items():
        if identifier in invalid_definitions:
            return "invalid_info_definition"
        definition = definitions.get(identifier)
        if definition is None:
            continue
        if definition.value_type == "Flag":
            if value is not True:
                return "info_type_mismatch"
            continue
        if value is True:
            return "info_type_mismatch"
        values = value if isinstance(value, list) else [value]
        if not all(isinstance(item, str) for item in values):
            return "info_type_mismatch"

        expected_count: int | None = None
        if definition.number == "A":
            expected_count = alternate_count
        elif definition.number == "R":
            expected_count = alternate_count + 1
        elif definition.number not in {"G", "."}:
            expected_count = int(definition.number)
        is_missing_scalar = value == "."
        if (
            expected_count is not None
            and not is_missing_scalar
            and len(values) != expected_count
        ):
            return "info_number_mismatch"

        for item in values:
            if item == ".":
                continue
            if not _info_value_matches_type(item, definition.value_type):
                return "info_type_mismatch"
    return None


def _info_value_matches_type(value: str, value_type: str) -> bool:
    if value_type == "String":
        return True
    if value_type == "Character":
        return len(value) == 1
    if value_type == "Integer":
        if _INTEGER_VALUE.fullmatch(value) is None:
            return False
        try:
            number = int(value)
        except ValueError:
            return False
        return -(2**31) + 8 <= number <= 2**31 - 1
    if value_type == "Float":
        return _FLOAT_VALUE.fullmatch(value) is not None
    return False


def called_alternate_indices(
    genotype: object,
    alternate_count: int,
) -> frozenset[int] | None:
    """Return called non-reference ALT indices, or ``None`` when GT is incomplete.

    Indices are one-based, matching VCF/BCF's allele numbering (zero is REF).
    A missing GT, a partially missing call, or a haplotype with any missing
    allele is intentionally non-restrictive so an explicitly retained
    uncalled record remains available for review. A fully reference call
    returns an empty set. Callers decide whether such a record is retained.
    """

    if (
        isinstance(alternate_count, bool)
        or not isinstance(alternate_count, int)
        or alternate_count < 0
    ):
        raise ValidationError("alternate_count must be a non-negative integer")
    if genotype is None:
        return None
    if not isinstance(genotype, str) or not genotype:
        raise ValidationError("GT must be a non-empty string when present")

    alleles = re.split(r"[/|]", genotype)
    if genotype[0] in "/|" and alleles[0] == "":
        # VCF 4.5 permits a leading phase indicator to encode a missing first
        # allele, e.g. /0/1 or |0/1/2.
        alleles[0] = "."
    if any(not allele for allele in alleles):
        raise ValidationError("GT contains an empty allele between phase separators")

    selected: set[int] = set()
    has_missing_allele = False
    maximum_index = str(alternate_count)
    for allele in alleles:
        if allele == ".":
            has_missing_allele = True
            continue
        if any(character < "0" or character > "9" for character in allele):
            raise ValidationError("GT alleles must be non-negative integers or '.'")
        canonical_index = allele.lstrip("0") or "0"
        if len(canonical_index) > len(maximum_index) or (
            len(canonical_index) == len(maximum_index)
            and canonical_index > maximum_index
        ):
            raise ValidationError("GT allele index exceeds the number of ALT alleles")
        index = int(canonical_index)
        if index:
            selected.add(index)

    if has_missing_allele:
        return None
    return frozenset(selected)


def phased_alternate_haplotype_indices(
    genotype: object,
    alternate_count: int,
    alternate_index: int,
) -> tuple[int, ...] | None:
    """Map one VCF ALT index to 1-based haplotypes only for a complete phased GT.

    Slash-separated, haploid-without-a-phase-separator, and partially missing
    calls return ``None`` rather than guessing allele placement. A fully phased
    call that does not carry ``alternate_index`` returns an empty tuple.
    """

    if (
        isinstance(alternate_count, bool)
        or not isinstance(alternate_count, int)
        or alternate_count < 1
    ):
        raise ValidationError("alternate_count must be a positive integer")
    if (
        isinstance(alternate_index, bool)
        or not isinstance(alternate_index, int)
        or not 1 <= alternate_index <= alternate_count
    ):
        raise ValidationError("alternate_index must select one declared ALT allele")
    if genotype is None:
        return None
    if not isinstance(genotype, str) or not genotype:
        raise ValidationError("GT must be non-empty text when present")
    if len(genotype) > _MAX_PHASED_GENOTYPE_TEXT_LENGTH:
        raise ValidationError(
            "GT exceeds the "
            f"{_MAX_PHASED_GENOTYPE_TEXT_LENGTH}-character phased-call limit"
        )

    called = called_alternate_indices(genotype, alternate_count)
    if called is None or "/" in genotype or "|" not in genotype:
        return None
    alleles = genotype.split("|")
    if len(alleles) > _MAX_PHASED_GENOTYPE_PLOIDY:
        raise ValidationError(
            "GT exceeds the "
            f"{_MAX_PHASED_GENOTYPE_PLOIDY}-haplotype phased-call limit"
        )
    return tuple(
        haplotype_index
        for haplotype_index, allele in enumerate(alleles, start=1)
        if int(allele) == alternate_index
    )
