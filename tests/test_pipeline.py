import pytest
import os
from backend.core.schema import target_schema
from backend.core.pipeline import global_agent_pipeline, global_pipeline_state
from backend.core.mock_target import global_mock_target
from backend.core.cleaner import CleanerEngine

def test_cleaner_date_parsing():
    # Various formats
    d1, err1 = CleanerEngine.clean_date("15/01/2021")
    assert d1 == "2021-01-15"
    assert err1 is None

    d2, err2 = CleanerEngine.clean_date("2020-06-01")
    assert d2 == "2020-06-01"
    assert err2 is None

    d3, err3 = CleanerEngine.clean_date("12-Nov-2019")
    assert d3 == "2019-11-12"
    assert err3 is None

    # Invalid date format should produce error message
    d4, err4 = CleanerEngine.clean_date("invalid-date-format-32/99")
    assert d4 is None
    assert err4 is not None

def test_cleaner_salary_and_whitespace():
    sal1, err1 = CleanerEngine.clean_salary("$145,000 ")
    assert sal1 == 145000.0
    assert err1 is None

    # Negative salary constraint
    sal2, err2 = CleanerEngine.clean_salary("-50000")
    assert sal2 == -50000.0
    assert "negative" in err2.lower()

def test_end_to_end_pipeline():
    global_pipeline_state.reset()
    global_mock_target.reset_to_seed()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    samples_dir = os.path.join(base_dir, "data", "sample_sources")

    files = [
        {"path": os.path.join(samples_dir, "source_a_hris.csv")},
        {"path": os.path.join(samples_dir, "source_b_payroll.xlsx")},
        {"path": os.path.join(samples_dir, "source_c_crm_staff.csv")}
    ]

    # Run agent pipeline
    summary = global_agent_pipeline.run_pipeline(files)

    # 1. Multi-file Ingestion verification
    assert len(summary["sources"]) == 3
    assert summary["raw_records_count"] == 10

    # 2. Autonomous Mapping & Cleanup verification
    assert summary["cleaned_count"] > 0
    # Obvious duplicate Alice Smith (EMP-1001) in Source A & Source B should be autonomously consolidated
    emp_1001_matches = [r for r in global_pipeline_state.cleaned_records if r.get("employee_id") == "EMP-1001"]
    assert len(emp_1001_matches) == 1

    # 3. Defensible Escalation Boundary verification
    # We should have escalations for:
    # - Negative salary on EMP-1003 (Carlos Mendez)
    # - Conflicting department/salary on EMP-1006 (Fiona Gallagher)
    # - Invalid date on EMP-1008 (Hannah Abbott)
    pending_esc = summary["pending_escalations"]
    assert len(pending_esc) >= 3
    categories = [e["category"] for e in pending_esc]
    assert "DATA_CONFLICT" in categories
    assert "VALIDATION_FAILURE" in categories

    # 4. Human-In-The-Loop resolution
    # Let's resolve the negative salary escalation by approving the suggested absolute value
    salary_esc = next(e for e in pending_esc if e["field"] == "salary" and e["entity_id"] == "EMP-1003")
    initial_valid_count = summary["valid_count"]

    res = global_agent_pipeline.resolve_escalation_and_reprocess(
        escalation_id=salary_esc["id"],
        resolution_type="APPROVED_SUGGESTION",
        resolved_value=50000.0
    )
    # Record should now be valid and count should increase!
    assert res["valid_count"] == initial_valid_count + 1

    # 5. Delta Solutioning verification
    # Pre-existing target DB has EMP-1002 (Bob Johnson) with salary 125000, incoming has 138000
    # Should detect UPDATE with salary diff
    deltas = res["deltas"]
    update_deltas = [d for d in deltas if d["delta_type"] == "UPDATE" and d["entity_id"] == "EMP-1002"]
    assert len(update_deltas) == 1
    assert "salary" in update_deltas[0]["field_diffs"]

    # 6. Mock Target Push & Rollback verification
    push_res = global_agent_pipeline.push_to_target()
    assert push_res["success_count"] > 0
    tx_id = push_res["transaction_id"]

    # Target DB should contain the pushed records
    target_db = global_mock_target.get_database()
    assert "EMP-1001" in target_db

    # Rollback transaction
    rollback_res = global_agent_pipeline.rollback_push(tx_id)
    assert rollback_res["status"] == "ROLLED_BACK_SUCCESS"
    # Target DB should revert back to original seed size
    reverted_db = global_mock_target.get_database()
    assert len(reverted_db) == 1
