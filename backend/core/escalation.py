import uuid
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

class EscalationItem(BaseModel):
    id: str = Field(default_factory=lambda: f"ESC-{uuid.uuid4().hex[:6].upper()}")
    category: str  # "SCHEMA_AMBIGUITY" | "DATA_CONFLICT" | "VALIDATION_FAILURE"
    title: str
    severity: str = "MEDIUM"  # "HIGH" | "MEDIUM" | "LOW"
    entity_id: Optional[str] = None
    field: Optional[str] = None
    source_file: Optional[str] = None
    source_row: Optional[int] = None
    current_value: Optional[Any] = None
    agent_reasoning: str
    confidence_score: float
    suggested_action: str
    suggested_value: Optional[Any] = None
    status: str = "PENDING"  # "PENDING" | "RESOLVED" | "REJECTED"
    resolution_type: Optional[str] = None  # "APPROVED_SUGGESTION" | "MANUAL_OVERRIDE" | "REJECTED"
    resolved_value: Optional[Any] = None
    resolved_by: Optional[str] = None

class EscalationManager:
    def __init__(self):
        self.escalations: Dict[str, EscalationItem] = {}

    def add_schema_ambiguity(
        self,
        column_name: str,
        source_file: str,
        top_candidates: List[Dict[str, Any]],
        confidence: float
    ) -> EscalationItem:
        cand_str = " or ".join([f"'{c.get('target_field')}' ({c.get('score')})" for c in top_candidates[:2]])
        best_cand = top_candidates[0].get("target_field") if top_candidates else None
        item = EscalationItem(
            category="SCHEMA_AMBIGUITY",
            title=f"Ambiguous Column Mapping: '{column_name}'",
            severity="HIGH",
            field=column_name,
            source_file=source_file,
            current_value=column_name,
            agent_reasoning=f"Column header could map to multiple schema fields with near-equal confidence: {cand_str}.",
            confidence_score=confidence,
            suggested_action=f"Map '{column_name}' to '{best_cand}'",
            suggested_value=best_cand
        )
        self.escalations[item.id] = item
        return item

    def add_data_conflict(
        self,
        entity_id: str,
        field: str,
        rec_a_info: Dict[str, Any],
        rec_b_info: Dict[str, Any]
    ) -> EscalationItem:
        val_a = rec_a_info.get("value")
        val_b = rec_b_info.get("value")
        file_a = rec_a_info.get("source_file")
        file_b = rec_b_info.get("source_file")

        item = EscalationItem(
            category="DATA_CONFLICT",
            title=f"Contradictory '{field}' for Entity {entity_id}",
            severity="HIGH",
            entity_id=entity_id,
            field=field,
            source_file=f"{file_a} & {file_b}",
            current_value=f"{val_a} vs {val_b}",
            agent_reasoning=(
                f"Duplicate record for {entity_id} has irreconcilable values in '{field}': "
                f"'{val_a}' (from {file_a}) vs '{val_b}' (from {file_b}). Cannot safely guess truth."
            ),
            confidence_score=0.45,
            suggested_action=f"Retain primary system value '{val_a}'",
            suggested_value=val_a
        )
        self.escalations[item.id] = item
        return item

    def add_validation_failure(
        self,
        record: Dict[str, Any],
        field: str,
        error_msg: str,
        suggested_val: Optional[Any] = None,
        suggested_action_desc: Optional[str] = None
    ) -> EscalationItem:
        rec_id = record.get("employee_id") or record.get("email") or "Unknown"
        raw_val = record.get(field)
        
        # Heuristic for suggestions
        if not suggested_action_desc:
            if field == "salary" and raw_val is not None:
                try:
                    abs_val = abs(float(raw_val))
                    suggested_val = abs_val
                    suggested_action_desc = f"Convert negative salary to absolute value (${abs_val:,.2f})"
                except Exception:
                    suggested_action_desc = "Provide a valid annual compensation number"
            elif field == "hire_date":
                suggested_val = "2024-01-15"
                suggested_action_desc = "Provide corrected date in YYYY-MM-DD format (Default: '2024-01-15')"
            else:
                suggested_action_desc = f"Provide a valid value conforming to schema for '{field}'"

        item = EscalationItem(
            category="VALIDATION_FAILURE",
            title=f"Schema Constraint Violation on '{field}'",
            severity="MEDIUM",
            entity_id=rec_id,
            field=field,
            source_file=record.get("_source_file"),
            source_row=record.get("_source_row"),
            current_value=raw_val,
            agent_reasoning=f"Field violates target schema rule: {error_msg}.",
            confidence_score=0.50,
            suggested_action=suggested_action_desc,
            suggested_value=suggested_val
        )
        self.escalations[item.id] = item
        return item

    def resolve_escalation(
        self,
        escalation_id: str,
        resolution_type: str,
        resolved_value: Optional[Any] = None,
        resolved_by: str = "Consultant"
    ) -> EscalationItem:
        if escalation_id not in self.escalations:
            raise KeyError(f"Escalation {escalation_id} not found")
        item = self.escalations[escalation_id]
        item.status = "RESOLVED" if resolution_type != "REJECTED" else "REJECTED"
        item.resolution_type = resolution_type
        item.resolved_value = resolved_value if resolved_value is not None else item.suggested_value
        item.resolved_by = resolved_by
        return item

    def get_pending(self) -> List[Dict[str, Any]]:
        return [item.model_dump() for item in self.escalations.values() if item.status == "PENDING"]

    def get_all(self) -> List[Dict[str, Any]]:
        return [item.model_dump() for item in self.escalations.values()]

    def clear(self):
        self.escalations.clear()

global_escalations = EscalationManager()
