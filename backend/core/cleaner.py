import re
from typing import Dict, List, Any, Optional, Tuple
from dateutil import parser as date_parser
from backend.core.schema import TargetSchema
from backend.core.audit import global_audit

class CleanerEngine:
    def __init__(self, schema: TargetSchema):
        self.schema = schema

    @staticmethod
    def clean_text(val: Any) -> Optional[str]:
        if val is None:
            return None
        text = str(val).strip()
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text)
        return text if text else None

    @staticmethod
    def clean_name(val: Any) -> Optional[str]:
        cleaned = CleanerEngine.clean_text(val)
        if not cleaned:
            return None
        # Title case name components
        return " ".join(part.capitalize() for part in cleaned.split(" "))

    @staticmethod
    def clean_email(val: Any) -> Optional[str]:
        cleaned = CleanerEngine.clean_text(val)
        if not cleaned:
            return None
        return cleaned.lower()

    @staticmethod
    def clean_phone(val: Any) -> Optional[str]:
        cleaned = CleanerEngine.clean_text(val)
        if not cleaned:
            return None
        # Keep leading +, digits, remove parentheses and excessive dashes
        has_plus = cleaned.startswith("+")
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) >= 10:
            if has_plus:
                return f"+{digits}"
            elif len(digits) == 10:
                return f"+1{digits}"
            else:
                return f"+{digits}"
        return cleaned

    @staticmethod
    def clean_date(val: Any) -> Tuple[Optional[str], Optional[str]]:
        """Returns (cleaned_iso_date, error_message)"""
        cleaned = CleanerEngine.clean_text(val)
        if not cleaned:
            return None, None
        
        # Strip ordinal suffixes e.g., 15th, 1st, 2nd, 3rd
        sanitized = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", cleaned, flags=re.IGNORECASE)
        
        try:
            # If format has day first e.g. 15/01/2021
            parsed = None
            if "/" in sanitized:
                parts = sanitized.split("/")
                if len(parts) == 3 and len(parts[0]) == 2 and int(parts[0]) > 12:
                    parsed = date_parser.parse(sanitized, dayfirst=True)
                else:
                    parsed = date_parser.parse(sanitized)
            else:
                parsed = date_parser.parse(sanitized)

            iso_date = parsed.strftime("%Y-%m-%d")
            return iso_date, None
        except Exception as e:
            return None, f"Unable to parse date '{val}': {str(e)}"

    @staticmethod
    def clean_salary(val: Any) -> Tuple[Optional[float], Optional[str]]:
        cleaned = CleanerEngine.clean_text(val)
        if cleaned is None:
            return None, None
        # Strip currency symbols and commas
        clean_num_str = re.sub(r"[$,\s]", "", cleaned)
        try:
            num = float(clean_num_str)
            if num < 0:
                return num, f"Salary value {num} is negative (violates non-negative constraint)"
            return num, None
        except ValueError:
            return None, f"Salary value '{val}' cannot be converted to numeric amount"

    @staticmethod
    def clean_status(val: Any) -> Optional[str]:
        cleaned = CleanerEngine.clean_text(val)
        if not cleaned:
            return "ACTIVE"
        upper = cleaned.upper().replace(" ", "_")
        if upper in ["ACTIVE", "ACT", "EMPLOYED"]:
            return "ACTIVE"
        if upper in ["INACTIVE", "INACT", "TERMINATED", "RESIGNED", "EXIT"]:
            return "INACTIVE"
        if upper in ["ON_LEAVE", "LEAVE", "FURLOUGH", "ABSENT"]:
            return "ON_LEAVE"
        return upper

    @staticmethod
    def clean_department(val: Any) -> Optional[str]:
        cleaned = CleanerEngine.clean_text(val)
        if not cleaned:
            return None
        norm = cleaned.lower()
        dept_map = {
            "engineering": "Engineering",
            "eng": "Engineering",
            "tech": "Engineering",
            "product": "Product",
            "sales": "Sales",
            "human resources": "Human Resources",
            "hr": "Human Resources",
            "finance": "Finance",
            "operations": "Operations",
            "ops": "Operations",
            "customer success": "Customer Success",
            "support": "Customer Success",
            "cs": "Customer Success"
        }
        return dept_map.get(norm, CleanerEngine.clean_name(cleaned))

    def clean_field_value(self, field_name: str, raw_val: Any) -> Tuple[Any, Optional[str]]:
        """Cleans value according to schema. Returns (cleaned_val, warning_or_error)"""
        field_def = self.schema.fields.get(field_name)
        if not field_def or raw_val is None:
            return raw_val, None

        if field_name in ["first_name", "last_name", "job_title"]:
            return self.clean_name(raw_val), None
        elif field_name == "email":
            return self.clean_email(raw_val), None
        elif field_name == "phone_number":
            return self.clean_phone(raw_val), None
        elif field_name == "department":
            return self.clean_department(raw_val), None
        elif field_name == "hire_date":
            return self.clean_date(raw_val)
        elif field_name == "salary":
            return self.clean_salary(raw_val)
        elif field_name == "status":
            return self.clean_status(raw_val), None
        elif field_name == "employee_id":
            cleaned = self.clean_text(raw_val)
            return cleaned.upper() if cleaned else None, None
        
        return self.clean_text(raw_val), None

    def transform_and_clean_record(self, raw_row: Dict[str, Any], column_mapping: Dict[str, str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Maps raw row keys into target schema fields and runs normalization.
        Returns: (transformed_record, list_of_clean_issues)
        """
        record = {}
        issues = []
        source_file = raw_row.get("_source_file", "unknown")
        source_row = raw_row.get("_source_row")

        for src_col, raw_val in raw_row.items():
            if src_col.startswith("_"):
                continue
            target_field = column_mapping.get(src_col)
            if not target_field:
                continue

            cleaned_val, err = self.clean_field_value(target_field, raw_val)
            record[target_field] = cleaned_val

            # Record audit if changed
            if raw_val is not None and str(raw_val) != str(cleaned_val):
                global_audit.record(
                    action="AUTO_CLEAN",
                    actor="AGENT",
                    entity_id=record.get("employee_id") or record.get("email"),
                    field=target_field,
                    source_file=source_file,
                    source_row=source_row,
                    old_value=raw_val,
                    new_value=cleaned_val,
                    reason=f"Standardized {src_col} to schema target {target_field}",
                    confidence=0.98
                )

            if err:
                issues.append({
                    "field": target_field,
                    "source_col": src_col,
                    "raw_val": raw_val,
                    "cleaned_val": cleaned_val,
                    "error": err,
                    "source_file": source_file,
                    "source_row": source_row
                })

        record["_source_file"] = source_file
        record["_source_row"] = source_row
        return record, issues

    def reconcile_duplicates(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Detects duplicates by (employee_id or email).
        If records have matching or non-conflicting fields, merges them autonomously.
        If records have conflicting non-null fields, generates conflict escalation items.
        Returns (reconciled_records, list_of_conflicts)
        """
        groups: Dict[str, List[Dict[str, Any]]] = {}
        reconciled = []
        conflicts = []

        # Index by employee_id or email
        for r in records:
            key = r.get("employee_id") or r.get("email")
            if not key:
                reconciled.append(r)
                continue
            groups.setdefault(key, []).append(r)

        for key, rec_list in groups.items():
            if len(rec_list) == 1:
                reconciled.append(rec_list[0])
                continue

            # Multi-record conflict detection & merge
            merged = dict(rec_list[0])
            conflict_detected = False

            for next_rec in rec_list[1:]:
                for field, val in next_rec.items():
                    if field.startswith("_"):
                        continue
                    if val is None:
                        continue
                    curr_val = merged.get(field)
                    if curr_val is None:
                        # Auto-merge missing field safely
                        merged[field] = val
                        global_audit.record(
                            action="AUTO_MERGE_FIELD",
                            actor="AGENT",
                            entity_id=key,
                            field=field,
                            source_file=next_rec.get("_source_file"),
                            source_row=next_rec.get("_source_row"),
                            old_value=None,
                            new_value=val,
                            reason=f"Autonomously filled missing field from {next_rec.get('_source_file')}",
                            confidence=0.99
                        )
                    elif str(curr_val).strip().lower() != str(val).strip().lower():
                        # CONFLICT! Defensible escalation boundary
                        conflict_detected = True
                        conflicts.append({
                            "entity_id": key,
                            "field": field,
                            "record_a": {
                                "source_file": merged.get("_source_file"),
                                "source_row": merged.get("_source_row"),
                                "value": curr_val
                            },
                            "record_b": {
                                "source_file": next_rec.get("_source_file"),
                                "source_row": next_rec.get("_source_row"),
                                "value": val
                            },
                            "reason": f"Contradictory values for field '{field}' across source files: '{curr_val}' vs '{val}'"
                        })

            if not conflict_detected:
                global_audit.record(
                    action="AUTO_DEDUPLICATE",
                    actor="AGENT",
                    entity_id=key,
                    reason=f"Autonomously consolidated {len(rec_list)} matching records across sources into one",
                    confidence=1.0
                )
                reconciled.append(merged)
            else:
                # Keep merged base but mark as conflicted
                merged["_has_conflict"] = True
                reconciled.append(merged)

        return reconciled, conflicts
