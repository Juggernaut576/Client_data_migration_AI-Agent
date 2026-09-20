import re
from typing import Dict, List, Any, Optional, Tuple
from backend.core.schema import TargetSchema

class ValidationErrorItem:
    def __init__(self, field: str, value: Any, rule: str, message: str, is_blocking: bool = True):
        self.field = field
        self.value = value
        self.rule = rule
        self.message = message
        self.is_blocking = is_blocking

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "rule": self.rule,
            "message": self.message,
            "is_blocking": self.is_blocking
        }

class ValidationResult:
    def __init__(self, record_id: Optional[str], is_valid: bool, errors: List[ValidationErrorItem]):
        self.record_id = record_id
        self.is_valid = is_valid
        self.errors = errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors]
        }

class SchemaValidator:
    def __init__(self, schema: TargetSchema):
        self.schema = schema

    def validate_record(self, record: Dict[str, Any]) -> ValidationResult:
        errors: List[ValidationErrorItem] = []
        rec_id = record.get("employee_id") or record.get("email") or "Unknown"

        for field_name, field_def in self.schema.fields.items():
            val = record.get(field_name)

            # 1. Required Check
            if field_def.required:
                if val is None or str(val).strip() == "":
                    errors.append(ValidationErrorItem(
                        field=field_name,
                        value=val,
                        rule="REQUIRED",
                        message=f"Mandatory field '{field_name}' is missing"
                    ))
                    continue

            if val is None:
                continue

            # 2. Minimum numeric constraint
            if field_def.minimum is not None:
                try:
                    num_val = float(val)
                    if num_val < field_def.minimum:
                        errors.append(ValidationErrorItem(
                            field=field_name,
                            value=val,
                            rule="MINIMUM_CONSTRAINT",
                            message=f"Value {num_val} violates minimum allowable threshold {field_def.minimum}"
                        ))
                except (ValueError, TypeError):
                    errors.append(ValidationErrorItem(
                        field=field_name,
                        value=val,
                        rule="TYPE_ERROR",
                        message=f"Expected numeric value for '{field_name}', got '{val}'"
                    ))

            # 3. Enum constraint
            if field_def.enum is not None:
                if str(val) not in field_def.enum:
                    errors.append(ValidationErrorItem(
                        field=field_name,
                        value=val,
                        rule="ENUM_VIOLATION",
                        message=f"Value '{val}' is not in allowed enum options: {', '.join(field_def.enum)}"
                    ))

            # 4. Format constraint: email
            if field_def.format == "email":
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(val)):
                    errors.append(ValidationErrorItem(
                        field=field_name,
                        value=val,
                        rule="FORMAT_EMAIL",
                        message=f"'{val}' is not a valid email format"
                    ))

            # 5. Format constraint: date
            if field_def.format == "date":
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(val)):
                    errors.append(ValidationErrorItem(
                        field=field_name,
                        value=val,
                        rule="FORMAT_DATE",
                        message=f"'{val}' is not a valid ISO 8601 date (YYYY-MM-DD)"
                    ))

        return ValidationResult(
            record_id=rec_id,
            is_valid=len(errors) == 0,
            errors=errors
        )

    def validate_dataset(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[ValidationResult]]:
        valid_records = []
        invalid_results = []
        for r in records:
            res = self.validate_record(r)
            if res.is_valid:
                valid_records.append(r)
            else:
                invalid_results.append(res)
        return valid_records, invalid_results
