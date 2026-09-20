from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_get_schema_api():
    response = client.get("/api/schema")
    assert response.status_code == 200
    data = response.json()
    assert data["entity"] == "Employee"
    assert "employee_id" in data["fields"]
    assert "email" in data["fields"]

def test_run_sample_and_workflow_api():
    # 1. Reset state
    res_reset = client.post("/api/target/reset")
    assert res_reset.status_code == 200

    # 2. Run sample pipeline
    res_run = client.post("/api/pipeline/run-sample")
    assert res_run.status_code == 200
    summary = res_run.json()

    assert summary["raw_records_count"] == 10
    assert len(summary["sources"]) == 3
    assert summary["pending_escalations_count"] >= 3

    # 3. Resolve an escalation item
    esc_item = summary["pending_escalations"][0]
    res_resolve = client.post("/api/escalation/resolve", json={
        "escalation_id": esc_item["id"],
        "resolution_type": "APPROVED_SUGGESTION",
        "resolved_value": esc_item["suggested_value"]
    })
    assert res_resolve.status_code == 200
    updated_summary = res_resolve.json()["summary"]
    assert updated_summary["pending_escalations_count"] == summary["pending_escalations_count"] - 1

    # 4. Push to target Darwinbox API
    res_push = client.post("/api/target/push")
    assert res_push.status_code == 200
    push_data = res_push.json()
    assert push_data["success_count"] > 0
    tx_id = push_data["transaction_id"]

    # 5. Rollback push
    res_rollback = client.post("/api/target/rollback", json={"transaction_id": tx_id})
    assert res_rollback.status_code == 200
    assert res_rollback.json()["status"] == "ROLLED_BACK_SUCCESS"

def test_index_html_served():
    res = client.get("/")
    assert res.status_code == 200
    assert "AI Data Migration & Integration" in res.text
    assert "AI Copilot Chat" in res.text

def test_chat_endpoint():
    res = client.post("/api/chat", json={
        "message": "Why was EMP-1003 Carlos Mendez escalated?",
        "history": []
    })
    assert res.status_code == 200
    data = res.json()
    assert any(w in data["reply"].lower() for w in ["carlos", "salary", "1003", "escalat"])

def test_chat_actions_end_to_end():
    # 1. Reset from chat
    res = client.post("/api/chat", json={"message": "Reset", "history": []})
    assert res.status_code == 200
    data = res.json()
    assert data["action_taken"] == "RESET"
    assert data["summary"]["raw_records_count"] == 0

    # 2. Run pipeline from chat
    res = client.post("/api/chat", json={"message": "Run pipeline", "history": []})
    assert res.status_code == 200
    data = res.json()
    assert data["action_taken"] == "RUN_PIPELINE"
    assert data["summary"]["raw_records_count"] > 0
    assert data["summary"]["pending_escalations_count"] >= 3

    # 3. Show escalations from chat
    res = client.post("/api/chat", json={"message": "Show escalations", "history": []})
    assert res.status_code == 200
    data = res.json()
    assert "Escalation Queue" in data["reply"]

    # 4. Approve specific escalation (Carlos Mendez) from chat
    res = client.post("/api/chat", json={"message": "Approve Carlos Mendez", "history": []})
    assert res.status_code == 200
    data = res.json()
    assert data["action_taken"] == "RESOLVE_ESCALATION"

    # 5. Approve all remaining from chat
    res = client.post("/api/chat", json={"message": "Approve all", "history": []})
    assert res.status_code == 200
    data = res.json()
    assert data["action_taken"] == "RESOLVE_ESCALATION"
    assert data["summary"]["pending_escalations_count"] == 0

    # 6. Show deltas from chat
    res = client.post("/api/chat", json={"message": "Show deltas", "history": []})
    assert res.status_code == 200
    data = res.json()
    assert "Delta Solutioning Breakdown" in data["reply"]

    # 7. Push to target from chat
    res = client.post("/api/chat", json={"message": "Push to target", "history": []})
    assert res.status_code == 200
    data = res.json()
    assert data["action_taken"] == "PUSH_TARGET"
    assert "Target Platform Push Completed" in data["reply"]

    # 8. Rollback push from chat
    res = client.post("/api/chat", json={"message": "Rollback", "history": []})
    assert res.status_code == 200
    data = res.json()
    assert data["action_taken"] == "ROLLBACK"
    assert "Rolled Back Successfully" in data["reply"]


def test_export_csv_only_when_processed():
    # 1. Reset state so pipeline is un-run
    client.post("/api/target/reset")

    # 2. Export attempt before pipeline run should be rejected
    res_pre = client.get("/api/export/csv")
    assert res_pre.status_code == 400
    assert "not been executed" in res_pre.json()["detail"].lower()

    # Chat attempt before pipeline run should explain it needs execution first
    chat_pre = client.post("/api/chat", json={"message": "Download clean dataset", "history": []})
    assert chat_pre.status_code == 200
    assert "not executed yet" in chat_pre.json()["reply"].lower() or "run pipeline" in chat_pre.json()["reply"].lower()

    # 3. Run pipeline to process dataset
    res_run = client.post("/api/pipeline/run-sample")
    assert res_run.status_code == 200

    # 4. Export attempt after pipeline processing should succeed
    res_post = client.get("/api/export/csv")
    assert res_post.status_code == 200
    assert "text/csv" in res_post.headers["content-type"]
    assert "employee_id" in res_post.text


