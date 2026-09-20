import copy
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from backend.core.audit import global_audit

class PushTransaction:
    def __init__(self, tx_id: str, timestamp: str, pre_state: Dict[str, Dict[str, Any]]):
        self.tx_id = tx_id
        self.timestamp = timestamp
        self.pre_state = pre_state
        self.records_applied: List[str] = []
        self.status = "COMMITTED"  # "COMMITTED" | "ROLLED_BACK"

class MockTargetPlatform:
    def __init__(self):
        # In-memory target HR database keyed by employee_id
        self.database: Dict[str, Dict[str, Any]] = {}
        self.transactions: Dict[str, PushTransaction] = {}
        self._seed_baseline_data()

    def _seed_baseline_data(self):
        """Seed pre-existing employee in target Darwinbox database to demonstrate Delta updates"""
        self.database = {
            "EMP-1002": {
                "employee_id": "EMP-1002",
                "first_name": "Bob",
                "last_name": "Johnson",
                "email": "bob.johnson@acme-corp.com",
                "department": "Product",
                "job_title": "Product Manager",  # Incoming file has "Lead Product Manager" -> tests UPDATE!
                "hire_date": "2020-06-01",
                "salary": 125000,                # Incoming file has 138000 -> tests salary diff!
                "status": "ACTIVE",
                "phone_number": "+15558765432"
            }
        }

    def get_database(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.database)

    def push_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        tx_id = f"TX-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Save snapshot for rollback
        pre_state = copy.deepcopy(self.database)
        transaction = PushTransaction(tx_id, timestamp, pre_state)

        results = []
        success_count = 0
        failed_count = 0

        for r in records:
            emp_id = r.get("employee_id")
            email = r.get("email")
            key = emp_id or email

            # Target API domain constraint check
            clean_rec = {k: v for k, v in r.items() if not k.startswith("_")}
            
            # Simulate failure condition if negative salary or missing mandatory key
            if not key or (clean_rec.get("salary") is not None and clean_rec.get("salary") < 0):
                failed_count += 1
                results.append({
                    "record_id": key or "UNKNOWN",
                    "status": "FAILED",
                    "status_code": 422,
                    "error": "Target validation rejected: Invalid identifier or negative compensation",
                    "data": clean_rec
                })
                continue

            # Apply record to mock Darwinbox platform
            prev_record = self.database.get(key)
            self.database[key] = clean_rec
            transaction.records_applied.append(key)
            success_count += 1

            action_type = "UPDATE" if prev_record else "INSERT"
            global_audit.record(
                action="PUSHED_TO_TARGET",
                actor="AGENT",
                entity_id=key,
                old_value=prev_record,
                new_value=clean_rec,
                reason=f"Successfully pushed ({action_type}) to target HR platform API in tx {tx_id}",
                confidence=1.0
            )

            results.append({
                "record_id": key,
                "status": "SUCCESS",
                "status_code": 200,
                "action": action_type,
                "data": clean_rec
            })

        self.transactions[tx_id] = transaction

        return {
            "transaction_id": tx_id,
            "timestamp": timestamp,
            "total_records": len(records),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results
        }

    def rollback(self, tx_id: str) -> Dict[str, Any]:
        if tx_id not in self.transactions:
            raise KeyError(f"Transaction ID {tx_id} not found in rollback log")
        
        tx = self.transactions[tx_id]
        if tx.status == "ROLLED_BACK":
            return {"status": "ALREADY_ROLLED_BACK", "transaction_id": tx_id}

        # Restore snapshot
        self.database = copy.deepcopy(tx.pre_state)
        tx.status = "ROLLED_BACK"

        global_audit.record(
            action="ROLLBACK",
            actor="HUMAN",
            reason=f"Rolled back transaction {tx_id}. Database restored to previous state.",
            confidence=1.0
        )

        return {
            "status": "ROLLED_BACK_SUCCESS",
            "transaction_id": tx_id,
            "reverted_records_count": len(tx.records_applied),
            "current_database_size": len(self.database)
        }

    def retry(self, tx_id: str, corrected_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Retry pushing corrected records"""
        return self.push_records(corrected_records)

    def reset_to_seed(self):
        self._seed_baseline_data()
        self.transactions.clear()

global_mock_target = MockTargetPlatform()
