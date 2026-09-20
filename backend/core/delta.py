from typing import Dict, List, Any, Optional

class DeltaRecord:
    def __init__(
        self,
        entity_id: str,
        delta_type: str,  # "NEW", "UPDATE", "NO_CHANGE", "CONFLICT"
        incoming_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]] = None,
        field_diffs: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        self.entity_id = entity_id
        self.delta_type = delta_type
        self.incoming_data = incoming_data
        self.target_data = target_data
        self.field_diffs = field_diffs or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "delta_type": self.delta_type,
            "incoming_data": self.incoming_data,
            "target_data": self.target_data,
            "field_diffs": self.field_diffs
        }

class DeltaEngine:
    @staticmethod
    def compute_delta(
        incoming_records: List[Dict[str, Any]],
        existing_target_store: Dict[str, Dict[str, Any]]
    ) -> List[DeltaRecord]:
        """
        existing_target_store: Dict keyed by employee_id or email
        """
        deltas = []

        for record in incoming_records:
            emp_id = record.get("employee_id")
            email = record.get("email")
            
            # Lookup in target store
            target_match = None
            if emp_id and emp_id in existing_target_store:
                target_match = existing_target_store[emp_id]
            elif email and email in existing_target_store:
                target_match = existing_target_store[email]

            clean_incoming = {k: v for k, v in record.items() if not k.startswith("_")}

            if not target_match:
                deltas.append(DeltaRecord(
                    entity_id=emp_id or email or "Unknown",
                    delta_type="NEW",
                    incoming_data=clean_incoming
                ))
            else:
                # Compare fields
                diffs = {}
                is_conflict = False

                for k, in_v in clean_incoming.items():
                    if in_v is None:
                        continue
                    tgt_v = target_match.get(k)
                    if tgt_v is None:
                        diffs[k] = {"before": None, "after": in_v}
                    elif str(in_v).strip().lower() != str(tgt_v).strip().lower():
                        diffs[k] = {"before": tgt_v, "after": in_v}
                        # Conflict rule: e.g. status active vs inactive in target
                        if k == "status" and tgt_v == "INACTIVE" and in_v == "ACTIVE":
                            is_conflict = True

                if is_conflict:
                    delta_type = "CONFLICT"
                elif diffs:
                    delta_type = "UPDATE"
                else:
                    delta_type = "NO_CHANGE"

                deltas.append(DeltaRecord(
                    entity_id=emp_id or email or "Unknown",
                    delta_type=delta_type,
                    incoming_data=clean_incoming,
                    target_data=target_match,
                    field_diffs=diffs
                ))

        return deltas
