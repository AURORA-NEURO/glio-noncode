"""Failure taxonomy and bounded recovery guidance for D08."""

from __future__ import annotations

from typing import Any

D08_FAILURES = {
    "context_mismatch": {
        "severity": "high",
        "disposition": "hold",
        "recovery": "restate the exact context key and re-run the case",
    },
    "malformed_input": {
        "severity": "high",
        "disposition": "hold",
        "recovery": "repair the declared object shape before delegation",
    },
    "identity_conflict": {
        "severity": "critical",
        "disposition": "hold",
        "recovery": "reconcile conflicting identity fields outside the release",
    },
    "invalid_cell_count": {
        "severity": "high",
        "disposition": "review",
        "recovery": "verify count bounds against total cells",
    },
    "ambiguous_reference_mapping": {
        "severity": "medium",
        "disposition": "review",
        "recovery": "increase score or margin support before mapping",
    },
    "cell_state_out_of_domain": {
        "severity": "medium",
        "disposition": "review",
        "recovery": "declare a supported boundary or retain the OOD finding",
    },
}


def failure_definition(code: str) -> dict[str, Any]:
    return dict(
        D08_FAILURES.get(
            code,
            {
                "severity": "unknown",
                "disposition": "review",
                "recovery": "inspect the receipt and preserve evidence",
            },
        )
    ) | {"code": code}


def failure_summary(issue_codes: tuple[str, ...]) -> dict[str, Any]:
    definitions = [failure_definition(code) for code in issue_codes]
    return {
        "issue_codes": list(issue_codes),
        "definitions": definitions,
        "blocking": any(item["disposition"] == "hold" for item in definitions),
    }


__all__ = ["D08_FAILURES", "failure_definition", "failure_summary"]
