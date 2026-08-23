# Validation-design frontier data dictionary

| Field | Meaning | Boundary |
| --- | --- | --- |
| fixture_id | stable public fixture identity | deterministic |
| fixture_version | contract version | release-scoped |
| context_key | genome, disease, age, state, territory, treatment context | exact match |
| evidence_boundary | declared source boundary | public aggregate |
| source_ids | source receipt joins | known HTTPS receipts |
| record_id | scenario identity | unique |
| capability | human-readable planning capability | four operation families |
| operation | executable operation enum | four values |
| role | positive or control | balanced |
| payload | operation input object | safe synthetic aggregate |
| expected_state | fixture expectation | explicit |
| expected_issue_codes | control reason expectation | normalized |
| observed_state | runtime decision | deterministic |
| issue_codes | runtime reasons | visible |
| output | safe operation projection | no private markers |
| content_address | content identity | SHA-256 |

The public fixture has five receipts, sixteen records, four positive records, twelve controls, four operations, and eighty row checks. A source receipt carries an HTTPS URI, scope, version label, and content address.
