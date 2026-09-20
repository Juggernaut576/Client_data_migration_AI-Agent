# Enterprise AI Agent: Client Data Migration & Integration

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://clientdatamigrationai-agent-k3fa94duqoj5hhskk945kx.streamlit.app/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-8%20passed-brightgreen.svg)]()

> 🌐 **Live Cloud Deployment**: [https://clientdatamigrationai-agent-k3fa94duqoj5hhskk945kx.streamlit.app/](https://clientdatamigrationai-agent-k3fa94duqoj5hhskk945kx.streamlit.app/)

An autonomous, Human-in-the-Loop (HITL) AI Data Migration Agent built for Forward Deployed Engineers and Implementation Consultants. The agent ingests heterogeneous client HR/CRM exports (CSV & Excel), autonomously maps schemas, normalizes data, respects a defensible escalation boundary, performs delta analysis, and pushes to a mock target platform with full transaction rollback support.

---

## 🚀 Live Cloud Deployment & Quick Demo

Access the live cloud deployment on Streamlit Community Cloud:
👉 **[https://clientdatamigrationai-agent-k3fa94duqoj5hhskk945kx.streamlit.app/](https://clientdatamigrationai-agent-k3fa94duqoj5hhskk945kx.streamlit.app/)**

You can drive the **entire migration lifecycle** directly through conversational chat commands:

| Step | What to Type in Chat | Action Performed |
| :--- | :--- | :--- |
| **1. Ingest & Reconcile** | `Run pipeline` | Ingests CSVs & Excel, performs schema mapping, cleans, deduplicates, and reports KPIs. |
| **2. Inspect Escalations** | `Show escalations` | Lists open queue items with entity IDs, error reasons, and recommended fixes. |
| **3. Approve All** | `Approve all` | Resolves all pending escalations using defensible agent recommendations. |
| **4. Manual Override** | `Set Carlos salary to 105000` | Re-evaluates record with your custom value and moves it to the valid pool. |
| **5. Delta Solutioning** | `Show deltas` | Previews new vs. updated records (with field-level diffs like Bob Johnson's salary update). |
| **6. Target Sync** | `Push to target` | Commits all validated records to Darwinbox with an immutable transaction ID. |
| **7. Instant Rollback** | `Rollback` | Reverts the target database to its exact snapshot before that transaction. |
| **8. Reset** | `Reset` | Restores memory and target database back to seed state. |
| **9. Export Data** | `Export CSV` | Generates a direct download link for `cleaned_target_employees.csv`. |

---

## 🌟 Key Architectural Pillars

1. **Multi-File Ingestion (`CSV` & `Excel`):**
   - Ingests multiple source exports representing the same entity with distinct column headers, orderings, and formats.
   - Automatically preserves source file provenance (`_source_file`, `_source_row`).
   - Supports arbitrary number of files simultaneously.

2. **Autonomous Schema Mapping & Cleaning:**
   - Heuristic and semantic mapping with confidence scoring ($0.0 - 1.0$) evaluating name similarity, aliases, and value patterns.
   - Autonomous sanitization: converts mixed dates (`DD/MM/YYYY`, `YYYY-MM-DD`, `12-Nov-2019`) to standard ISO 8601 (`YYYY-MM-DD`), normalizes whitespace, proper casing, and phone numbers.
   - Autonomous duplicate record consolidation across files.

3. **Defensible Escalation Boundary:**
   - Stops to request human intervention **only** when genuinely ambiguous:
     - **Schema Ambiguity:** Column header matches multiple target fields with near-equal scores.
     - **Data Conflicts:** Duplicate records for an employee contain contradictory non-null attributes (e.g. Sales vs Operations).
     - **Constraint Violations:** Values that violate target schema constraints (e.g. negative compensation, unparseable dates).
   - Provides full context: source file, row, agent rationale, confidence score, and one-click recommended resolutions.

4. **Human-in-the-Loop (HITL) Unified AI Copilot UI:**
   - Interactive chat window with real-time smooth auto-scrolling on response generation.
   - Live KPI status cards and expandable raw data inspector for table/audit reviews.

5. **Delta Solutioning:**
   - Analyzes incoming dataset against the destination HR database to classify records into:
     - `NEW_RECORD` (Insert)
     - `UPDATED_RECORD` (Update with field-level diffs)
     - `NO_CHANGE` (Identical data, skipped)
     - `CONFLICT` (Requires review)

6. **Mock System Integration with 1-Click Rollback:**
   - Destination HR API stub (`POST /api/target/employees/batch`).
   - Per-record success/failure reporting.
   - Instant transactional rollback: restores the target database to its pre-push snapshot.

---

## 🏗️ Architecture & Project Structure

```
Client_data_migration_AI-Agent/
├── streamlit_app.py               # Streamlit application (Cloud Deployment entrypoint)
├── requirements.txt               # Dependencies for Streamlit Cloud & local execution
├── backend/
│   ├── app.py                     # FastAPI application & REST endpoints
│   └── core/
│       ├── schema.py              # Target schema definition & Pydantic models
│       ├── ingestion.py           # Multi-file parser (CSV & Excel)
│       ├── mapper.py              # Semantic schema mapper & ambiguity detector
│       ├── cleaner.py             # Normalization & autonomous deduplication
│       ├── validator.py           # Schema rules & domain constraint checks
│       ├── escalation.py          # Defensible escalation boundary manager
│       ├── delta.py               # Delta solutioning engine against target state
│       ├── mock_target.py         # Mock target platform API with rollback & retry
│       ├── llm_agent.py           # Conversational Agentic Copilot & Groq LLM reasoner
│       └── audit.py               # Immutable transformation audit logger
├── data/
│   ├── sample_sources/            # Raw client files (CSV & XLSX)
│   └── migrated_output/           # Cleaned output CSV & persistent audit logs
├── frontend/                      # Standalone Web Client (HTML/CSS/JS)
└── tests/                         # Full automated test suite (8 tests)
```

---

## 💻 Local Setup & Execution

### 1. Clone & Install
```bash
git clone https://github.com/Juggernaut576/Client_data_migration_AI-Agent.git
cd Client_data_migration_AI-Agent
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Variables (Optional for LLM)
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=gsk_your_groq_api_key
```
*(If no API key is provided, the agent seamlessly uses its built-in local deterministic semantic reasoner).*

### 3. Run the Applications
- **Streamlit App (Recommended)**:
  ```bash
  streamlit run streamlit_app.py
  ```
  Open `http://localhost:8501`.

- **FastAPI Backend + Web SPA**:
  ```bash
  uvicorn backend.app:app --reload --port 8000
  ```
  Open `http://127.0.0.1:8000/`.

---

## 🧪 Automated Testing

Run the full automated test suite covering unit, pipeline, and conversational API tests:
```bash
python -m pytest tests
```

Output:
```
======================== 8 passed, 1 warning in ~2.5s =========================
```

---

## ☁️ Streamlit Community Cloud Configuration

When deploying on [Streamlit Community Cloud](https://share.streamlit.io):
1. **Repository**: `Juggernaut576/Client_data_migration_AI-Agent`
2. **Branch**: `master`
3. **Main file path**: `streamlit_app.py`
4. **Secrets** (under *Advanced settings*):
   ```toml
   GROQ_API_KEY = "gsk_your_key_here"
   ```
   The agent automatically reads credentials from `st.secrets` in the cloud environment.
