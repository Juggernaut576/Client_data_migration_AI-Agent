# Darwinbox AI Agent: Client Data Migration & Integration

An autonomous, Human-in-the-Loop (HITL) AI Data Migration Agent built for Forward Deployed Engineers and Implementation Consultants. The agent ingests heterogeneous client HR/CRM exports (CSV & Excel), autonomously maps schemas, normalizes data, respects a defensible escalation boundary, performs delta analysis, and pushes to a mock target platform with full transaction rollback support.

---

## 🌟 Key Features

1. **Multi-File Ingestion (`CSV` & `Excel`):**
   - Ingests multiple source exports representing the same entity with distinct column headers, orderings, and formats.
   - Automatically preserves source file provenance (`_source_file`, `_source_row`).

2. **Autonomous Schema Mapping & Cleaning:**
   - Heuristic and semantic mapping with confidence scoring ($0.0 - 1.0$) evaluating name similarity, aliases, and value patterns (regex, date/phone/email heuristics).
   - Autonomous sanitization: converts mixed dates (`DD/MM/YYYY`, `YYYY-MM-DD`, `12-Nov-2019`) to standard ISO 8601 (`YYYY-MM-DD`), normalizes whitespace, proper casing, and phone numbers.
   - Autonomous duplicate record consolidation across files without pestering the consultant.

3. **Defensible Escalation Boundary:**
   - Stops to request human intervention **only** when genuinely ambiguous:
     - **Schema Ambiguity:** Column header matches multiple target fields with near-equal scores or low confidence.
     - **Data Conflicts:** Duplicate records for an employee contain contradictory non-null attributes (e.g. Sales vs Operations).
     - **Constraint Violations:** Values that violate target schema constraints (e.g. negative compensation, unparseable dates).
   - Provides full context: source file, row, agent rationale, confidence score, and one-click recommended resolutions.

4. **Human-in-the-Loop (HITL) Web UI:**
   - Real-time pipeline visualizer and live KPI metrics.
   - Escalation resolution queue: **Approve Suggestion**, **Manual Override**, or **Reject Record**.
   - Side-by-side field diff viewer and immutable audit trail.

5. **Delta Solutioning:**
   - Analyzes incoming dataset against the destination Darwinbox HR database to classify records into:
     - `NEW_RECORD` (Insert)
     - `UPDATED_RECORD` (Update with field-level diffs)
     - `NO_CHANGE` (Identical data, skipped)
     - `CONFLICT` (Requires review)

6. **Mock System Integration with 1-Click Rollback:**
   - Destination Darwinbox HR API stub (`POST /api/target/employees/batch`).
   - Per-record success/failure reporting.
   - Instant transactional rollback: restores the target database to its pre-push snapshot.

---

## 🏗️ Architecture & Project Structure

```
Client_data_migration_AI-Agent/
├── backend/
│   ├── app.py                     # FastAPI application & REST endpoints
│   ├── requirements.txt           # Python dependencies
│   └── core/
│       ├── schema.py              # Target schema definition & Pydantic models
│       ├── ingestion.py           # Multi-file parser (CSV & Excel)
│       ├── mapper.py              # Semantic schema mapper & ambiguity detector
│       ├── cleaner.py             # Normalization & autonomous deduplication
│       ├── validator.py           # Schema rules & domain constraint checks
│       ├── escalation.py          # Defensible escalation boundary manager
│       ├── delta.py               # Delta solutioning engine against target state
│       ├── mock_target.py         # Mock target platform API with rollback & retry
│       └── audit.py               # Immutable transformation audit logger
├── frontend/
│   ├── index.html                 # Modern glassmorphic SPA dashboard
│   ├── style.css                  # Responsive dark-theme styling
│   └── app.js                     # Dynamic UI interactions & API bindings
├── data/
│   ├── target_schema.json         # Standard Darwinbox HR Employee Schema
│   ├── generate_samples.py        # Generator for test exports
│   └── sample_sources/
│       ├── source_a_hris.csv      # Source 1 (inconsistent dates, dirty salary)
│       ├── source_b_payroll.xlsx   # Source 2 (Excel format, duplicates, conflicting records)
│       └── source_c_crm_staff.csv # Source 3 (contractors, unparseable dates)
├── tests/
│   ├── test_pipeline.py           # Automated end-to-end pipeline tests
│   └── test_api.py                # FastAPI REST endpoint tests
├── WRITEUP.md                     # 1-Page Architectural & Escalation Philosophy Write-Up
└── README.md                      # Setup, documentation, and walkthrough guide
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.10 or higher.
- Git.

### 2. Installation
Clone the repository and install the dependencies:
```bash
# Clone repository
git clone <repository-url>
cd Client_data_migration_AI-Agent

# Install backend dependencies
python -m pip install -r backend/requirements.txt
```

### 3. Run the Application
Start the FastAPI server:
```bash
python backend/app.py
```
Or with uvicorn directly:
```bash
uvicorn backend.app:app --port 8000 --reload
```

Open your browser and navigate to:
```
http://127.0.0.1:8000/
```

---

## 🧪 Automated Testing

Run the full automated test suite covering unit, pipeline, and API tests:
```bash
python -m pytest
```

Expected output:
```
tests\test_api.py ...                                                    [ 50%]
tests\test_pipeline.py ...                                               [100%]
============================== 6 passed in ~1.3s ==============================
```

---

## 🎬 Step-by-Step Demo Walkthrough

1. **Launch Dashboard:** Open `http://127.0.0.1:8000/` in your browser.
2. **Run Sample Ingestion:**
   - Click the **"Run Sample Ingestion (3 Files)"** button.
   - The agent ingests `source_a_hris.csv`, `source_b_payroll.xlsx`, and `source_c_crm_staff.csv`.
3. **Inspect Autonomous Mappings:**
   - Switch to the **Autonomous Mappings** tab to see how source headers like `DOJ`, `ctc`, `emp_status`, and `division` were autonomously mapped to `hire_date`, `salary`, `status`, and `department` with confidence scores.
4. **Review HITL Escalation Queue:**
   - Notice the agent only escalated genuine edge cases:
     - *Carlos Mendez:* Negative salary (`-$50,000`).
     - *Fiona Gallagher:* Contradictory department (`Operations` in Payroll vs `Sales` in CRM).
     - *Hannah Abbott:* Unparseable date format (`invalid-date-format-32/99`).
   - Click **"Approve Suggestion"** on Carlos Mendez to accept the auto-suggested absolute salary (`$50,000`). Notice Carlos immediately moves into the **Valid Ready Records** pool!
   - Click **"Manual Edit"** on Fiona Gallagher to assign the confirmed department (`Engineering`).
5. **Inspect Delta Solutioning:**
   - Switch to the **Delta Solutioning & Diff** tab.
   - Observe how `Bob Johnson (EMP-1002)` is flagged as `UPDATE` with a side-by-side visual diff showing before (`$125,000`) and after (`$138,000`), while net-new employees are marked `NEW`.
6. **Push to Destination Platform & Rollback:**
   - Switch to the **Target API & Rollback** tab.
   - Click **"Push to Target Platform"**. All valid records are committed, and a transaction ID is generated (e.g. `TX-ABC1234`).
   - Inspect the live destination database table.
   - Click **"Rollback Transaction"** to test transactional safety; the destination database reverts back to its baseline snapshot.
7. **Audit Trail:**
   - Open the **Audit Trail** tab to view the immutable log of all actions, actors (`AGENT` vs `HUMAN`), timestamps, and confidence ratings.

---

## 📄 Documentation

- Refer to [WRITEUP.md](WRITEUP.md) for the 1-page writeup detailing the escalation philosophy, mathematical threshold rationale, and future roadmap.
