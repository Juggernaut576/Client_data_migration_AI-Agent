import os
import glob
import json
import pandas as pd
import streamlit as st

# Configure page layout
st.set_page_config(
    page_title="Enterprise AI Data Migration & Integration Suite",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

from backend.core.schema import target_schema
from backend.core.pipeline import global_agent_pipeline, global_pipeline_state
from backend.core.mock_target import global_mock_target
from backend.core.llm_agent import global_llm_reasoner

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "sample_sources")
CSS_PATH = os.path.join(BASE_DIR, "frontend", "style.css")

# Inject Google Fonts
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# Inject exact same CSS stylesheet from frontend/style.css
if os.path.exists(CSS_PATH):
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        custom_css = f.read()
    st.markdown(f"<style>{custom_css}</style>", unsafe_allow_html=True)

# Custom overrides to ensure Streamlit native elements perfectly match the frontend design
st.markdown("""
<style>
    /* Remove default Streamlit top padding and hide sidebar collapse arrow */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; max-width: 1440px !important; }
    header[data-testid="stHeader"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }

    /* Button styling to match exact frontend .btn classes */
    div.stButton > button {
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        padding: 9px 16px !important;
        border-radius: 10px !important;
        cursor: pointer !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    div.stButton > button[kind="primary"] {
        background: #4f46e5 !important;
        color: #ffffff !important;
        border-color: #4f46e5 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05) !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #4338ca !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08) !important;
    }
    div.stButton > button[kind="secondary"] {
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05) !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background: #f8fafc !important;
        border-color: #cbd5e1 !important;
    }

    /* Download button styling */
    div[data-testid="stDownloadButton"] > button {
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        padding: 9px 16px !important;
        border-radius: 10px !important;
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05) !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background: #f8fafc !important;
        border-color: #cbd5e1 !important;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid #e2e8f0; margin-bottom: 20px; }
    .stTabs [data-baseweb="tab"] { font-family: 'Inter', sans-serif; font-weight: 600; font-size: 0.88rem; color: #64748b; padding: 10px 16px; border-bottom: 2px solid transparent; }
    .stTabs [aria-selected="true"] { color: #4f46e5 !important; border-bottom-color: #4f46e5 !important; }

    /* DataFrame styling */
    div[data-testid="stDataFrame"] { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05); }
</style>
""", unsafe_allow_html=True)

# Fetch Current Pipeline Summary
summary = global_agent_pipeline.get_summary()

# PREPARE DOWNLOAD DATA FOR TOP HEADER BUTTON
valid_records = summary.get("valid_records_preview", [])
if valid_records:
    clean_df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in valid_records])
    csv_bytes = clean_df.to_csv(index=False).encode('utf-8')
elif os.path.exists(os.path.join(BASE_DIR, "data", "migrated_output", "cleaned_target_employees.csv")):
    with open(os.path.join(BASE_DIR, "data", "migrated_output", "cleaned_target_employees.csv"), "rb") as f:
        csv_bytes = f.read()
else:
    csv_bytes = b"employee_id,first_name,last_name,email,department,job_title,hire_date,salary,status,phone_number\n"

# TOP HEADER WITH IDENTICAL ACTIONS
head_col1, head_col2 = st.columns([1.8, 1.2])

with head_col1:
    st.markdown("""
    <div class="brand" style="margin-bottom: 8px;">
      <div class="brand-badge">
        <span class="brand-dot"></span>
        <span>ENTERPRISE FDE</span>
      </div>
      <div class="brand-title">
        <div class="title-row">
          <h1>AI Data Migration & Integration Suite</h1>
          <span class="version-tag">v2.4 Production</span>
        </div>
        <p class="subtitle">Autonomous Multi-Source Reconciliation &bull; Defensible Escalation Boundary &bull; Human-in-the-Loop Supervision</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

with head_col2:
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    act_col1, act_col2, act_col3 = st.columns([1.2, 1.1, 0.8])
    with act_col1:
        if st.button("▶ Run Pipeline (3 Files)", type="primary", use_container_width=True):
            sample_files = glob.glob(os.path.join(DATA_DIR, "*.*"))
            file_inputs = [{"path": p} for p in sample_files if p.endswith((".csv", ".xlsx", ".xls"))]
            with st.spinner("Processing files through autonomous pipeline..."):
                global_agent_pipeline.run_pipeline(file_inputs)
            st.rerun()
    with act_col2:
        st.download_button(
            label="📥 Download Cleaned CSV",
            data=csv_bytes,
            file_name="cleaned_target_employees.csv",
            mime="text/csv",
            use_container_width=True
        )
    with act_col3:
        if st.button("🔄 Reset", use_container_width=True):
            global_pipeline_state.reset()
            global_mock_target.reset_to_seed()
            st.rerun()

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# RENDER IDENTICAL KPI SUMMARY CARDS
st.markdown(f"""
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-icon-wrap icon-purple">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
    </div>
    <div class="kpi-content">
      <div class="kpi-label">Ingested Records</div>
      <div class="kpi-value">{summary['raw_records_count']}</div>
      <div class="kpi-meta">{len(summary['sources'])} source files loaded</div>
    </div>
  </div>

  <div class="kpi-card">
    <div class="kpi-icon-wrap icon-blue">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
    </div>
    <div class="kpi-content">
      <div class="kpi-label">Autonomous Cleans</div>
      <div class="kpi-value highlight-blue">{summary['cleaned_count']}</div>
      <div class="kpi-meta">Dates, dedupe & casing</div>
    </div>
  </div>

  <div class="kpi-card">
    <div class="kpi-icon-wrap icon-amber">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
    </div>
    <div class="kpi-content">
      <div class="kpi-label">Escalation Queue</div>
      <div class="kpi-value highlight-amber">{summary['pending_escalations_count']}</div>
      <div class="kpi-meta">Requires consultant decision</div>
    </div>
  </div>

  <div class="kpi-card">
    <div class="kpi-icon-wrap icon-emerald">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
    </div>
    <div class="kpi-content">
      <div class="kpi-label">Validated Entities</div>
      <div class="kpi-value highlight-emerald">{summary['valid_count']}</div>
      <div class="kpi-meta">Target schema compliant</div>
    </div>
  </div>

  <div class="kpi-card">
    <div class="kpi-icon-wrap icon-slate">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
    </div>
    <div class="kpi-content">
      <div class="kpi-label">Target DB Size</div>
      <div class="kpi-value">{len(summary['target_database_preview'])}</div>
      <div class="kpi-meta">Target system live state</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# RENDER IDENTICAL STEPPER TRACKER
st.markdown("""
<div class="stepper-section">
  <div class="stepper">
    <div class="step-node active">
      <div class="step-dot"></div>
      <span class="step-name">1. Ingest Sources</span>
    </div>
    <div class="step-line"></div>
    <div class="step-node active">
      <div class="step-dot"></div>
      <span class="step-name">2. Schema Mapping</span>
    </div>
    <div class="step-line"></div>
    <div class="step-node active">
      <div class="step-dot"></div>
      <span class="step-name">3. Clean & Deduplicate</span>
    </div>
    <div class="step-line"></div>
    <div class="step-node active">
      <div class="step-dot"></div>
      <span class="step-name">4. Target Validation</span>
    </div>
    <div class="step-line"></div>
    <div class="step-node active">
      <div class="step-dot"></div>
      <span class="step-name">5. Escalation Queue</span>
    </div>
    <div class="step-line"></div>
    <div class="step-node active">
      <div class="step-dot"></div>
      <span class="step-name">6. Delta Review</span>
    </div>
    <div class="step-line"></div>
    <div class="step-node">
      <div class="step-dot"></div>
      <span class="step-name">7. Target Push & Sync</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# CUSTOM MANUAL FILE UPLOAD SECTION
with st.expander("📂 Upload Custom Client Exports (.csv, .xlsx, .xls)", expanded=False):
    up_c1, up_c2 = st.columns([3, 1])
    with up_c1:
        uploaded_files = st.file_uploader(
            "Upload client files to reconcile and migrate",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )
    with up_c2:
        if uploaded_files:
            if st.button("⚡ Ingest Custom Files", type="primary", use_container_width=True):
                file_inputs = [{"filename": f.name, "content": f.read()} for f in uploaded_files]
                with st.spinner(f"Ingesting {len(uploaded_files)} files through autonomous agent..."):
                    global_agent_pipeline.run_pipeline(file_inputs)
                st.success(f"Ingested {len(uploaded_files)} custom files!")
                st.rerun()
        else:
            st.caption("Select one or more .csv / .xlsx files from your computer to run the agent.")

# TABS
tab_chat, tab_esc, tab_delta, tab_map, tab_data, tab_target, tab_audit = st.tabs([
    "💬 AI Copilot Chat",
    f"Escalation Queue ({summary['pending_escalations_count']})",
    f"Delta Solutioning ({len(summary['deltas'])})",
    "Autonomous Mappings",
    f"Ready Target Dataset ({summary['valid_count']})",
    "Target API & Rollback",
    "Audit Trail"
])

# 0. AI COPILOT CHAT
with tab_chat:
    st.markdown("""
    <div class="pane-header">
      <div>
        <h2>Autonomous Migration AI Copilot</h2>
        <p class="pane-desc">
          Converse with the Migration AI Agent in real time. Ask why specific records were escalated, inspect deltas, or query autonomous mapping decisions.
        </p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Initialize chat history in session state
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {
                "role": "assistant",
                "content": (
                    "Hello! I am your Autonomous Data Migration AI Agent. I monitor file ingestion, autonomous schema mapping, "
                    "data normalization, escalation detection, and target synchronizations.\n\n"
                    "How can I assist you with this client migration today? You can ask me why specific records were escalated, "
                    "request delta summaries, or click any of the quick prompts below."
                )
            }
        ]

    # Quick prompt buttons
    st.markdown("**Quick Prompts:**")
    qp_col1, qp_col2, qp_col3 = st.columns(3)
    quick_query = None
    with qp_col1:
        if st.button("❓ Why was EMP-1003 escalated?", key="qp1", use_container_width=True):
            quick_query = "Why was EMP-1003 Carlos Mendez escalated?"
        if st.button("📊 Show Delta Summary", key="qp2", use_container_width=True):
            quick_query = "Show me the Delta Solutioning summary"
    with qp_col2:
        if st.button("⚡ Explain EMP-1006 Conflict", key="qp3", use_container_width=True):
            quick_query = "Explain the data conflict on EMP-1006 Fiona Gallagher"
        if st.button("🧹 What was cleaned?", key="qp4", use_container_width=True):
            quick_query = "What cleaning steps were performed autonomously?"
    with qp_col3:
        if st.button("⚠️ Why did EMP-1008 fail?", key="qp5", use_container_width=True):
            quick_query = "Why did EMP-1008 Hannah Abbott fail validation?"
        if st.button("🚀 Can I push to target?", key="qp6", use_container_width=True):
            quick_query = "Is it safe to push to the target platform now?"

    # Display chat messages
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask the agent anything about this migration...")
    active_prompt = quick_query or user_input

    if active_prompt:
        st.session_state["chat_history"].append({"role": "user", "content": active_prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(active_prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Agent analyzing migration context..."):
                response = global_llm_reasoner.chat(
                    user_message=active_prompt,
                    history=st.session_state["chat_history"][-6:],
                    state=summary
                )
                reply = response.get("reply", "I processed your request.")
                st.markdown(reply)
                st.session_state["chat_history"].append({"role": "assistant", "content": reply})
        if quick_query:
            st.rerun()

# 1. ESCALATION QUEUE (HITL)
with tab_esc:
    st.markdown("""
    <div class="pane-header">
      <div>
        <h2>Human-in-the-Loop Escalation Queue</h2>
        <p class="pane-desc">
          The agent operates autonomously for standard operations and escalates <strong>only</strong> when encountering low-confidence schema mapping, contradictory multi-source attributes, or unresolvable domain constraint violations.
        </p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    pending = summary["pending_escalations"]
    if not pending:
        st.markdown("""
        <div class="empty-state">
          <div class="empty-icon">✓</div>
          <h3>No Pending Escalations</h3>
          <p>All records conform safely to schema or have been resolved by consultant.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for esc in pending:
            tag_class = "tag-ambiguity"
            if esc["category"] == "DATA_CONFLICT": tag_class = "tag-conflict"
            elif esc["category"] == "VALIDATION_FAILURE": tag_class = "tag-validation"

            st.markdown(f"""
            <div class="escalation-card" style="margin-bottom: 12px;">
              <div>
                <div class="esc-header">
                  <span class="esc-tag {tag_class}">{esc['category'].replace('_', ' ')}</span>
                  <span class="esc-meta">Confidence: {esc['confidence_score']*100:.0f}%</span>
                </div>
                <h3 class="esc-title">{esc['title']}</h3>
                <p class="esc-meta">{f"Source: {esc.get('source_file')}" if esc.get('source_file') else ''} &bull; Entity: <code>{esc.get('entity_id') or 'N/A'}</code></p>
                
                <div class="esc-context-box">
                  <div class="esc-context-row">
                    <span style="color: #64748b;">Target Field:</span>
                    <strong>{esc.get('field') or 'N/A'}</strong>
                  </div>
                  <div class="esc-context-row">
                    <span style="color: #64748b;">Current Raw Value:</span>
                    <code style="color: #be123c;">{esc.get('current_value')}</code>
                  </div>
                  <div class="esc-context-row">
                    <span style="color: #64748b;">Suggested Action:</span>
                    <span style="color: #047857; font-weight: 600;">{esc.get('suggested_action')}</span>
                  </div>
                </div>

                <div class="esc-reasoning">
                  <strong>Agent Reasoning:</strong> {esc['agent_reasoning']}
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            col_a, col_b, col_c = st.columns([1.5, 2.5, 1])
            with col_a:
                if st.button("✓ Approve Suggestion", key=f"app_{esc['id']}", type="primary", use_container_width=True):
                    global_agent_pipeline.resolve_escalation_and_reprocess(
                        escalation_id=esc["id"],
                        resolution_type="APPROVED_SUGGESTION",
                        resolved_value=esc["suggested_value"]
                    )
                    st.rerun()
            with col_b:
                override_input = st.text_input("Override value", value=str(esc["suggested_value"] or ""), key=f"in_{esc['id']}", label_visibility="collapsed")
                if st.button("Apply Manual Override", key=f"btn_ovr_{esc['id']}", use_container_width=True):
                    global_agent_pipeline.resolve_escalation_and_reprocess(
                        escalation_id=esc["id"],
                        resolution_type="MANUAL_OVERRIDE",
                        resolved_value=override_input
                    )
                    st.rerun()
            with col_c:
                if st.button("✕ Reject", key=f"btn_rej_{esc['id']}", use_container_width=True):
                    global_agent_pipeline.resolve_escalation_and_reprocess(
                        escalation_id=esc["id"],
                        resolution_type="REJECTED"
                    )
                    st.rerun()
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

# 2. DELTA SOLUTIONING
with tab_delta:
    tally = summary["delta_summary"]
    st.markdown(f"""
    <div class="pane-header">
      <div>
        <h2>Delta Solutioning Engine</h2>
        <p class="pane-desc">Diffs normalized records against destination target platform state to prevent redundant updates prior to commit.</p>
      </div>
      <div class="delta-tally">
        <span class="pill pill-green">New: <strong>{tally.get('new', 0)}</strong></span>
        <span class="pill pill-blue">Updates: <strong>{tally.get('update', 0)}</strong></span>
        <span class="pill pill-gray">No Change: <strong>{tally.get('no_change', 0)}</strong></span>
        <span class="pill pill-red">Conflicts: <strong>{tally.get('conflict', 0)}</strong></span>
      </div>
    </div>
    """, unsafe_allow_html=True)

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
    st.markdown("""
    <div class="pane-header">
      <div>
        <h2>Autonomous Schema Field Mappings</h2>
        <p class="pane-desc">Source-to-target field associations proposed via semantic similarity, synonym matching, and statistical data profiling.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

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
    st.markdown("""
    <div class="pane-header">
      <div>
        <h2>Target Entity Dataset (Cleaned & Validated)</h2>
        <p class="pane-desc">Consolidated entities conforming to target specification ready for destination synchronization.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if valid_records:
        st.dataframe(clean_df, use_container_width=True)
    else:
        st.info("No validated records loaded yet. Run the pipeline above.")

# 5. TARGET API & ROLLBACK
with tab_target:
    st.markdown("""
    <div class="pane-header">
      <div>
        <h2>Target Enterprise Platform Integration</h2>
        <p class="pane-desc">Execute the batch commit step to the destination REST API, monitor record-level responses, or perform transactional rollback.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    c_btn, c_res = st.columns([1, 2])
    with c_btn:
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

    st.markdown("#### Live Destination Database State")
    db_data = summary.get("target_database_preview", [])
    if db_data:
        st.dataframe(pd.DataFrame(db_data), use_container_width=True)
    else:
        st.info("Target database is empty.")

# 6. AUDIT TRAIL
with tab_audit:
    st.markdown("""
    <div class="pane-header">
      <div>
        <h2>Transformation Audit Trail</h2>
        <p class="pane-desc">Immutable verification log tracking every autonomous modification, merge, and consultant intervention.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    audit_entries = summary.get("audit_trail", [])
    if audit_entries:
        audit_df = pd.DataFrame(audit_entries)
        st.dataframe(audit_df[["timestamp", "actor", "action", "entity_id", "field", "reason"]], use_container_width=True)
    else:
        st.info("No audit entries recorded yet.")
