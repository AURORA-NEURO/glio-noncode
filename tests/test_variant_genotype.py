from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.variant_genotype import (
    FormatFieldDefinition,
    InfoFieldDefinition,
    called_alternate_indices,
    format_key_issue,
    has_duplicate_format_keys,
    has_duplicate_sample_ids,
    parse_format_definition,
    parse_info_definition,
    parse_info_fields,
    phased_alternate_haplotype_indices,
    register_format_definition,
    register_info_definition,
    sample_format_values,
    sample_value_issue,
    validate_format_values,
    validate_info_values,
)


class CalledAlternateIndicesTests(unittest.TestCase):
    def test_complete_calls_select_only_nonreference_alt_indices(self) -> None:
        cases = (
            ("0/2", 2, frozenset({2})),
            ("1|2", 2, frozenset({1, 2})),
            ("2", 2, frozenset({2})),
            ("0/0/2", 2, frozenset({2})),
            ("0002/0", 2, frozenset({2})),
            ("0/0", 2, frozenset()),
        )
        for genotype, alternate_count, expected in cases:
            with self.subTest(genotype=genotype):
                self.assertEqual(
                    called_alternate_indices(genotype, alternate_count),
                    expected,
                )

    def test_missing_or_partially_missing_calls_are_non_restrictive(self) -> None:
        for genotype in (None, ".", "./1", "|0/1/2", "/0/1"):
            with self.subTest(genotype=genotype):
                self.assertIsNone(called_alternate_indices(genotype, 2))

    def test_invalid_alleles_and_out_of_range_indices_are_rejected(self) -> None:
        for genotype in ("", "0/", "0//1", "0/x", "0/3", "0/999999999999999999999"):
            with self.subTest(genotype=genotype):
                with self.assertRaises(ValidationError):
                    called_alternate_indices(genotype, 2)

    def test_alternate_count_must_be_a_nonnegative_integer(self) -> None:
        for alternate_count in (-1, True, 1.5):
            with self.subTest(alternate_count=alternate_count):
                with self.assertRaises(ValidationError):
                    called_alternate_indices("0/1", alternate_count)  # type: ignore[arg-type]


class PhasedAlternateHaplotypeIndicesTests(unittest.TestCase):
    def test_complete_pipe_phased_calls_map_alt_copies_to_one_based_haplotypes(self) -> None:
        cases = (
            ("0|1", 1, (2,)),
            ("1|1", 1, (1, 2)),
            ("0|2", 1, ()),
            ("0002|0|1", 2, (1,)),
            ("0|1|2", 2, (3,)),
        )
        for genotype, alternate_index, expected in cases:
            with self.subTest(genotype=genotype, alternate_index=alternate_index):
                self.assertEqual(
                    phased_alternate_haplotype_indices(
                        genotype,
                        alternate_count=2,
                        alternate_index=alternate_index,
                    ),
                    expected,
                )

    def test_unphased_haploid_and_incomplete_calls_do_not_assign_haplotypes(self) -> None:
        for genotype in (None, ".", "0/1", "0|.", "1"):
            with self.subTest(genotype=genotype):
                self.assertIsNone(
                    phased_alternate_haplotype_indices(
                        genotype,
                        alternate_count=1,
                        alternate_index=1,
                    )
                )

    def test_invalid_alt_indices_calls_and_resource_sizes_are_rejected(self) -> None:
        for alternate_count, alternate_index in ((0, 1), (2, 0), (2, 3), (True, 1)):
            with self.subTest(alternate_count=alternate_count, alternate_index=alternate_index):
                with self.assertRaises(ValidationError):
                    phased_alternate_haplotype_indices(
                        "0|1",
                        alternate_count=alternate_count,  # type: ignore[arg-type]
                        alternate_index=alternate_index,
                    )
        for genotype in ("0|3", "0||1"):
            with self.subTest(genotype=genotype):
                with self.assertRaises(ValidationError):
                    phased_alternate_haplotype_indices(genotype, 2, 1)
        with self.assertRaisesRegex(ValidationError, "character phased-call limit"):
            phased_alternate_haplotype_indices("0|" * 257 + "0", 1, 1)
        with self.assertRaisesRegex(ValidationError, "haplotype phased-call limit"):
            phased_alternate_haplotype_indices("0|" * 32 + "0", 1, 1)


class DuplicateSampleIdTests(unittest.TestCase):
    def test_unique_and_repeated_header_sample_ids(self) -> None:
        self.assertFalse(has_duplicate_sample_ids(()))
        self.assertFalse(has_duplicate_sample_ids(("S1", "S2")))
        self.assertTrue(has_duplicate_sample_ids(("S1", "S1")))

    def test_unique_and_repeated_format_keys(self) -> None:
        self.assertFalse(has_duplicate_format_keys(()))
        self.assertFalse(has_duplicate_format_keys(("GT", "DP")))
        self.assertTrue(has_duplicate_format_keys(("GT", "GT")))

    def test_format_key_issue_codes_cover_duplicate_syntax_and_genotype_order(self) -> None:
        cases = (
            (("GT", "GT"), "duplicate_format_key"),
            (("GT", "DP+"), "invalid_format_key"),
            (("DP", "GT"), "genotype_format_key_not_first"),
            (("GT", "DP"), None),
            ((), None),
        )
        for format_keys, expected in cases:
            with self.subTest(format_keys=format_keys):
                self.assertEqual(format_key_issue(format_keys), expected)

    def test_sample_value_issue_distinguishes_missing_and_excess_fields(self) -> None:
        cases = (
            (("GT", "DP"), ".", None),
            (("GT", "DP"), "0/1", None),
            (("GT", "DP", "GQ"), "0/1:8", None),
            (("GT",), "0/1:8", "sample_data_excess_fields"),
            (("GT", "DP", "GQ"), "0/1::5", "sample_data_empty_field"),
            (("GT", "DP"), "0/1:", "sample_data_empty_field"),
            (("GT", "DP"), ":", "sample_data_empty_field"),
            (("GT",), "", "sample_data_missing"),
            ((), ".", None),
        )
        for format_keys, sample_text, expected in cases:
            with self.subTest(format_keys=format_keys, sample_text=sample_text):
                self.assertEqual(sample_value_issue(format_keys, sample_text), expected)


class FormatFieldValidationTests(unittest.TestCase):
    def test_format_definition_and_duplicate_registry(self) -> None:
        line = '##FORMAT=<Description="likelihoods, per genotype",Type=Integer,Number=G,ID=PL>'
        definition, issue, identifier = parse_format_definition(line)
        self.assertIsNone(issue)
        self.assertEqual(identifier, "PL")
        self.assertEqual(definition, FormatFieldDefinition("PL", "G", "Integer"))

        definitions: dict[str, FormatFieldDefinition] = {}
        invalid: set[str] = set()
        first = '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="depth">'
        second = '##FORMAT=<ID=DP,Number=1,Type=Float,Description="depth">'
        self.assertIsNone(register_format_definition(first, definitions, invalid))
        self.assertEqual(
            register_format_definition(second, definitions, invalid),
            "duplicate_format_definition",
        )
        self.assertEqual(definitions, {})
        self.assertEqual(invalid, {"DP"})

    def test_format_definition_rejects_invalid_gt_and_nonpositive_counts(self) -> None:
        for line in (
            '##FORMAT=<ID=GT,Number=2,Type=String,Description="genotype">',
            '##FORMAT=<ID=GT,Number=1,Type=Integer,Description="genotype">',
            '##FORMAT=<ID=DP,Number=0,Type=Integer,Description="depth">',
            '##FORMAT=<ID=DP,Number=1,Type=Flag,Description="depth">',
        ):
            with self.subTest(line=line):
                definition, issue, _ = parse_format_definition(line)
                self.assertIsNone(definition)
                self.assertEqual(issue, "invalid_format_definition")

    def test_format_values_check_types_cardinalities_and_genotype_context(self) -> None:
        definitions = {
            "GT": FormatFieldDefinition("GT", "1", "String"),
            "AD": FormatFieldDefinition("AD", "R", "Integer"),
            "PL": FormatFieldDefinition("PL", "G", "Integer"),
            "AF": FormatFieldDefinition("AF", "A", "Float"),
            "PQ": FormatFieldDefinition("PQ", "P", "Integer"),
            "LAA": FormatFieldDefinition("LAA", ".", "Integer"),
            "LAF": FormatFieldDefinition("LAF", "LA", "Float"),
            "LAD": FormatFieldDefinition("LAD", "LR", "Integer"),
            "LPL": FormatFieldDefinition("LPL", "LG", "Integer"),
        }
        values = {
            "GT": "0/1", "AD": "20,4,1", "PL": "0,1,2,3,4,5",
            "AF": "0.2,0.1", "PQ": "23,31", "LAA": "1",
            "LAF": "0.5", "LAD": "20,4", "LPL": "0,1,2",
        }
        self.assertIsNone(validate_format_values(values, definitions, set(), 2))
        self.assertEqual(
            validate_format_values(values | {"AD": "20,4"}, definitions, set(), 2),
            "format_number_mismatch",
        )
        self.assertEqual(
            validate_format_values(values | {"AF": "bad,0.1"}, definitions, set(), 2),
            "format_type_mismatch",
        )
        self.assertEqual(
            validate_format_values(values | {"LAA": "1,1"}, definitions, set(), 2),
            "format_number_mismatch",
        )
        self.assertEqual(
            sample_format_values(("GT", "DP", "GQ"), "0/1:8"),
            {"GT": "0/1", "DP": "8", "GQ": "."},
        )


    def test_oversized_local_allele_index_is_a_schema_issue(self) -> None:
        definitions = {"LAA": FormatFieldDefinition("LAA", ".", "Integer")}
        self.assertEqual(
            validate_format_values({"LAA": "9" * 5000}, definitions, set(), 1),
            "format_number_mismatch",
        )
        self.assertEqual(
            validate_format_values(
                {"LAA": [10**5000]}, definitions, set(), 1, typed_values=True
            ),
            "format_number_mismatch",
        )


class InfoFieldParsingTests(unittest.TestCase):
    def test_flags_scalars_and_lists_keep_their_source_representation(self) -> None:
        parsed, issue = parse_info_fields("DP=12;AF=0.25,0.75;DB;1000G;MISSING=.")
        self.assertIsNone(issue)
        self.assertEqual(
            parsed,
            {
                "DP": "12",
                "AF": ["0.25", "0.75"],
                "DB": True,
                "1000G": True,
                "MISSING": ".",
            },
        )

    def test_missing_info_field_is_empty_but_empty_text_is_malformed(self) -> None:
        self.assertEqual(parse_info_fields("."), ({}, None))
        self.assertEqual(parse_info_fields(""), ({}, "empty_info_field"))

    def test_malformed_or_duplicate_fields_are_rejected_without_overwrite(self) -> None:
        cases = (
            ("DP=1;DP=2", "duplicate_info_key"),
            ("DP=1;;AF=0.5", "empty_info_field"),
            ("DP=1;", "empty_info_field"),
            ("DP=", "invalid_info_value"),
            ("AF=0.5,", "invalid_info_value"),
            ("DP=1=2", "invalid_info_value"),
            ("DP+=1", "invalid_info_key"),
        )
        for value, expected_issue in cases:
            with self.subTest(value=value):
                parsed, issue = parse_info_fields(value)
                self.assertEqual(parsed, {})
                self.assertEqual(issue, expected_issue)

    def test_info_definition_parses_reordered_fields_and_quoted_commas(self) -> None:
        line = '##INFO=<Description="frequency, per alternate",Type=Float,Number=A,ID=AF>'
        definition, issue, identifier = parse_info_definition(line)
        self.assertIsNone(issue)
        self.assertEqual(identifier, "AF")
        self.assertEqual(definition, InfoFieldDefinition("AF", "A", "Float"))

    def test_info_definition_rejects_missing_fields_bad_types_and_bad_flag_number(self) -> None:
        cases = (
            '##INFO=<ID=DP,Number=1,Type=Integer>',
            '##INFO=<ID=DP,Number=1,Type=Decimal,Description="depth">',
            '##INFO=<ID=DB,Number=1,Type=Flag,Description="flag">',
            '##INFO=<ID=DP,Number=A,Type=Integer,Description=depth>',
            '##INFO=<ID=DP,Number=1,Type=Integer,Description="unterminated>',
        )
        for line in cases:
            with self.subTest(line=line):
                definition, issue, _ = parse_info_definition(line)
                self.assertIsNone(definition)
                self.assertEqual(issue, "invalid_info_definition")

    def test_duplicate_schema_invalidates_the_key(self) -> None:
        definitions: dict[str, InfoFieldDefinition] = {}
        invalid: set[str] = set()
        first = '##INFO=<ID=DP,Number=1,Type=Integer,Description="depth">'
        second = '##INFO=<ID=DP,Number=1,Type=Float,Description="depth">'
        self.assertIsNone(register_info_definition(first, definitions, invalid))
        self.assertEqual(
            register_info_definition(second, definitions, invalid),
            "duplicate_info_definition",
        )
        self.assertEqual(definitions, {})
        self.assertEqual(invalid, {"DP"})
        self.assertEqual(
            validate_info_values({"DP": "12"}, definitions, invalid, 1),
            "invalid_info_definition",
        )

    def test_declared_info_type_and_cardinality_are_validated_without_coercion(self) -> None:
        definitions = {
            "DP": InfoFieldDefinition("DP", "1", "Integer"),
            "AF": InfoFieldDefinition("AF", "A", "Float"),
            "AD": InfoFieldDefinition("AD", "R", "Integer"),
            "DB": InfoFieldDefinition("DB", "0", "Flag"),
            "GL": InfoFieldDefinition("GL", "G", "Float"),
            "NOTE": InfoFieldDefinition("NOTE", ".", "String"),
        }
        self.assertIsNone(
            validate_info_values(
                {
                    "DP": "12",
                    "AF": ["0.25", "."],
                    "AD": ["12", "3", "4"],
                    "DB": True,
                    "GL": ["-1.2", "NAN"],
                    "NOTE": "reads from sample 1",
                },
                definitions,
                set(),
                2,
            )
        )
        self.assertEqual(
            validate_info_values({"AF": ["0.25"]}, definitions, set(), 2),
            "info_number_mismatch",
        )
        self.assertEqual(
            validate_info_values({"DP": "depth"}, definitions, set(), 1),
            "info_type_mismatch",
        )
        self.assertEqual(
            validate_info_values({"DB": "1"}, definitions, set(), 1),
            "info_type_mismatch",
        )
        self.assertEqual(
            validate_info_values({"DP": str(-(2**31))}, definitions, set(), 1),
            "info_type_mismatch",
        )


if __name__ == "__main__":
    unittest.main()
