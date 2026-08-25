"""Replay and integrity verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .events import EventLog
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class ReplayReport:
    run_id: str
    event_chain_valid: bool
    input_address: str
    dossier_address: str
    stored_dossier_matches_address: bool
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "event_chain_valid": self.event_chain_valid,
            "input_address": self.input_address,
            "dossier_address": self.dossier_address,
            "stored_dossier_matches_address": self.stored_dossier_matches_address,
            "warnings": list(self.warnings),
        }


class ReplayVerifier:
    """Verify event links and canonical dossier content after a run."""

    def verify(self, run_record: dict[str, Any], event_record: dict[str, Any], dossier_record: dict[str, Any]) -> ReplayReport:
        run_id = str(run_record["run_id"])
        warnings: list[str] = []
        try:
            log = EventLog.from_record(event_record)
            event_chain_valid = log.run_id == run_id and log.verify()
        except (KeyError, TypeError, ValueError):
            event_chain_valid = False
        if not event_chain_valid:
            warnings.append("event chain verification failed")
        content_payload = {key: value for key, value in dossier_record.items() if key != "content_address"}
        expected = content_hash(content_payload)
        stored_matches = expected == dossier_record.get("content_address")
        if not stored_matches:
            warnings.append("dossier content address does not match canonical payload")
        return ReplayReport(
            run_id=run_id,
            event_chain_valid=event_chain_valid,
            input_address=str(run_record["input_address"]),
            dossier_address=str(run_record["dossier_address"]),
            stored_dossier_matches_address=stored_matches,
            warnings=tuple(warnings),
        )
