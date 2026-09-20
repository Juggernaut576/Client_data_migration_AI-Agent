from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class AuditEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    entity_id: Optional[str] = None
    field: Optional[str] = None
    source_file: Optional[str] = None
    source_row: Optional[int] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    action: str  # e.g., "AUTO_CLEAN", "AUTO_MERGE", "ESCALATION_RESOLVED", "PUSHED_TO_TARGET", "ROLLBACK"
    actor: str = "AGENT"  # "AGENT" | "HUMAN"
    reason: str
    confidence: Optional[float] = None

class AuditTrail:
    def __init__(self):
        self.entries: List[AuditEntry] = []

    def record(
        self,
        action: str,
        reason: str,
        actor: str = "AGENT",
        entity_id: Optional[str] = None,
        field: Optional[str] = None,
        source_file: Optional[str] = None,
        source_row: Optional[int] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        confidence: Optional[float] = None
    ) -> AuditEntry:
        entry = AuditEntry(
            action=action,
            reason=reason,
            actor=actor,
            entity_id=entity_id,
            field=field,
            source_file=source_file,
            source_row=source_row,
            old_value=old_value,
            new_value=new_value,
            confidence=confidence
        )
        self.entries.append(entry)
        return entry

    def get_entries(self) -> List[Dict[str, Any]]:
        return [e.model_dump() for e in self.entries]

    def clear(self):
        self.entries.clear()

global_audit = AuditTrail()
