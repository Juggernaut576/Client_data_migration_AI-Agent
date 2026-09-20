import os
import glob
import json
import pandas as pd
import streamlit as st

# Configure page layout
st.set_page_config(
    page_title="AI Data Migration & Integration Suite",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

from backend.core.schema import target_schema
from backend.core.pipeline import global_agent_pipeline, global_pipeline_state
from backend.core.mock_target import global_mock_target

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "sample_sources")

# Custom CSS for polished enterprise look
st.markdown("""
<style>
    .main-title { font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.2rem; }
    .subtitle { color: #8892b0; font-size: 0.95rem; margin-bottom: 1.5rem; }
    .status-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem; }
    .tag-conflict { background: rgba(244, 63, 94, 0.15); color: #fda4af; border: 1px solid rgba(244, 63, 94, 0.3); }
    .tag-validation { background: rgba(245, 158, 11, 0.15); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.3); }
    .tag-ambiguity { background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.3); }
    .diff-before { background: rgba(244, 63, 94, 0.2); color: #fca5a5; text-decoration: line-through; padding: 2px 6px; border-radius: 4px; }
    .diff-after { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; padding: 2px 6px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⚡ AI Data Migration & Integration Suite</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Autonomous Multi-Source Reconciliation &bull; Defensible Escalation Boundary &bull; Human-in-the-Loop Supervision</div>', unsafe_allow_html=True)

# SIDEBAR CONTROLS
with st.sidebar:
    st.header("Migration Control")
    st.info("Ingest client raw files (CSV & Excel) and run autonomous mapping & cleaning pipeline.")
    
    if st.button("🚀 Run Pipeline (3 Sample Files)", use_container_width=True, type="primary"):
        sample_files = glob.glob(os.path.join(DATA_DIR, "*.*"))
        file_inputs = [{"path": p} for p in sample_files if p.endswith((".csv", ".xlsx", ".xls"))]
        with st.spinner("Processing files through autonomous pipeline..."):
            global_agent_pipeline.run_pipeline(file_inputs)
        st.success("Ingestion & reconciliation complete!")
        st.rerun()

    uploaded_files = st.file_uploader("Or Upload Custom Client Exports (.csv, .xlsx)", accept_multiple_files=True)
    if uploaded_files and st.button("Ingest Uploaded Files", use_container_width=True):
        file_inputs = [{"filename": f.name, "content": f.read()} for f in uploaded_files]
        with st.spinner("Processing custom uploads..."):
            global_agent_pipeline.run_pipeline(file_inputs)
        st.success("Uploaded files processed!")
        st.rerun()

    st.markdown("---")
    if st.button("🔄 Reset Target State", use_container_width=True):
        global_pipeline_state.reset()
        global_mock_target.reset_to_seed()
        st.info("State reset to initial seed.")
        st.rerun()

# FETCH CURRENT SUMMARY
summary = global_agent_pipeline.get_summary()

# METRICS BAR
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Ingested Records", summary["raw_records_count"], f"{len(summary['sources'])} files")
col2.metric("Autonomous Cleans", summary["cleaned_count"], "Dates, casing, dedupe")
col3.metric("Escalation Queue", summary["pending_escalations_count"], "Requires review")
col4.metric("Validated Entities", summary["valid_count"], "Target compliant")
col5.metric("Target DB Size", len(summary["target_database_preview"]), "Live destination")

st.markdown("---")

# MAIN TABS
tab_esc, tab_delta, tab_map, tab_data, tab_target, tab_audit = st.tabs([
    f"⚠️ Escalation Queue ({summary['pending_escalations_count']})",
    f"🔄 Delta Solutioning ({len(summary['deltas'])})",
    "🗺️ Schema Mappings",
    f"📋 Ready Target Dataset ({summary['valid_count']})",
    "🎯 Target API & Rollback",
    "📜 Audit Trail"
])

# 1. ESCALATION QUEUE (HITL)
with tab_esc:
    st.subheader("Human-in-the-Loop Escalation Queue")
    st.write("The agent pauses **only** when confidence is low or conflicting source data makes autonomous resolution unsafe.")

    pending = summary["pending_escalations"]
    if not pending:
        st.success("✅ No pending escalations. All records conform safely to schema or have been resolved.")
    else:
        for esc in pending:
            category_color = "tag-ambiguity"
            if esc["category"] == "DATA_CONFLICT": category_color = "tag-conflict"
            elif esc["category"] == "VALIDATION_FAILURE": category_color = "tag-validation"

            with st.expander(f"**[{esc['category']}]** {esc['title']} — Entity: `{esc.get('entity_id') or 'N/A'}`", expanded=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"**Target Field:** `{esc.get('field') or 'N/A'}`")
                    st.markdown(f"**Source File:** `{esc.get('source_file')}`")
                    st.markdown(f"**Current Raw Value:** `{esc.get('current_value')}`")
                    st.info(f"**Agent Reasoning:** {esc['agent_reasoning']}")
                with c2:
                    st.markdown(f"**Confidence Score:** `{esc['confidence_score'] * 100:.0f}%`")
                    st.markdown(f"**Recommended Action:** {esc['suggested_action']}")
                    
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        if st.button("Approve", key=f"app_{esc['id']}", type="primary"):
                            global_agent_pipeline.resolve_escalation_and_reprocess(
                                escalation_id=esc["id"],
                                resolution_type="APPROVED_SUGGESTION",
                                resolved_value=esc["suggested_value"]
                            )
                            st.rerun()
                    with b2:
                        override_val = st.text_input("Override", value=str(esc["suggested_value"] or ""), key=f"txt_{esc['id']}", label_visibility="collapsed")
                        if st.button("Apply", key=f"ovr_{esc['id']}"):
                            global_agent_pipeline.resolve_escalation_and_reprocess(
                                escalation_id=esc["id"],
                                resolution_type="MANUAL_OVERRIDE",
                                resolved_value=override_val
                            )
                            st.rerun()
                    with b3:
                        if st.button("Reject", key=f"rej_{esc['id']}"):
                            global_agent_pipeline.resolve_escalation_and_reprocess(
                                escalation_id=esc["id"],
                                resolution_type="REJECTED"
                            )
                            st.rerun()

# 2. DELTA SOLUTIONING
with tab_delta:
    st.subheader("Delta Solutioning Engine")
    st.write("Diffs incoming records against destination target database state prior to commit.")
    
    tally = summary["delta_summary"]
    st.markdown(f"**Summary:** `New: {tally.get('new', 0)}` | `Updates: {tally.get('update', 0)}` | `No Change: {tally.get('no_change', 0)}` | `Conflicts: {tally.get('conflict', 0)}`")

    deltas = summary["deltas"]
    if deltas:
        delta_rows = []
        for d in deltas:
            inc = d.get("incoming_data", {})
            diff_text = "; ".join([f"{k}: {v.get('before')} -> {v.get('after')}" for k, v in d.get("field_diffs", {}).items()]) or "Identical"
            delta_rows.append({
                "Entity ID": d.get("entity_id"),
                "Delta Operation": d.get("delta_type"),
                "Employee Name": f"{inc.get('first_name', '')} {inc.get('last_name', '')}",
                "Department": inc.get("department", "-"),
                "Field Level Diffs": diff_text
            })
        st.dataframe(pd.DataFrame(delta_rows), use_container_width=True)
    else:
        st.info("Run the ingestion pipeline to view delta analysis.")

# 3. SCHEMA MAPPINGS
with tab_map:
    st.subheader("Autonomous Schema Mappings")
    st.write("Columns mapped autonomously via semantic similarity, alias ontology, and sample value profiling.")

    mappings_by_file = summary.get("column_mappings", {})
    if mappings_by_file:
        for fname, maps in mappings_by_file.items():
            st.markdown(f"#### Source File: `{fname}`")
            rows = []
            for col, m in maps.items():
                rows.append({
                    "Source Header": col,
                    "Target Field": m.get("target_field"),
                    "Confidence": f"{m.get('confidence', 0)*100:.0f}%",
                    "Rationale": m.get("reasoning")
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("Run the ingestion pipeline to view schema mappings.")

# 4. READY TARGET DATASET
with tab_data:
    st.subheader("Target Entity Dataset (Cleaned & Validated)")
    st.write("Consolidated entities conforming to target specification ready for destination synchronization.")

    valid_records = summary.get("valid_records_preview", [])
    if valid_records:
        clean_df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in valid_records])
        st.dataframe(clean_df, use_container_width=True)

        # 1-Click CSV Download
        csv_bytes = clean_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Cleaned CSV",
            data=csv_bytes,
            file_name="cleaned_target_employees.csv",
            mime="text/csv",
            type="primary"
        )
    else:
        st.info("No validated records loaded yet. Run the pipeline above.")

# 5. TARGET API & ROLLBACK
with tab_target:
    st.subheader("Target Enterprise Platform Integration")
    st.write("Execute batch commit to destination target API, view per-record results, or trigger transactional rollback.")

    col_btn, col_res = st.columns([1, 2])
    with col_btn:
        if st.button("🚀 Synchronize to Target Platform", type="primary", use_container_width=True):
            res = global_agent_pipeline.push_to_target()
            st.success(f"Push committed! Transaction ID: {res['transaction_id']}")
            st.rerun()

    push_res = summary.get("push_result")
    if push_res:
        st.markdown(f"**Last Transaction:** `{push_res.get('transaction_id')}` | **Success:** `{push_res.get('success_count')}` | **Failed:** `{push_res.get('failed_count')}`")
        if st.button("↩️ Rollback Last Transaction"):
            rb_res = global_agent_pipeline.rollback_push(push_res["transaction_id"])
            st.warning(f"Rollback status: {rb_res.get('status')}. Reverted {rb_res.get('reverted_records_count')} records.")
            st.rerun()

    st.markdown("#### Live Target Platform Database")
    db_data = summary.get("target_database_preview", [])
    if db_data:
        st.dataframe(pd.DataFrame(db_data), use_container_width=True)
    else:
        st.info("Target database is empty.")

# 6. AUDIT TRAIL
with tab_audit:
    st.subheader("Transformation Audit Trail")
    st.write("Immutable verification log tracking every autonomous modification, merge, and consultant intervention.")

    audit_entries = summary.get("audit_trail", [])
    if audit_entries:
        audit_df = pd.DataFrame(audit_entries)
        st.dataframe(audit_df[["timestamp", "actor", "action", "entity_id", "field", "reason"]], use_container_width=True)
    else:
        st.info("No audit entries recorded yet.")
