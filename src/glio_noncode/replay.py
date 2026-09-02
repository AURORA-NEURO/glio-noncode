"""Replay and integrity verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .events import EventLog
from .models import Dossier


def _sha256_address(value: object, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValidationError(f"{label} must be a canonical sha256 content address")
    return value


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

    def verify(
        self,
        run_record: dict[str, Any],
        event_record: dict[str, Any],
        dossier_record: dict[str, Any],
    ) -> ReplayReport:
        for label, value in (
            ("run record", run_record),
            ("event record", event_record),
            ("dossier record", dossier_record),
        ):
            if not isinstance(value, dict):
                raise ValidationError(f"{label} must be an object")
        required_run_fields = {"run_id", "input_address", "event_address", "dossier_address"}
        missing = required_run_fields - set(run_record)
        if missing:
            raise ValidationError(f"run record is missing required fields: {sorted(missing)}")
        run_id = run_record["run_id"]
        input_address = _sha256_address(
            run_record["input_address"],
            "run record input_address",
        )
        _sha256_address(
            run_record["event_address"],
            "run record event_address",
        )
        dossier_address = _sha256_address(
            run_record["dossier_address"],
            "run record dossier_address",
        )
        if type(run_id) is not str or not run_id:
            raise ValidationError("run record run_id must be a non-empty string")
        warnings: list[str] = []
        log: EventLog | None = None
        try:
            log = EventLog.from_record(event_record)
            event_chain_valid = log.run_id == run_id and log.verify()
        except (KeyError, TypeError, ValueError):
            event_chain_valid = False
        if not event_chain_valid:
            warnings.append("event chain verification failed")

        dossier: Dossier | None = None
        try:
            dossier = Dossier.from_dict(dossier_record)
        except ValidationError as exc:
            warnings.append(f"dossier contract validation failed: {exc}")
        stored_matches = dossier is not None and dossier.content_address == dossier_address
        if dossier is not None:
            if dossier.run_id != run_id:
                stored_matches = False
                warnings.append("dossier run identifier does not match run record")
            if dossier.input_address != input_address:
                stored_matches = False
                warnings.append("dossier input address does not match run record")
            if log is not None and dossier.event_head != log.head:
                event_chain_valid = False
                warnings.append("dossier event head does not match event chain")
        if not stored_matches:
            warnings.append("dossier content address does not match canonical payload")
        return ReplayReport(
            run_id=run_id,
            event_chain_valid=event_chain_valid,
            input_address=input_address,
            dossier_address=dossier_address,
            stored_dossier_matches_address=stored_matches,
            warnings=tuple(warnings),
        )
