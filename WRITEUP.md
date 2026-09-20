# Forward Deployed Engineer — AI Agent for Client Data Migration
## Executive Brief & Architectural Write-Up (1-Page)

### 1. Executive Summary & Architecture
Client enterprise data migrations frequently stall when non-technical implementation consultants are forced to manually map, clean, and reconcile hundreds of messy fields across disparate spreadsheets. This project introduces an autonomous **Client Data Migration & Integration Agent** built with a **Human-in-the-Loop (HITL)** architecture:
- **Ingestion Engine:** Unifies heterogeneous formats (`.csv`, `.xlsx`, `.xls`) preserving source file provenance.
- **Semantic Mapper:** Evaluates column header tokens, known HR/CRM aliases, and sample value heuristics (regex, date profiling, numeric parsing) to assign mapping confidence ($0.0 - 1.0$).
- **Autonomous Normalizer:** Standardizes non-destructive transforms (mixed dates $\rightarrow$ ISO 8601, whitespace, proper casing, E.164 phone numbers, and non-conflicting duplicate record consolidation).
- **Delta Solutioning Engine:** Computes state transitions against the destination Enterprise HR platform (`NEW_RECORD`, `UPDATED_RECORD`, `NO_CHANGE`, `CONFLICT`) with field-level visual diffs.
- **Mock Target Integration:** Transactional push endpoint with per-record validation, retry mechanics, and one-click rollback.

```
[Raw Client Exports (CSV/XLSX)]
             │
             ▼
   [Ingestion Engine] ──► [Semantic Schema Mapper]
                                   │ (Confidence Scoring)
             ┌─────────────────────┴─────────────────────┐
             ▼                                           ▼
[Autonomous Normalization]                   [Escalation Boundary Engine]
(Dates, Casing, Deduplication)                (Ambiguities, Conflicts, Rule Breaks)
             │                                           │
             ▼                                           ▼
  [Schema Validation]                          [HITL Supervision UI]
             │                                (Approve / Override / Reject)
             ▼                                           │
  [Delta Solutioning] ◄──────────────────────────────────┘
  (NEW, UPDATE, NOOP, CONFLICT)
             │
             ▼
[Mock Target Enterprise API] ──► [Transaction Log & Rollback]
```

---

### 2. The Defensible Escalation Boundary: Where & Why the Line is Drawn
An effective migration agent must not suffer from either extreme: **it must neither pester the consultant on every trivial field nor silently make risky assumptions that corrupt enterprise payroll or HR records.**

| Dimension | Autonomous Zone (Handled Alone) | Escalation Zone (Surfaced to Human) | Defensible Rationale |
| :--- | :--- | :--- | :--- |
| **Schema Mapping** | Match confidence $\ge 0.80$ (exact names, standard aliases like `DOJ` $\leftrightarrow$ `hire_date`, `ctc` $\leftrightarrow$ `salary`). | Match confidence $< 0.80$ or **dual-target collision** (e.g., column matches two fields with $\Delta < 0.12$). | Mapping to the wrong database column silently corrupts downstream business logic; human must clarify intent. |
| **Data Cleaning** | Deterministic syntax: standardizing `15/01/2021` or `12-Nov-2019` to `YYYY-MM-DD`, trimming whitespace, proper nouns. | Unparseable formats (e.g. `invalid-date-format-32/99`) or syntax that cannot be reliably salvaged. | Guessing an invalid date creates legal and payroll compliance liabilities. |
| **Record Deduplication** | Identical records or non-conflicting null-filling (e.g., Source A provides phone, Source B provides email). | **Contradictory values on identical key** (e.g., Fiona Gallagher has `Dept: Operations` in Payroll vs `Dept: Sales` in CRM). | A computer cannot guess which departmental hierarchy or compensation figure is current without organizational authority. |
| **Domain Constraints** | Valid values within schema limits. | Boundary violations (e.g. `Salary = -$50,000`, invalid status enum). | Violates target database integrity constraints; agent suggests absolute value or defaults, requiring human approval. |

---

### 3. Delta Solutioning on Top of AI
Data migrations are rarely greenfield; enterprise tenants often already have existing staff or active users. The **Delta Engine** compares incoming normalized records against the target system's live state prior to pushing:
1. **`NEW_RECORD` (Insert):** Net-new employee generated in target tenant.
2. **`UPDATED_RECORD` (Update):** Existing employee with field-level changes (e.g. title promotion or salary adjustment), displaying clear side-by-side Before $\rightarrow$ After diff badges.
3. **`NO_CHANGE` (Skip):** Identical record, bypassed to preserve write quotas and avoid unnecessary audit spam.
4. **`CONFLICT`:** Target system state contradicts incoming data (e.g., employee marked `INACTIVE` in target but `ACTIVE` in incoming export).

---

### 4. What We Would Build Next (Production Roadmap)
1. **Active Learning Memory Store:** Persist resolved consultant overrides in a tenant vector/relational memory so subsequent file batches automatically adopt learned client-specific mappings.
2. **Enterprise Connectors:** Add direct OAuth/API adapters for Workday, BambooHR, ADP, and Salesforce CRM alongside flat-file uploads.
3. **Automated Rollback Checkpoints & Dry-Run Mode:** Full shadow-push simulation that generates pre-migration impact reports and downloadable executive sign-off summaries.
