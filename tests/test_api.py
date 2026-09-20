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
    assert "reply" in data
    assert "EMP-1003" in data["reply"] or "Negative" in data["reply"]

