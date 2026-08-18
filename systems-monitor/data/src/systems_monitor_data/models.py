from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Observation:
    observation_id: str
    indicator_id: str
    source_id: str
    source_series_id: str
    release_id: str
    artifact_sha256: str
    value: Decimal
    unit: str
    geography: str
    valid_time: str
    public_time: str
    retrieved_time: str
    accepted_time: str
    vintage_id: str
    revision_number: int
    supersedes_observation_id: str | None
    publication_time_kind: str
    provenance_url: str
    rights_state: str = "ALLOW"

    def validate(self) -> None:
        public = parse_utc(self.public_time)
        retrieved = parse_utc(self.retrieved_time)
        accepted = parse_utc(self.accepted_time)
        if accepted < retrieved:
            raise ValueError("accepted_time cannot precede retrieved_time")
        if self.publication_time_kind == "official" and retrieved < public:
            raise ValueError("retrieval cannot precede official public availability")
        Decimal(self.value)
        if self.geography != "US" or self.rights_state not in {"ALLOW", "DENY", "UNKNOWN"}:
            raise ValueError("invalid geography or rights state")

    def as_record(self) -> dict[str, Any]:
        data = asdict(self)
        data["value"] = str(self.value)
        return data

