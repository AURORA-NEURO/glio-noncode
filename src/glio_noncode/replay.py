"""Replay and integrity verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .events import EventLog, RuntimeEvent
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
        log = EventLog(run_id)
        for raw in event_record.get("events", []):
            event = RuntimeEvent(
                event_id=str(raw["event_id"]),
                run_id=str(raw["run_id"]),
                event_type=str(raw["event_type"]),
                payload=dict(raw.get("payload", {})),
                created_at=str(raw["created_at"]),
                previous_hash=raw.get("previous_hash"),
                event_hash=str(raw.get("event_hash", "")),
            )
            log._events.append(event)
        warnings: list[str] = []
        if not log.verify():
            warnings.append("event chain verification failed")
        content_payload = {key: value for key, value in dossier_record.items() if key != "content_address"}
        expected = content_hash(content_payload)
        stored_matches = expected == dossier_record.get("content_address")
        if not stored_matches:
            warnings.append("dossier content address does not match canonical payload")
        return ReplayReport(
            run_id=run_id,
            event_chain_valid=log.verify(),
            input_address=str(run_record["input_address"]),
            dossier_address=str(run_record["dossier_address"]),
            stored_dossier_matches_address=stored_matches,
            warnings=tuple(warnings),
        )
