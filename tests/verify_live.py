import urllib.request
import json

url = "http://127.0.0.1:8000/api/pipeline/run-sample"
req = urllib.request.Request(url, method="POST")
with urllib.request.urlopen(req) as res:
    data = json.loads(res.read().decode("utf-8"))

print(f"=== LIVE AGENT INGESTION RESULTS ===")
print(f"Total Raw Records Ingested: {data['raw_records_count']}")
print(f"Source Files Read: {[s['filename'] for s in data['sources']]}")
print(f"Autonomously Cleaned Count: {data['cleaned_count']}")
print(f"Valid Ready Records Count: {data['valid_count']}")
print(f"Pending Escalation Count: {data['pending_escalations_count']}")

print(f"\n=== MAPPINGS GENERATED PER FILE ===")
for filename, mappings in data['column_mappings'].items():
    print(f"\nFile: {filename}")
    for col, m in mappings.items():
        print(f"  {col:16} -> {str(m['target_field']):16} (Confidence: {m['confidence']:.2f}) | {m['reasoning']}")

print(f"\n=== ESCALATIONS FLAGGED TO HUMAN ===")
for esc in data['pending_escalations']:
    print(f"[{esc['category']}] {esc['title']}")
    print(f"   Context: File={esc.get('source_file')} | Current Value={esc.get('current_value')}")
    print(f"   Reasoning: {esc['agent_reasoning']}")
    print(f"   Suggested Fix: {esc['suggested_action']}\n")

print(f"=== DELTA SUMMARY AGAINST TARGET DATABASE ===")
print(json.dumps(data['delta_summary'], indent=2))

# Test resolving Carlos Mendez's negative salary escalation live
sal_esc = next((e for e in data['pending_escalations'] if e['field'] == 'salary' and e['entity_id'] == 'EMP-1003'), None)
if sal_esc:
    print(f"\n=== TESTING LIVE RESOLUTION ===")
    print(f"Resolving {sal_esc['id']} for Carlos Mendez (Negative Salary)...")
    res_req = urllib.request.Request(
        'http://127.0.0.1:8000/api/escalation/resolve',
        data=json.dumps({'escalation_id': sal_esc['id'], 'resolution_type': 'APPROVED_SUGGESTION', 'resolved_value': 50000.0}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(res_req) as res_response:
        res_data = json.loads(res_response.read().decode('utf-8'))
        print(f"Resolution Successful! Valid Ready Records count increased to: {res_data['summary']['valid_count']}")

# Test pushing to target Darwinbox API
print(f"\n=== TESTING MOCK TARGET API PUSH ===")
push_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/target/push',
    data=b'{}',
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(push_req) as push_response:
    push_data = json.loads(push_response.read().decode('utf-8'))
    print(f"Committed Transaction ID: {push_data['transaction_id']}")
    print(f"Success Count: {push_data['success_count']} / {push_data['total_records']}")
    print(f"Failed Count: {push_data['failed_count']}")

# Test 1-click Rollback
print(f"\n=== TESTING TRANSACTION ROLLBACK ===")
tx_id = push_data['transaction_id']
rb_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/target/rollback',
    data=json.dumps({'transaction_id': tx_id}).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(rb_req) as rb_response:
    rb_data = json.loads(rb_response.read().decode('utf-8'))
    print(f"Rollback Status: {rb_data['status']}")
    print(f"Reverted Records Count: {rb_data['reverted_records_count']}")
    print(f"Target Database Restored to Seed Size: {rb_data['current_database_size']}")

