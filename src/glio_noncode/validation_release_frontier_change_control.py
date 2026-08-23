"""Change-control receipt for versioned validation-release contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ValidationReleaseChangeControl:
    change_id: str
    from_version: str
    to_version: str
    required_checks: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_change_control(from_version: str, to_version: str) -> ValidationReleaseChangeControl:
    body = {"change_id": f"change:{from_version}->{to_version}", "from_version": from_version, "to_version": to_version, "required_checks": ("schema", "replay", "quality", "release"), "accepted": bool(from_version and to_version and from_version != to_version)}
    return ValidationReleaseChangeControl(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseChangeControl", "build_validation_release_change_control"]
