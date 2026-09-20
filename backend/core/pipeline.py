import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from backend.core.schema import target_schema
from backend.core.ingestion import IngestionEngine, IngestedSource
from backend.core.mapper import SchemaMapper
from backend.core.cleaner import CleanerEngine
from backend.core.validator import SchemaValidator
from backend.core.escalation import global_escalations
from backend.core.delta import DeltaEngine
from backend.core.mock_target import global_mock_target
from backend.core.audit import global_audit

class PipelineState:
    def __init__(self):
        self.sources: List[IngestedSource] = []
        self.column_mappings: Dict[str, Dict[str, Any]] = {}  # filename -> {col: mapping_dict}
        self.raw_records_count: int = 0
        self.transformed_records: List[Dict[str, Any]] = []
        self.cleaned_records: List[Dict[str, Any]] = []
        self.valid_records: List[Dict[str, Any]] = []
        self.quarantined_records: List[Dict[str, Any]] = []
        self.deltas: List[Dict[str, Any]] = []
        self.push_result: Optional[Dict[str, Any]] = None
        self.is_processed: bool = False

    def reset(self):
        self.sources.clear()
        self.column_mappings.clear()
        self.raw_records_count = 0
        self.transformed_records.clear()
        self.cleaned_records.clear()
        self.valid_records.clear()
        self.quarantined_records.clear()
        self.deltas.clear()
        self.push_result = None
        self.is_processed = False
        global_escalations.clear()
        global_audit.clear()

        # Remove generated output files on reset so un-run states are pristine
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base_dir, "data", "migrated_output")
        for f_name in ["cleaned_target_employees.csv", "migration_audit_trail.json"]:
            f_path = os.path.join(output_dir, f_name)
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except OSError:
                    pass

global_pipeline_state = PipelineState()

class MigrationAgentPipeline:
    def __init__(self):
        self.schema = target_schema
        self.mapper = SchemaMapper(self.schema)
        self.cleaner = CleanerEngine(self.schema)
        self.validator = SchemaValidator(self.schema)

    def run_pipeline(self, file_inputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executes the autonomous pipeline from Ingestion through Delta analysis.
        Stops and populates the Escalation Queue whenever ambiguous items are hit.
        """
        global_pipeline_state.reset()
        
        # 1. Ingestion
        sources = IngestionEngine.ingest_files(file_inputs)
        global_pipeline_state.sources = sources
        total_raw = sum(s.row_count for s in sources)
        global_pipeline_state.raw_records_count = total_raw

        global_audit.record(
            action="INGESTION_COMPLETED",
            actor="AGENT",
            reason=f"Ingested {len(sources)} source files with total {total_raw} raw records",
            confidence=1.0
        )

        # 2. Autonomous Mapping with Confidence & Ambiguity Detection
        all_mapped_rows = []
        for src in sources:
            mappings = self.mapper.map_dataset(src.columns, src.rows)
            global_pipeline_state.column_mappings[src.filename] = {
                k: v.to_dict() for k, v in mappings.items()
            }

            # Check for ambiguous columns (Defensible Escalation Boundary)
            for col_name, prop in mappings.items():
                if prop.is_ambiguous:
                    global_escalations.add_schema_ambiguity(
                        column_name=col_name,
                        source_file=src.filename,
                        top_candidates=prop.candidate_fields,
                        confidence=prop.confidence
                    )
                else:
                    global_audit.record(
                        action="AUTO_MAP_COLUMN",
                        actor="AGENT",
                        field=prop.target_field,
                        source_file=src.filename,
                        reason=f"Autonomously mapped source header '{col_name}' to '{prop.target_field}': {prop.reasoning}",
                        confidence=prop.confidence
                    )

            # Transform raw rows using confirmed or best-guess mappings
            active_col_map = {
                col: prop.target_field for col, prop in mappings.items() if prop.target_field
            }
            for row in src.rows:
                transformed, issues = self.cleaner.transform_and_clean_record(row, active_col_map)
                all_mapped_rows.append(transformed)

        global_pipeline_state.transformed_records = all_mapped_rows

        # 3. Autonomous Deduplication & Conflict Escalation
        reconciled_records, conflicts = self.cleaner.reconcile_duplicates(all_mapped_rows)
        
        for c in conflicts:
            global_escalations.add_data_conflict(
                entity_id=c["entity_id"],
                field=c["field"],
                rec_a_info=c["record_a"],
                rec_b_info=c["record_b"]
            )

        global_pipeline_state.cleaned_records = reconciled_records

        # 4. Validation against Target Schema & Constraint Violations
        valid_records = []
        quarantined = []
        for r in reconciled_records:
            val_res = self.validator.validate_record(r)
            if val_res.is_valid and not r.get("_has_conflict"):
                valid_records.append(r)
            else:
                quarantined.append(r)
                # Generate validation escalations for each violating field
                for err in val_res.errors:
                    global_escalations.add_validation_failure(
                        record=r,
                        field=err.field,
                        error_msg=err.message
                    )

        global_pipeline_state.valid_records = valid_records
        global_pipeline_state.quarantined_records = quarantined

        # 5. Delta Solutioning against Mock Target Platform
        target_db = global_mock_target.get_database()
        deltas = DeltaEngine.compute_delta(valid_records, target_db)
        global_pipeline_state.deltas = [d.to_dict() for d in deltas]
        global_pipeline_state.is_processed = True

        self.persist_output_to_disk()
        return self.get_summary()

    def persist_output_to_disk(self):
        """Persists corrected records and audit trail into data/migrated_output/"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base_dir, "data", "migrated_output")
        os.makedirs(output_dir, exist_ok=True)

        if global_pipeline_state.valid_records:
            clean_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in global_pipeline_state.valid_records]
            df = pd.DataFrame(clean_rows)
            csv_path = os.path.join(output_dir, "cleaned_target_employees.csv")
            df.to_csv(csv_path, index=False)

        audit_path = os.path.join(output_dir, "migration_audit_trail.json")
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(global_audit.get_entries(), f, indent=2)

    def resolve_escalation_and_reprocess(
        self,
        escalation_id: str,
        resolution_type: str,
        resolved_value: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Applies human decision to an escalation item and re-evaluates pipeline state.
        """
        item = global_escalations.resolve_escalation(
            escalation_id=escalation_id,
            resolution_type=resolution_type,
            resolved_value=resolved_value
        )

        global_audit.record(
            action="ESCALATION_RESOLVED",
            actor="HUMAN",
            entity_id=item.entity_id,
            field=item.field,
            source_file=item.source_file,
            new_value=item.resolved_value,
            reason=f"Human resolved escalation '{item.title}' with action {resolution_type}: {item.resolved_value}",
            confidence=1.0
        )

        # Apply fix to quarantined record if validation failure or conflict
        if item.category in ["VALIDATION_FAILURE", "DATA_CONFLICT"] and item.entity_id:
            for r in list(global_pipeline_state.quarantined_records):
                rec_id = r.get("employee_id") or r.get("email")
                if rec_id == item.entity_id:
                    if resolution_type == "REJECTED":
                        # Record is rejected/dropped
                        global_pipeline_state.quarantined_records.remove(r)
                    else:
                        # Fix the value
                        if item.field:
                            r[item.field] = item.resolved_value
                        r.pop("_has_conflict", None)
                        
                        # Re-validate
                        res = self.validator.validate_record(r)
                        if res.is_valid:
                            global_pipeline_state.quarantined_records.remove(r)
                            global_pipeline_state.valid_records.append(r)
                            
                            # Re-compute deltas
                            target_db = global_mock_target.get_database()
                            deltas = DeltaEngine.compute_delta(global_pipeline_state.valid_records, target_db)
                            global_pipeline_state.deltas = [d.to_dict() for d in deltas]
                    break

        self.persist_output_to_disk()
        return self.get_summary()

    def push_to_target(self) -> Dict[str, Any]:
        """
        Executes mock push of all valid records to target platform
        """
        records_to_push = global_pipeline_state.valid_records
        res = global_mock_target.push_records(records_to_push)
        global_pipeline_state.push_result = res
        return res

    def rollback_push(self, tx_id: str) -> Dict[str, Any]:
        return global_mock_target.rollback(tx_id)

    def get_summary(self) -> Dict[str, Any]:
        pending_escalations = global_escalations.get_pending()
        all_escalations = global_escalations.get_all()
        delta_summary = {
            "total": len(global_pipeline_state.deltas),
            "new": sum(1 for d in global_pipeline_state.deltas if d["delta_type"] == "NEW"),
            "update": sum(1 for d in global_pipeline_state.deltas if d["delta_type"] == "UPDATE"),
            "no_change": sum(1 for d in global_pipeline_state.deltas if d["delta_type"] == "NO_CHANGE"),
            "conflict": sum(1 for d in global_pipeline_state.deltas if d["delta_type"] == "CONFLICT")
        }

        return {
            "sources": [s.to_dict() for s in global_pipeline_state.sources],
            "raw_records_count": global_pipeline_state.raw_records_count,
            "column_mappings": global_pipeline_state.column_mappings,
            "cleaned_count": len(global_pipeline_state.cleaned_records),
            "valid_count": len(global_pipeline_state.valid_records),
            "quarantined_count": len(global_pipeline_state.quarantined_records),
            "pending_escalations_count": len(pending_escalations),
            "pending_escalations": pending_escalations,
            "all_escalations": all_escalations,
            "delta_summary": delta_summary,
            "deltas": global_pipeline_state.deltas,
            "is_processed": global_pipeline_state.is_processed,
            "valid_records_preview": global_pipeline_state.valid_records[:20],
            "audit_trail": global_audit.get_entries()[-40:],
            "push_result": global_pipeline_state.push_result,
            "target_database_preview": list(global_mock_target.get_database().values())
        }

global_agent_pipeline = MigrationAgentPipeline()
