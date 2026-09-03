"""Research-use policy enforcement and bounded claim-language checks."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar

from .errors import PolicyViolation, ValidationError
from .models import (
    AssayType,
    Dossier,
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ExperimentOption,
    Hypothesis,
    HypothesisEdge,
    ReferenceContext,
    ResearchStatus,
    ReviewDecision,
    ReviewState,
    SupportLevel,
)

_HARD_MAX_POLICY_TEXT_ITEMS = 500_000
_HARD_MAX_POLICY_TEXT_CHARACTERS = 65_536
_HARD_MAX_POLICY_TOTAL_CHARACTERS = 33_554_432
_HARD_MAX_POLICY_PATTERN_MATCHES = 100_000
_HARD_MAX_POLICY_STRUCTURED_DEPTH = 64
_HARD_MAX_POLICY_VERSION_CHARACTERS = 128

MAX_POLICY_TEXT_ITEMS = _HARD_MAX_POLICY_TEXT_ITEMS
MAX_POLICY_TEXT_CHARACTERS = _HARD_MAX_POLICY_TEXT_CHARACTERS
MAX_POLICY_TOTAL_CHARACTERS = _HARD_MAX_POLICY_TOTAL_CHARACTERS
MAX_POLICY_PATTERN_MATCHES = _HARD_MAX_POLICY_PATTERN_MATCHES
MAX_POLICY_STRUCTURED_DEPTH = _HARD_MAX_POLICY_STRUCTURED_DEPTH
MAX_POLICY_VERSION_CHARACTERS = _HARD_MAX_POLICY_VERSION_CHARACTERS

_POLICY_WARNING = "All outputs are research-use only and require expert review."
_POLICY_VERSION = "research-boundary-2026.09"
_SUPPORTED_POLICY_VERSIONS = frozenset({"research-boundary-2026.08", _POLICY_VERSION})
_INVALID_TEXT_INPUT = "policy text input must be an iterable of strings"
_UNSAFE_TEXT_INPUT = "policy text input could not be inspected safely"
_MALFORMED_DOSSIER_TEXT = "dossier policy text fields are malformed"
_UNSUPPORTED_TEXT_CHARACTERS = "policy text contains unsupported control characters"
_INVALID_POLICY_LIMITS = "policy limits are invalid"
_T = TypeVar("_T")
_CONFUSABLE_ASCII = str.maketrans(
    {
        "\N{CYRILLIC CAPITAL LETTER A}": "A",
        "\N{CYRILLIC SMALL LETTER A}": "a",
        "\N{CYRILLIC CAPITAL LETTER IE}": "E",
        "\N{CYRILLIC SMALL LETTER IE}": "e",
        "\N{CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I}": "I",
        "\N{CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I}": "i",
        "\N{CYRILLIC CAPITAL LETTER O}": "O",
        "\N{CYRILLIC SMALL LETTER O}": "o",
        "\N{CYRILLIC CAPITAL LETTER ER}": "P",
        "\N{CYRILLIC SMALL LETTER ER}": "p",
        "\N{CYRILLIC CAPITAL LETTER DZE}": "S",
        "\N{CYRILLIC SMALL LETTER DZE}": "s",
        "\N{CYRILLIC CAPITAL LETTER ES}": "C",
        "\N{CYRILLIC SMALL LETTER ES}": "c",
        "\N{CYRILLIC CAPITAL LETTER VE}": "B",
        "\N{CYRILLIC SMALL LETTER VE}": "b",
        "\N{CYRILLIC CAPITAL LETTER EN}": "H",
        "\N{CYRILLIC SMALL LETTER EN}": "h",
        "\N{CYRILLIC CAPITAL LETTER KA}": "K",
        "\N{CYRILLIC SMALL LETTER KA}": "k",
        "\N{CYRILLIC CAPITAL LETTER EM}": "M",
        "\N{CYRILLIC SMALL LETTER EM}": "m",
        "\N{CYRILLIC CAPITAL LETTER TE}": "T",
        "\N{CYRILLIC SMALL LETTER TE}": "t",
        "\N{CYRILLIC CAPITAL LETTER HA}": "X",
        "\N{CYRILLIC SMALL LETTER HA}": "x",
        "\N{GREEK CAPITAL LETTER IOTA}": "I",
        "\N{GREEK SMALL LETTER IOTA}": "i",
        "\N{GREEK CAPITAL LETTER OMICRON}": "O",
        "\N{GREEK SMALL LETTER OMICRON}": "o",
        "\N{GREEK CAPITAL LETTER ALPHA}": "A",
        "\N{GREEK SMALL LETTER ALPHA}": "a",
        "\N{GREEK CAPITAL LETTER BETA}": "B",
        "\N{GREEK SMALL LETTER BETA}": "b",
        "\N{GREEK CAPITAL LETTER EPSILON}": "E",
        "\N{GREEK SMALL LETTER EPSILON}": "e",
        "\N{GREEK CAPITAL LETTER KAPPA}": "K",
        "\N{GREEK SMALL LETTER KAPPA}": "k",
        "\N{GREEK CAPITAL LETTER MU}": "M",
        "\N{GREEK SMALL LETTER MU}": "m",
        "\N{GREEK CAPITAL LETTER NU}": "N",
        "\N{GREEK SMALL LETTER NU}": "n",
        "\N{GREEK CAPITAL LETTER RHO}": "P",
        "\N{GREEK SMALL LETTER RHO}": "p",
        "\N{GREEK CAPITAL LETTER TAU}": "T",
        "\N{GREEK SMALL LETTER TAU}": "t",
        "\N{GREEK CAPITAL LETTER CHI}": "X",
        "\N{GREEK SMALL LETTER CHI}": "x",
    }
)


def _canonicalize_separators(text: str) -> str:
    characters: list[str] = []
    for character in unicodedata.normalize("NFKC", text):
        category = unicodedata.category(character)
        if category in {"Zl", "Zp"}:
            characters.append("\n")
        elif category in {"Pc", "Pd"} or character in "\N{HYPHEN BULLET}\N{MINUS SIGN}":
            characters.append("-")
        elif character in "‘’‛＇":
            characters.append("'")
        elif character in "“”„‟":
            characters.append('"')
        else:
            characters.append(character)
    return "".join(characters)


def _is_default_ignorable(character: str) -> bool:
    """Reject invisible token separators without excluding ordinary combining marks."""

    codepoint = ord(character)
    return (
        codepoint == 0x034F
        or 0x115F <= codepoint <= 0x1160
        or 0x17B4 <= codepoint <= 0x17B5
        or 0x180B <= codepoint <= 0x180F
        or 0x3164 == codepoint
        or 0xFE00 <= codepoint <= 0xFE0F
        or codepoint == 0xFFA0
        or 0x1BCA0 <= codepoint <= 0x1BCA3
        or 0x1D173 <= codepoint <= 0x1D17A
        or 0xE0000 <= codepoint <= 0xE0FFF
    )


def _bounded_positive_integer(value: object, field_name: str, ceiling: int) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field_name} must be an integer")
    if value < 1:
        raise ValidationError(f"{field_name} must be positive")
    if value > ceiling:
        raise ValidationError(f"{field_name} must not exceed the safety ceiling of {ceiling}")
    return value


@dataclass(frozen=True, slots=True)
class PolicyLimits:
    """Hard-ceiling, downward-configurable policy inspection limits."""

    max_text_items: int = MAX_POLICY_TEXT_ITEMS
    max_text_characters: int = MAX_POLICY_TEXT_CHARACTERS
    max_total_characters: int = MAX_POLICY_TOTAL_CHARACTERS
    max_pattern_matches: int = MAX_POLICY_PATTERN_MATCHES

    def __post_init__(self) -> None:
        for field_name, ceiling in (
            ("max_text_items", _HARD_MAX_POLICY_TEXT_ITEMS),
            ("max_text_characters", _HARD_MAX_POLICY_TEXT_CHARACTERS),
            ("max_total_characters", _HARD_MAX_POLICY_TOTAL_CHARACTERS),
            ("max_pattern_matches", _HARD_MAX_POLICY_PATTERN_MATCHES),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_positive_integer(getattr(self, field_name), field_name, ceiling),
            )


DEFAULT_POLICY_LIMITS = PolicyLimits()


def _decision_integrity(
    allowed: bool,
    policy_version: str,
    violations: tuple[str, ...],
    warnings: tuple[str, ...],
) -> str:
    payload = repr((allowed, policy_version, violations, warnings)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Result of applying the product boundary to a payload."""

    allowed: bool
    policy_version: str
    violations: tuple[str, ...]
    warnings: tuple[str, ...]
    _integrity: str = field(init=False, repr=False, compare=False)

    @staticmethod
    def _validate_fields(
        allowed: object,
        policy_version: object,
        violations: object,
        warnings: object,
    ) -> None:
        if type(allowed) is not bool:
            raise ValidationError("policy decision allowed must be a boolean")
        if (
            type(policy_version) is not str
            or len(policy_version) > _HARD_MAX_POLICY_VERSION_CHARACTERS
            or policy_version != _POLICY_VERSION
        ):
            raise ValidationError("policy decision version is invalid")
        for field_name, values in (
            ("violations", violations),
            ("warnings", warnings),
        ):
            if type(values) is not tuple:
                raise ValidationError(f"policy decision {field_name} must be a tuple")
            if len(values) > _HARD_MAX_POLICY_PATTERN_MATCHES:
                raise ValidationError(f"policy decision {field_name} exceeds its safety ceiling")
            for value in values:
                if (
                    type(value) is not str
                    or len(value) > _HARD_MAX_POLICY_TEXT_CHARACTERS
                    or not value
                    or value != value.strip()
                ):
                    raise ValidationError(
                        f"policy decision {field_name} must contain bounded non-empty strings"
                    )
            if len(values) != len(set(values)):
                raise ValidationError(f"policy decision {field_name} must contain unique values")
        if allowed == bool(violations):
            raise ValidationError("policy decision allowed flag disagrees with its violations")
        if warnings != (_POLICY_WARNING,):
            raise ValidationError("policy decision must retain its research-use warning")

    def __post_init__(self) -> None:
        self._validate_fields(
            self.allowed,
            self.policy_version,
            self.violations,
            self.warnings,
        )
        object.__setattr__(
            self,
            "_integrity",
            _decision_integrity(
                self.allowed,
                self.policy_version,
                self.violations,
                self.warnings,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        try:
            allowed = self.allowed
            policy_version = self.policy_version
            violations = self.violations
            warnings = self.warnings
            integrity = self._integrity
        except Exception as exc:  # noqa: BLE001 - reject forged exact instances
            raise ValidationError("policy decision is malformed") from exc
        self._validate_fields(allowed, policy_version, violations, warnings)
        expected_integrity = _decision_integrity(
            allowed,
            policy_version,
            violations,
            warnings,
        )
        if integrity != expected_integrity:
            raise ValidationError("policy decision was mutated after validation")
        return {
            "allowed": allowed,
            "policy_version": policy_version,
            "violations": list(violations),
            "warnings": list(warnings),
        }


class _MalformedDossierText(ValueError):
    """Keep malformed direct-object failures inside the policy boundary."""


class ResearchPolicy:
    """Enforce a bounded research-only boundary before output is released."""

    version = _POLICY_VERSION
    supported_versions = _SUPPORTED_POLICY_VERSIONS

    _blocked_patterns = (
        (
            re.compile(
                r"\b(?:(?:re|mis)?diagnos(?:e|ed|es|ing|is|tic|tics|tically)|"
                r"d\s*i\s*a\s*g\s*n\s*o\s*s\s*i\s*s)\b",
                re.IGNORECASE,
            ),
            "diagnostic claim",
        ),
        (
            re.compile(
                r"\b(?:"
                r"(?:treat(?:ment)?|therap(?:y|eutic)|chemotherapy|radiotherapy|"
                r"immunotherapy|temozolomide|medication|regimen|surgery|intervention)"
                r"[-_\s]+"
                r"recommend(?:ation|ations|ed|ing|s)?"
                r"|recommend(?:ation|ations|ed|ing|s)?[-_\s]+"
                r"(?:(?:a|no)[-_\s]+)?(?:treat(?:ment)?|therap(?:y|eutic)|"
                r"chemotherapy|radiotherapy|immunotherapy|temozolomide|medication|"
                r"regimen|surgery|intervention)"
                r"|(?:treat(?:ment)?|therap(?:y|eutic)|chemotherapy|radiotherapy|"
                r"immunotherapy|temozolomide|medication|regimen|surgery|intervention)"
                r"[-_\s]+(?:is|was|may[-_\s]+be|should[-_\s]+be|must[-_\s]+be)"
                r"[-_\s]+recommend(?:ed|ing|s)?"
                r")\b",
                re.IGNORECASE,
            ),
            "treatment recommendation",
        ),
        (
            re.compile(r"\b(?:non[-_\s]*)?pathogenic(?:ity)?\b", re.IGNORECASE),
            "pathogenicity claim",
        ),
        (
            re.compile(
                r"\b(?:trial[-_\s]+(?:in)?eligib(?:le|ility)|"
                r"(?:in)?eligib(?:le|ility)[-_\s]+(?:for[-_\s]+)?(?:a[-_\s]+)?"
                r"(?:clinical[-_\s]+)?trial)\b",
                re.IGNORECASE,
            ),
            "trial eligibility claim",
        ),
        (
            re.compile(
                r"\b(?:clinically[-_\s]+actionable|clinical[-_\s]+actionability)\b",
                re.IGNORECASE,
            ),
            "clinical actionability claim",
        ),
        (
            re.compile(r"\bpatient[-_\s]+specific\b", re.IGNORECASE),
            "patient-specific claim",
        ),
    )
    _clause_boundary = re.compile(
        r"(?:[.!?;:\r\n。！？；：]+|\b(?:but|however|yet|nevertheless|"
        r"although|though|whereas|except|excepting|unless)\b)",
        re.IGNORECASE,
    )
    _non_assertive_prefixes = (
        re.compile(
            r"(?:\b(?:no|not(?!\s+only\b)|never|without)\s+"
            r"(?:(?:a|an|the|any|clear|clinical|confirmed|definitive|established|"
            r"supported|validated)\s+){0,4}|"
            r"\b(?:(?:am|is|are|was|were)\s+)?unable\s+to\s+|"
            r"\b(?:cannot|can't|(?:do|does|did|can|could|will|would|should|must|"
            r"may|might)\s+not)\s+|\bnon[-_\s]*)[\"']?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:"
            r"(?:do|does|did|can|could|will|would|should|must|may|might)\s+not|"
            r"cannot|can't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|"
            r"won't|wouldn't|shouldn't|mustn't"
            r")\s+(?:"
            r"provide|make|offer|constitute|establish|support|perform|claim|"
            r"determine|assess|infer|recommend|represent|produce|return|assign|"
            r"classify|validate|evaluate|diagnose|conclude|be(?:\s+used)?"
            r")\b(?P<tail>[^.!?;:\r\n]{0,160})$",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:uncertain|unknown|unresolved|undetermined|unassessed|unsupported)"
            r"(?:\s+(?:whether|if|as\s+to))?\s+(?:a|an|the)?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"\binsufficient\s+(?:evidence|support|validation)\b"
            r"[^.!?;:\r\n]{0,80}(?:for|to\s+(?:establish|determine|support|validate))"
            r"\s+(?:a|an|the)?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:fails?|failed|unable)\s+to\s+"
            r"(?:establish|determine|assess|support|validate)\s+(?:a|an|the)?\s*$",
            re.IGNORECASE,
        ),
    )
    _non_assertive_suffix = re.compile(
        r"^\s*[\"']?\s*(?:"
        r"performance\s+(?:is|was|has\s+been)\s+"
        r"(?:measured|evaluated|assessed|characterized)\b|"
        r"(?:(?:claims?|inferences?|status|use|uses|conclusions?|determinations?|"
        r"assessments?|interpretations?|findings?|classifications?|performance)"
        r"\s+)?(?:"
        r"(?:testing|assessment|classification|evidence)\s+"
        r"(?:is|are|was|were|remain|remains)\s+"
        r"(?:(?:currently|presently|still|yet)\s+)?"
        r"(?:inconclusive|pending|uncertain|unknown|unresolved|undetermined|"
        r"unassessed|unsupported)\b|"
        r"(?:is|are|was|were|remain|remains)\s+"
        r"(?:(?:currently|presently|still|yet)\s+)?(?:"
        r"(?:not|never)\s+(?:established|evaluated|assessed|determined|supported|"
        r"validated|provided|made|intended|claimed|recommended|permitted|known)\b|"
        r"unknown\b|uncertain\b|unresolved\b|undetermined\b|"
        r"unassessed\b|unsupported\b|prohibited\b|excluded\b|disallowed\b|"
        r"outside\s+(?:the\s+)?scope\b"
        r")|(?:has|have|had)\s+not\s+"
        r"(?:(?:yet|currently|previously)\s+)?(?:been\s+)?(?:"
        r"established|evaluated|assessed|determined|supported|validated|provided"
        r")\b|(?:cannot|can't|could\s+not|should\s+not|must\s+not)\s+"
        r"(?:(?:currently|presently|yet|reliably)\s+)?be\s+"
        r"(?:established|evaluated|assessed|determined|supported|validated|provided|made)"
        r"\b|(?:should|must)\s+not\s+be\s+(?:followed|used|adopted|applied)\b|"
        r"(?:lack|lacks)\s+(?:evidence|support|validation)\b"
        r"))",
        re.IGNORECASE,
    )
    _meta_disclaimer_suffix = re.compile(
        r"^\s*[\"']?\s*(?:(?:claims?|inferences?|conclusions?|determinations?|"
        r"assessments?|interpretations?|findings?|classifications?)\s+)?"
        r"(?:is|are|was|were)\s+(?:not\s+)?(?:made|provided|offered|returned|"
        r"assigned|established|supported|validated)\b",
        re.IGNORECASE,
    )
    _negated_subject_suffix = re.compile(
        r"^\s*[\"']?\s*(?:can|could|should|would|must)\s+(?:not\s+)?be\s+"
        r"(?:made|provided|offered|returned|assigned|established|supported|"
        r"validated|determined|inferred|recommended)\b",
        re.IGNORECASE,
    )
    _safe_governed_tail = re.compile(
        r"^(?:[\s,\"'()/+\-]+|\b(?:a|an|the|any|clear|clinical|confirmed|"
        r"definitive|established|supported|validated|diagnos(?:e|ed|es|ing|is|tic|"
        r"tics|tically)|treat(?:ment)?|therap(?:y|eutic)|recommend(?:ation|ations|"
        r"ed|ing|s)?|pathogenic(?:ity)?|trial|(?:in)?eligib(?:le|ility)|clinically|"
        r"actionable|actionability|patient|specific|claims?|inferences?|conclusions?|"
        r"determinations?|assessments?|interpretations?|classifications?|or|and|nor)"
        r"\b)*$",
        re.IGNORECASE,
    )
    _assignment_suffix = re.compile(r"^\s*[\"']?\s*(?::|=)\s*\S")
    _assertive_suffix = re.compile(
        r"^\s*[\"']?\s*(?:is|are|was|were|means?|indicates?|confirms?|shows?|"
        r"supports?|favou?rs?|favou?red|favou?ring)\s+"
        r"(?!(?:not|never|unknown|uncertain|unresolved|undetermined|unassessed|"
        r"unsupported|prohibited|excluded|disallowed|outside)\b)\S",
        re.IGNORECASE,
    )
    _assertive_bridge = re.compile(
        r"\b(?:conclud(?:e|ed|es|ing)|assert(?:ed|s|ing)?|confirm(?:ed|s|ing)?|"
        r"find(?:s|ing)?|found|show(?:ed|s|ing)?|indicat(?:e|ed|es|ing)|"
        r"classif(?:y|ied|ies|ying)|declar(?:e|ed|es|ing)|assign(?:ed|s|ing)?|"
        r"favou?r(?:s|ed|ing)?|advis(?:e|ed|es|ing)|suggest(?:ed|s|ing)?|"
        r"likely|probably|presumably|apparently|"
        r"but|however|yet|nevertheless|nonetheless|actually|instead|except|"
        r"excepting|unless|although|though|whereas|"
        r"(?:it|this|that)\s+(?:(?:is|are|was|were)\s+"
        r"(?!(?:not|never|unknown|uncertain|unresolved|undetermined|unassessed|"
        r"unsupported)\b)\S+|means?|indicates?|shows?))\b",
        re.IGNORECASE,
    )
    _assertive_remainder = re.compile(r"(?::|=)\s*\S")

    @classmethod
    def _has_assertive_continuation(cls, text: str) -> bool:
        return (
            cls._assertive_bridge.search(text) is not None
            or cls._assertive_remainder.search(text) is not None
        )

    def __init__(self, *, limits: PolicyLimits | None = None) -> None:
        selected = DEFAULT_POLICY_LIMITS if limits is None else limits
        if type(selected) is not PolicyLimits:
            raise ValidationError("limits must be PolicyLimits")
        try:
            max_text_items = selected.max_text_items
            max_text_characters = selected.max_text_characters
            max_total_characters = selected.max_total_characters
            max_pattern_matches = selected.max_pattern_matches
        except Exception as exc:  # noqa: BLE001 - reject forged exact instances
            raise ValidationError("limits must be a valid PolicyLimits") from exc
        self.limits = PolicyLimits(
            max_text_items=max_text_items,
            max_text_characters=max_text_characters,
            max_total_characters=max_total_characters,
            max_pattern_matches=max_pattern_matches,
        )

    def _limit_snapshot(self) -> PolicyLimits | None:
        try:
            selected = self.limits
            if type(selected) is not PolicyLimits:
                return None
            return PolicyLimits(
                max_text_items=selected.max_text_items,
                max_text_characters=selected.max_text_characters,
                max_total_characters=selected.max_total_characters,
                max_pattern_matches=selected.max_pattern_matches,
            )
        except Exception:  # noqa: BLE001 - public state may be forged after construction
            return None

    @staticmethod
    def _append_unique(violations: list[str], violation: str) -> None:
        if violation not in violations:
            violations.append(violation)

    def _decision(self, violations: Iterable[str]) -> PolicyDecision:
        unique = tuple(dict.fromkeys(violations))
        return PolicyDecision(
            allowed=not unique,
            policy_version=_POLICY_VERSION,
            violations=unique,
            warnings=(_POLICY_WARNING,),
        )

    @staticmethod
    def _normalize_text(text: str) -> tuple[str, ...] | None:
        normalized = _canonicalize_separators(text)
        if any(
            (unicodedata.category(character).startswith("C") and character not in "\t\n\r")
            or _is_default_ignorable(character)
            for candidate in (text, normalized)
            for character in candidate
        ):
            return None
        collapsed: list[str] = []
        spaced: list[str] = []
        for index, source_character in enumerate(text):
            category = unicodedata.category(source_character)
            previous_is_word = index > 0 and text[index - 1].isalnum()
            next_is_word = index + 1 < len(text) and text[index + 1].isalnum()
            suspicious_separator = (
                (category == "Zs" and source_character != " ")
                or category in {"Pc", "Pd"}
                or source_character in "\N{BRAILLE PATTERN BLANK}/\\|\N{MIDDLE DOT}"
                or (category.startswith("S") and previous_is_word and next_is_word)
                or (
                    category.startswith("P")
                    and source_character not in "'‘’‛＇"
                    and previous_is_word
                    and next_is_word
                )
            )
            if category.startswith("M"):
                continue
            if suspicious_separator:
                spaced.append(" ")
                continue
            security_character = source_character.translate(_CONFUSABLE_ASCII)
            decomposed = unicodedata.normalize("NFKD", security_character)
            canonical = _canonicalize_separators(
                "".join(
                    character
                    for character in decomposed
                    if not unicodedata.category(character).startswith("M")
                )
            )
            collapsed.append(canonical)
            spaced.append(canonical)
        return tuple(dict.fromkeys((normalized, "".join(collapsed), "".join(spaced))))

    @classmethod
    def _is_non_assertive_context(
        cls,
        text: str,
        match: re.Match[str],
        label: str,
    ) -> bool:
        """Allow explicit scope, negation, and uncertainty around a matched term."""

        context_start = max(0, match.start() - 256)
        prefix = cls._clause_boundary.split(text[context_start : match.start()])[-1]
        following = text[match.end() : match.end() + 256]
        if cls._assignment_suffix.match(following) is not None:
            return False
        suffix_match = cls._non_assertive_suffix.match(following)
        if suffix_match is not None and not cls._has_assertive_continuation(
            following[suffix_match.end() :]
        ):
            return True
        direct_negation = cls._non_assertive_prefixes[0].search(prefix)
        if direct_negation is not None:
            direct_text = direct_negation.group(0).casefold().strip(" \t\r\n\"'")
            matched_text = match.group(0).casefold()
            has_assertive_continuation = cls._has_assertive_continuation(following)
            if direct_text.startswith("non") and label == "diagnostic claim":
                return not has_assertive_continuation
            if (
                label == "diagnostic claim"
                and any(item in direct_text for item in ("not", "cannot", "can't", "unable"))
                and "diagnos" in matched_text
            ):
                return not has_assertive_continuation
            if (
                label == "treatment recommendation"
                and any(item in direct_text for item in ("not", "cannot", "can't"))
                and matched_text.startswith("recommend")
            ):
                return not has_assertive_continuation
            if (
                direct_text.startswith("no")
                and cls._negated_subject_suffix.match(following) is not None
            ):
                return not has_assertive_continuation
            disclaimer = cls._meta_disclaimer_suffix.match(following)
            return disclaimer is not None and not cls._has_assertive_continuation(
                following[disclaimer.end() :]
            )
        if cls._assertive_suffix.match(following) is not None:
            return False
        governed = cls._non_assertive_prefixes[1].search(prefix)
        if (
            governed is not None
            and cls._safe_governed_tail.fullmatch(governed.group("tail")) is not None
            and cls._assertive_bridge.search(governed.group("tail")) is None
        ):
            return True
        if any(pattern.search(prefix) is not None for pattern in cls._non_assertive_prefixes[2:]):
            return True

        return False

    def inspect_texts(self, texts: Iterable[str]) -> PolicyDecision:
        """Inspect a bounded iterable without coercing or exhaustively consuming it."""

        violations: list[str] = []
        matched_labels: set[str] = set()
        limits = self._limit_snapshot()
        if limits is None:
            return self._decision((_INVALID_POLICY_LIMITS,))
        if isinstance(texts, (str, bytes, bytearray, Mapping)):
            return self._decision((_INVALID_TEXT_INPUT,))
        try:
            iterator = iter(texts)
        except TypeError:
            return self._decision((_INVALID_TEXT_INPUT,))
        except Exception:  # noqa: BLE001 - a policy boundary must fail closed
            return self._decision((_UNSAFE_TEXT_INPUT,))

        total_characters = 0
        pattern_matches = 0
        matching_exhausted = False
        for index in range(limits.max_text_items + 1):
            try:
                text = next(iterator)
            except StopIteration:
                break
            except _MalformedDossierText:
                self._append_unique(violations, _MALFORMED_DOSSIER_TEXT)
                break
            except Exception:  # noqa: BLE001 - a policy boundary must fail closed
                self._append_unique(violations, _UNSAFE_TEXT_INPUT)
                break

            if index == limits.max_text_items:
                self._append_unique(
                    violations,
                    "policy text input exceeds the configured maximum of "
                    f"{limits.max_text_items} items",
                )
                break
            if type(text) is not str:
                self._append_unique(violations, _INVALID_TEXT_INPUT)
                break
            if len(text) > limits.max_text_characters:
                self._append_unique(
                    violations,
                    "policy text exceeds the configured maximum of "
                    f"{limits.max_text_characters} characters",
                )
                break
            normalized_variants = self._normalize_text(text)
            if normalized_variants is None:
                self._append_unique(violations, _UNSUPPORTED_TEXT_CHARACTERS)
                break
            normalized = normalized_variants[0]
            if any(
                len(candidate) > limits.max_text_characters for candidate in normalized_variants
            ):
                self._append_unique(
                    violations,
                    "normalized policy text exceeds the configured maximum of "
                    f"{limits.max_text_characters} characters",
                )
                break
            inspected_characters = sum(len(candidate) for candidate in normalized_variants)
            if inspected_characters > limits.max_total_characters - total_characters:
                self._append_unique(
                    violations,
                    "policy text input exceeds the configured maximum of "
                    f"{limits.max_total_characters} total characters",
                )
                break
            total_characters += inspected_characters
            if not normalized:
                continue

            for candidate in normalized_variants:
                for pattern, label in _CANONICAL_BLOCKED_PATTERNS:
                    if label in matched_labels:
                        continue
                    for match in pattern.finditer(candidate):
                        pattern_matches += 1
                        if pattern_matches > limits.max_pattern_matches:
                            self._append_unique(
                                violations,
                                "policy pattern matching exceeds the configured maximum of "
                                f"{limits.max_pattern_matches} candidates",
                            )
                            matching_exhausted = True
                            break
                        if not self._is_non_assertive_context(candidate, match, label):
                            matched_labels.add(label)
                            break
                    if matching_exhausted:
                        break
                if matching_exhausted:
                    break
            if matching_exhausted:
                break
        ordered_claim_violations = (
            label for _, label in _CANONICAL_BLOCKED_PATTERNS if label in matched_labels
        )
        return self._decision((*ordered_claim_violations, *violations))

    def enforce_texts(self, texts: Iterable[str]) -> PolicyDecision:
        decision = self.inspect_texts(texts)
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.violations))
        return decision

    @staticmethod
    def _typed_items(
        value: object,
        expected_type: type[_T],
    ) -> Iterator[_T]:
        if type(value) is not tuple:
            raise _MalformedDossierText
        for item in value:
            if type(item) is not expected_type:
                raise _MalformedDossierText
            yield item

    @staticmethod
    def _string_items(value: object) -> Iterator[str]:
        if type(value) is not tuple:
            raise _MalformedDossierText
        for item in value:
            if type(item) is not str:
                raise _MalformedDossierText
            yield item

    @staticmethod
    def _text(value: object) -> str:
        if type(value) is not str:
            raise _MalformedDossierText
        return value

    @staticmethod
    def _enum_text(value: object, expected_type: type[Enum]) -> str:
        if type(value) is not expected_type or type(value.value) is not str:
            raise _MalformedDossierText
        return value.value

    def _context_texts(self, context: object) -> Iterator[str]:
        if type(context) is not ReferenceContext:
            raise _MalformedDossierText
        yield ""
        for value in (
            context.genome_build,
            context.disease_class,
            context.age_group,
            context.cell_state,
            context.territory,
            context.treatment_phase,
            context.source_version,
        ):
            yield self._text(value)
        yield from self._string_items(context.assay_support)

    def _json_texts(
        self,
        value: object,
        *,
        depth: int = 0,
        active: set[int] | None = None,
    ) -> Iterator[str]:
        """Walk canonical JSON lazily, charging containers, keys, and scalar values."""

        if depth > _HARD_MAX_POLICY_STRUCTURED_DEPTH:
            raise _MalformedDossierText
        if type(value) is str:
            yield value
            return
        if value is None or type(value) in {bool, int, float}:
            yield ""
            return
        if not isinstance(value, (Mapping, list, tuple)):
            raise _MalformedDossierText

        seen = set() if active is None else active
        marker = id(value)
        if marker in seen:
            raise _MalformedDossierText
        seen.add(marker)
        try:
            yield ""
            if isinstance(value, Mapping):
                try:
                    for key, item in value.items():
                        yield self._text(key)
                        yield from self._json_texts(
                            item,
                            depth=depth + 1,
                            active=seen,
                        )
                except _MalformedDossierText:
                    raise
                except Exception as exc:  # noqa: BLE001 - hostile direct objects
                    raise _MalformedDossierText from exc
            else:
                try:
                    for item in value:
                        yield from self._json_texts(
                            item,
                            depth=depth + 1,
                            active=seen,
                        )
                except _MalformedDossierText:
                    raise
                except Exception as exc:  # noqa: BLE001 - hostile direct objects
                    raise _MalformedDossierText from exc
        finally:
            seen.remove(marker)

    def _dossier_texts(self, dossier: Dossier) -> Iterator[str]:
        """Yield every serialized dossier string lazily through shared work limits."""

        yield ""
        for value in (
            dossier.dossier_id,
            dossier.case_id,
            dossier.run_id,
            dossier.created_at,
            dossier.input_address,
            dossier.policy_version,
            dossier.event_head,
            dossier.content_address,
        ):
            yield self._text(value)
        yield self._enum_text(dossier.status, ResearchStatus)
        for hypothesis in self._typed_items(dossier.hypotheses, Hypothesis):
            yield ""
            for value in (
                hypothesis.hypothesis_id,
                hypothesis.variant_id,
                hypothesis.element_id,
                hypothesis.gene_id,
                hypothesis.state_id,
                hypothesis.mechanism,
            ):
                yield self._text(value)
            yield from self._context_texts(hypothesis.context)
            yield self._enum_text(hypothesis.status, ResearchStatus)
            yield from self._string_items(hypothesis.missing_evidence)
            yield from self._string_items(hypothesis.negative_evidence)
            yield from self._string_items(hypothesis.alternatives)
            yield from self._string_items(hypothesis.provenance)
            for edge in self._typed_items(hypothesis.edges, HypothesisEdge):
                yield ""
                yield self._text(edge.edge_id)
                yield self._enum_text(edge.edge_type, EdgeType)
                yield self._text(edge.source_id)
                yield self._text(edge.target_id)
                yield from self._string_items(edge.claim_ids)
                yield self._enum_text(edge.support_level, SupportLevel)
                yield from self._string_items(edge.alternatives)
        for claim in self._typed_items(dossier.evidence, EvidenceClaim):
            yield ""
            for value in (
                claim.evidence_id,
                claim.edge_id,
                claim.source_id,
                claim.channel,
                claim.summary,
                claim.produced_by,
                claim.created_at,
            ):
                yield self._text(value)
            yield self._enum_text(claim.state, EvidenceState)
            yield self._enum_text(claim.tier, EvidenceTier)
            yield from self._context_texts(claim.context)
            if not isinstance(claim.payload, Mapping):
                raise _MalformedDossierText
            yield from self._json_texts(claim.payload)
            yield from self._string_items(claim.depends_on)
            if claim.supersedes is not None:
                yield self._text(claim.supersedes)
        for option in self._typed_items(dossier.experiments, ExperimentOption):
            yield ""
            yield self._text(option.option_id)
            yield self._enum_text(option.assay, AssayType)
            yield from self._string_items(option.tests_edges)
            yield self._text(option.cost_class)
            yield from self._string_items(option.required_context)
            yield from self._string_items(option.controls)
            yield from self._string_items(option.readouts)
            yield from self._string_items(option.limitations)
        if dossier.review is not None:
            if type(dossier.review) is not ReviewDecision:
                raise _MalformedDossierText
            yield ""
            for value in (
                dossier.review.review_id,
                dossier.review.case_id,
                dossier.review.reviewer,
                dossier.review.rationale,
                dossier.review.created_at,
            ):
                yield self._text(value)
            yield self._enum_text(dossier.review.state, ReviewState)
            yield from self._string_items(dossier.review.reviewed_hypothesis_ids)
            yield from self._string_items(dossier.review.checked_claim_ids)
        yield from self._string_items(dossier.warnings)
        if type(dossier.source_receipts) is not tuple:
            raise _MalformedDossierText
        for receipt in dossier.source_receipts:
            if not isinstance(receipt, Mapping):
                raise _MalformedDossierText
            yield from self._json_texts(receipt)
        yield from self._string_items(dossier.source_bundle_addresses)

    def validate_dossier(self, dossier: Dossier) -> PolicyDecision:
        """Validate release semantics and every human-facing dossier text surface."""

        if type(dossier) is not Dossier:
            return self._decision(("dossier must be a Dossier",))

        try:
            research_use_only = dossier.research_use_only
            policy_version = dossier.policy_version
            status = dossier.status
            review = dossier.review
        except Exception:  # noqa: BLE001 - forged exact instances must fail closed
            return self._decision((_MALFORMED_DOSSIER_TEXT,))

        decision = self.inspect_texts(self._dossier_texts(dossier))
        violations = list(decision.violations)
        if decision.allowed:
            try:
                dossier._validate_structure()
            except Exception:  # noqa: BLE001 - policy validation must fail closed
                self._append_unique(violations, "dossier structure is invalid")
        if research_use_only is not True:
            self._append_unique(violations, "research-use flag missing")
        if (
            type(policy_version) is not str
            or not policy_version
            or len(policy_version) > MAX_POLICY_VERSION_CHARACTERS
        ):
            self._append_unique(violations, "dossier policy version is invalid")
        elif policy_version != policy_version.strip():
            self._append_unique(violations, "dossier policy version is invalid")
        elif policy_version not in _SUPPORTED_POLICY_VERSIONS:
            self._append_unique(violations, "dossier policy version is unsupported")

        status_is_valid = type(status) is ResearchStatus
        if not status_is_valid:
            self._append_unique(violations, "dossier research status is invalid")
        review_is_valid = review is None or type(review) is ReviewDecision
        if not review_is_valid:
            self._append_unique(violations, "dossier review decision is invalid")
        review_state: object = None
        if type(review) is ReviewDecision:
            try:
                review_state = review.state
            except Exception:  # noqa: BLE001 - forged exact instances must fail closed
                self._append_unique(violations, _MALFORMED_DOSSIER_TEXT)
            if type(review_state) is not ReviewState:
                self._append_unique(violations, "dossier review state is invalid")

        if status_is_valid and status is ResearchStatus.REVIEWED and review is None:
            self._append_unique(violations, "reviewed dossier has no review decision")
        if status_is_valid and status is ResearchStatus.RELEASED_RESEARCH:
            if review is None:
                self._append_unique(violations, "released dossier has no review decision")
            elif type(review) is not ReviewDecision or review_state is not ReviewState.ACCEPTED:
                self._append_unique(
                    violations,
                    "released dossier review decision is not accepted",
                )
        if (
            status_is_valid
            and status is not ResearchStatus.RELEASED_RESEARCH
            and review_state is ReviewState.ACCEPTED
        ):
            self._append_unique(
                violations,
                "accepted review is attached to a non-released dossier status",
            )
        return self._decision(violations)


_CANONICAL_BLOCKED_PATTERNS = ResearchPolicy._blocked_patterns
