# Workbench release frontier data dictionary

| Field | Shape | Meaning |
| --- | --- | --- |
| `fixture_id` | string | stable public fixture identity |
| `context_key` | string | exact ordered workbench boundary |
| `source_ids` | array[string] | joins to public source receipts |
| `payload` | object | operation input projection |
| `expected_state` | enum | fixture-declared behavior |
| `expected_issue_codes` | array[string] | control reasons expected from replay |
| `observed_state` | enum | operation result state |
| `issue_codes` | array[string] | normalized operation findings |
| `output` | object | safe result projection |
| `content_address` | string | canonical SHA-256 receipt |
| `completion` | number | descriptive valid-field fraction for a form |
| `score` | number | descriptive accessibility pass fraction |
| `result_count` | integer | bounded search result count |
| `line_count` | integer | rendered report section line count |

Search results retain matched fields, score, record type, title, and command when
present. Accessibility findings retain criterion, pass state, severity, and message.
Report sections retain section identity, title, order, rendered content, line count,
and section address. Review fields retain identity, label, required flag, validity,
issue, and value-presence without echoing private values.

The data dictionary is descriptive. It does not imply a calibrated probability,
clinical outcome, or accessibility certification.
