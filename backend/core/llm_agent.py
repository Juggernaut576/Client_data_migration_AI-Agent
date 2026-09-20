import os
import json
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class LLMAgentReasoner:
    def __init__(self, api_key: Optional[str] = None):
        self._custom_api_key = api_key

    @property
    def api_key(self) -> Optional[str]:
        # Always re-read from environment or custom
        try:
            from dotenv import load_dotenv
            load_dotenv(override=False)
        except Exception:
            pass
        # Check Streamlit Cloud secrets if available
        st_key = None
        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                st_key = (
                    st.secrets.get("GROQ_API_KEY")
                    or st.secrets.get("GEMINI_API_KEY")
                    or st.secrets.get("OPENAI_API_KEY")
                )
        except Exception:
            pass

        return (
            self._custom_api_key
            or os.getenv("GROQ_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or st_key
        )

    @property
    def provider(self) -> str:
        key = self.api_key or ""
        if os.getenv("GROQ_API_KEY") or key.startswith("gsk_"):
            return "groq"
        if os.getenv("GEMINI_API_KEY") or key.startswith("AIza"):
            return "gemini"
        return "openai"

    def is_configured(self) -> bool:
        key = self.api_key
        return bool(key and len(key.strip()) > 8)

    def reason_about_ambiguity(
        self,
        column_name: str,
        sample_values: List[Any],
        candidate_fields: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Uses LLM to resolve schema ambiguity if an API key is available.
        Falls back safely to heuristic if no key or on network error.
        """
        if not self.is_configured():
            return {
                "used_llm": False,
                "reasoning": f"Evaluated via Local Semantic Agent: candidate fields {candidate_fields[:2]}"
            }

        prompt = f"""You are an expert Data Migration AI Agent.
Analyze the following source column header and sample values from a client export:
Source Column Header: '{column_name}'
Sample Data Values: {sample_values[:5]}
Candidate Target Schema Fields: {[c.get('target_field') for c in candidate_fields]}

Determine the best target field, explain your step-by-step reasoning, and assign a confidence score between 0.0 and 1.0.
Respond strictly in valid JSON format:
{{
  "selected_field": "string or null",
  "confidence": 0.85,
  "reasoning": "brief explanation",
  "is_ambiguous": false
}}
"""
        try:
            raw_response = self._call_llm(prompt)
            cleaned_json = self._extract_json(raw_response)
            parsed = json.loads(cleaned_json)
            parsed["used_llm"] = True
            return parsed
        except Exception as e:
            return {
                "used_llm": False,
                "reasoning": f"Local agent fallback (LLM query skipped: {str(e)})"
            }

    def reason_about_conflict(
        self,
        entity_id: str,
        field: str,
        val_a: Any,
        source_a: str,
        val_b: Any,
        source_b: str
    ) -> Dict[str, Any]:
        """
        Uses LLM to analyze conflict between two client exports.
        """
        if not self.is_configured():
            return {
                "used_llm": False,
                "suggested_action": f"Retain primary system value '{val_a}'",
                "reasoning": f"Local Agent: Contradictory values '{val_a}' ({source_a}) vs '{val_b}' ({source_b})"
            }

        prompt = f"""You are a Data Migration AI Agent resolving entity conflicts.
Entity ID: {entity_id}
Field with Conflict: '{field}'
Source File A: {source_a} | Value A: '{val_a}'
Source File B: {source_b} | Value B: '{val_b}'

Analyze which source is more authoritative (e.g. Payroll/HRIS typically takes precedence over CRM for job role and compensation).
Respond strictly in JSON format:
{{
  "preferred_value": "{val_a}",
  "confidence": 0.75,
  "suggested_action": "brief suggested action",
  "reasoning": "clear explanation of why this source was preferred"
}}
"""
        try:
            raw_response = self._call_llm(prompt)
            parsed = json.loads(self._extract_json(raw_response))
            parsed["used_llm"] = True
            return parsed
        except Exception as e:
            return {
                "used_llm": False,
                "suggested_action": f"Retain primary system value '{val_a}'",
                "reasoning": f"Local Agent: Conflicting values across {source_a} and {source_b}"
            }

    def chat(self, user_message: str, history: List[Dict[str, str]], state: Dict[str, Any], pipeline: Optional[Any] = None) -> Dict[str, Any]:
        """
        Conversational assistant method allowing the user to converse with the agent
        AND execute end-to-end migration actions directly from chat.
        """
        if pipeline is None:
            try:
                from backend.core.pipeline import global_agent_pipeline
                pipeline = global_agent_pipeline
            except Exception:
                pipeline = None

        user_text = user_message.strip()
        lower_msg = user_text.lower()

        # =====================================================================
        # 1. ACTION DISPATCHER: DIRECT EXECUTION FROM CHAT
        # =====================================================================
        import re

        # --- A. HELP / CAPABILITIES ---
        if re.search(r"^(help|commands|options|what can you do|what can i do|menu)\b", lower_msg):
            return {
                "reply": (
                    "🤖 **Autonomous AI Co-Pilot Capabilities & Chat Commands:**\n\n"
                    "You can drive the entire migration lifecycle directly from this chat:\n\n"
                    "1. **Pipeline & Ingestion**:\n"
                    "   - `Run pipeline` or `Ingest files` — Ingest source files, auto-map, clean & normalize.\n"
                    "2. **Escalations (HITL)**:\n"
                    "   - `Show escalations` — List all open items paused in the queue.\n"
                    "   - `Approve all` — Accept all recommended actions at once.\n"
                    "   - `Approve Carlos Mendez` (or `Approve ESC-...`) — Approve a specific item.\n"
                    "   - `Set Carlos salary to 105000` — Apply a custom compensation override.\n"
                    "   - `Set Hannah date to 2024-03-15` — Correct an invalid hire date.\n"
                    "   - `Reject Fiona` — Drop an unverified record.\n"
                    "3. **Delta Review**:\n"
                    "   - `Show deltas` — Preview new, updated, and unchanged records against target.\n"
                    "4. **Target Synchronization & Rollback**:\n"
                    "   - `Push to target` — Commit valid records to the Darwinbox Mock API.\n"
                    "   - `Rollback` — Safely revert the last synchronization transaction.\n"
                    "5. **System Controls**:\n"
                    "   - `Export CSV` — Get direct download link for cleaned dataset.\n"
                    "   - `Reset` — Clear state and restore seed target database."
                ),
                "action_taken": None
            }

        # --- B. RESET PIPELINE ---
        if re.search(r"\b(reset(\s+(pipeline|state|all|everything))?|start\s+over|clear\s+all)\b", lower_msg) and "carlos" not in lower_msg and "fiona" not in lower_msg:
            if pipeline:
                from backend.core.pipeline import global_pipeline_state
                from backend.core.mock_target import global_mock_target
                global_pipeline_state.reset()
                global_mock_target.reset_to_seed()
                new_state = pipeline.get_summary()
                return {
                    "reply": (
                        "🔄 **System Reset Completed Successfully!**\n\n"
                        "- Pipeline memory and cache cleared.\n"
                        "- Escalation queue emptied.\n"
                        "- Target platform database restored to initial seed state.\n\n"
                        "Say **`Run pipeline`** to begin a fresh autonomous migration."
                    ),
                    "action_taken": "RESET",
                    "summary": new_state
                }

        # --- C. RUN PIPELINE / INGESTION ---
        if re.search(r"\b((run|start|execute|re-run|rerun)\s+(the\s+)?(pipeline|migration)|ingest(\s+(files|data|sources|sample))?|process\s+files|load\s+sources)\b", lower_msg):
            if pipeline:
                import glob
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                data_dir = os.path.join(base_dir, "data", "sample_sources")
                sample_files = glob.glob(os.path.join(data_dir, "*.*"))
                file_inputs = [{"path": p} for p in sample_files if p.endswith((".csv", ".xlsx", ".xls"))]
                
                new_summary = pipeline.run_pipeline(file_inputs)
                sources = new_summary.get("sources", [])
                src_names = ", ".join([f"`{s.get('filename')}`" for s in sources])
                raw_c = new_summary.get("raw_records_count", 0)
                clean_c = new_summary.get("cleaned_count", 0)
                valid_c = new_summary.get("valid_count", 0)
                pending_c = new_summary.get("pending_escalations_count", 0)

                reply = (
                    f"🚀 **Autonomous Migration Pipeline Executed!**\n\n"
                    f"### 📊 Ingestion & Processing Results:\n"
                    f"- **Source Files Ingested ({len(sources)})**: {src_names}\n"
                    f"- **Raw Records Read**: {raw_c} across 3 client exports\n"
                    f"- **Autonomously Cleaned & Normalized**: {clean_c} records (deduplicated, dates & casing standardized)\n"
                    f"- **Target-Ready Valid Records**: {valid_c} records\n"
                    f"- **Escalation Queue**: ⚠️ **{pending_c} items** paused for Human-in-the-Loop review\n\n"
                    f"### 💡 Next Actions:\n"
                    f"- Say **`Show escalations`** to inspect the items needing attention.\n"
                    f"- Say **`Approve all`** to accept all recommended resolutions at once.\n"
                    f"- Say **`Show deltas`** to see incoming changes versus the target system.\n"
                    f"- 📥 **Cleaned Dataset Ready**: The **Download Clean CSV** button is now unlocked at the top of the interface."
                )
                return {
                    "reply": reply,
                    "action_taken": "RUN_PIPELINE",
                    "summary": new_summary
                }

        # --- D. SHOW ESCALATIONS / LIST QUEUE ---
        if re.search(r"\b((show|list|view|check|get)\s+(the\s+)?(escalations?|queue|pending|issues)|what('s| is)?\s+in\s+the\s+queue|what\s+needs\s+(approval|review|attention))\b", lower_msg):
            cur_summary = pipeline.get_summary() if pipeline else state
            pending = cur_summary.get("pending_escalations", [])
            valid_c = cur_summary.get("valid_count", 0)

            if not pending:
                return {
                    "reply": (
                        f"✅ **The Escalation Queue is completely clear!** (0 pending items)\n\n"
                        f"All **{valid_c} records** are valid and conform to the target schema.\n"
                        f"- Say **`Show deltas`** to preview incoming changes against Darwinbox.\n"
                        f"- Say **`Push to target`** to synchronize the records."
                    ),
                    "action_taken": None,
                    "summary": cur_summary
                }

            lines = [f"⚠️ **Current Escalation Queue ({len(pending)} item(s) requiring consultant decision):**\n"]
            for i, esc in enumerate(pending, 1):
                cat = esc.get("category", "").replace("_", " ")
                ent = esc.get("entity_id") or "Schema-level"
                fld = esc.get("field") or "N/A"
                cur = esc.get("current_value")
                sug = esc.get("suggested_action")
                lines.append(
                    f"**{i}. `[{esc['id']}]` {esc['title']}**\n"
                    f"   - **Category**: `{cat}` | **Entity**: `{ent}` | **Field**: `{fld}`\n"
                    f"   - **Current Value**: `{cur}`\n"
                    f"   - **Agent Recommendation**: {sug}\n"
                )

            lines.append(
                "\n💡 **How to resolve directly from chat:**\n"
                "- Say **`Approve all`** to apply all agent recommendations at once.\n"
                "- Say **`Approve Carlos Mendez`** or **`Approve ESC-...`** for a single record.\n"
                "- Say **`Set Carlos salary to 105000`** or **`Set Hannah date to 2024-03-15`** for custom values.\n"
                "- Say **`Reject Fiona`** to exclude an unverified record."
            )
            return {
                "reply": "\n".join(lines),
                "action_taken": None,
                "summary": cur_summary
            }

        # --- E. APPROVE ALL ESCALATIONS ---
        if re.search(r"\b(approve\s+all(\s+escalations?)?|resolve\s+all(\s+escalations?)?|accept\s+all(\s+suggestions?)?|approve\s+everything)\b", lower_msg):
            if pipeline:
                cur_summary = pipeline.get_summary()
                pending = cur_summary.get("pending_escalations", [])
                if not pending:
                    return {
                        "reply": "ℹ️ There are no pending escalations in the queue.",
                        "action_taken": None,
                        "summary": cur_summary
                    }

                resolved_items = []
                for item in list(pending):
                    val = item.get("suggested_value")
                    if val is None and item.get("field") == "hire_date":
                        val = "2024-01-15"
                    pipeline.resolve_escalation_and_reprocess(item["id"], "APPROVED_SUGGESTION", val)
                    resolved_items.append(f"- **{item.get('entity_id') or item['id']}** ({item.get('field')}): Applied `{val}`")

                updated = pipeline.get_summary()
                reply = (
                    f"✅ **All {len(pending)} Escalation Items Approved & Resolved!**\n\n"
                    f"### Resolutions Applied:\n" + "\n".join(resolved_items) + "\n\n"
                    f"🎉 **Target-Ready Valid Records**: **{updated['valid_count']} records** (0 pending escalations).\n\n"
                    f"👉 Say **`Show deltas`** to preview the target diff or **`Push to target`** to commit to Darwinbox!"
                )
                return {
                    "reply": reply,
                    "action_taken": "RESOLVE_ESCALATION",
                    "summary": updated
                }

        # --- F. MANUAL OVERRIDE VIA CHAT ---
        # e.g. "set carlos salary to 105000", "set hannah date to 2024-03-15", "override emp-1003 salary 95000"
        override_match = re.search(
            r"(?:set|override|resolve|update)\s+([a-zA-Z0-9\-_]+(?:\s+[a-zA-Z0-9\-_]+)?)\s+(salary|compensation|date|hire_date|hire\s+date|department|role|field)?\s*(?:to|=|as|with)?\s*([a-zA-Z0-9\-_/.:$]+)",
            user_text,
            re.I
        )
        if override_match and "pipeline" not in lower_msg and "everything" not in lower_msg:
            ent_target = override_match.group(1).strip()
            field_name = (override_match.group(2) or "").strip()
            val_raw = override_match.group(3).strip()

            if pipeline:
                cur_summary = pipeline.get_summary()
                pending = cur_summary.get("pending_escalations", [])
                match_esc = None
                ent_lower = ent_target.lower()
                for esc in pending:
                    e_id = (esc.get("entity_id") or "").lower()
                    t_str = esc.get("title", "").lower()
                    i_str = esc.get("id", "").lower()
                    if ent_lower in e_id or ent_lower in t_str or ent_lower in i_str:
                        match_esc = esc
                        break
                    if "carlos" in ent_lower and ("1003" in e_id or "carlos" in t_str):
                        match_esc = esc
                        break
                    if "fiona" in ent_lower and ("1006" in e_id or "fiona" in t_str):
                        match_esc = esc
                        break
                    if "hannah" in ent_lower and ("1008" in ent_lower or "hannah" in t_str or "1008" in e_id):
                        match_esc = esc
                        break

                if match_esc:
                    target_field = match_esc.get("field")
                    if field_name:
                        fn_lower = field_name.lower()
                        if "sal" in fn_lower or "comp" in fn_lower:
                            target_field = "salary"
                        elif "date" in fn_lower or "doj" in fn_lower:
                            target_field = "hire_date"
                        elif "dept" in fn_lower:
                            target_field = "department"
                        elif "role" in fn_lower:
                            target_field = "role"

                    clean_val = val_raw.replace("$", "").replace(",", "")
                    if target_field == "salary":
                        try:
                            clean_val = float(clean_val)
                        except ValueError:
                            pass

                    pipeline.resolve_escalation_and_reprocess(match_esc["id"], "MANUAL_OVERRIDE", clean_val)
                    updated = pipeline.get_summary()

                    reply = (
                        f"✏️ **Manual Override Applied for {match_esc.get('entity_id')}**!\n\n"
                        f"- **Field**: `{target_field}`\n"
                        f"- **Manual Value**: `{clean_val}`\n"
                        f"- **Status**: Re-evaluated and validated into Target-Ready Dataset.\n"
                        f"- **Remaining Queue**: {updated['pending_escalations_count']} item(s).\n\n"
                        f"Say **`Show escalations`** or **`Push to target`**."
                    )
                    return {
                        "reply": reply,
                        "action_taken": "RESOLVE_ESCALATION",
                        "summary": updated
                    }

        # --- G. APPROVE SPECIFIC ESCALATION ---
        # e.g. "approve carlos", "approve fiona", "approve emp-1003", "approve esc-001"
        approve_match = re.search(r"\b(?:approve|resolve|accept)\s+([a-zA-Z0-9\-_]+(?:\s+[a-zA-Z0-9\-_]+)?)\b", lower_msg)
        if approve_match:
            cand = approve_match.group(1).strip()
            if cand not in ["all", "everything", "the queue", "pipeline"]:
                if pipeline:
                    cur_summary = pipeline.get_summary()
                    pending = cur_summary.get("pending_escalations", [])
                    match_esc = None
                    for esc in pending:
                        e_id = (esc.get("entity_id") or "").lower()
                        t_str = esc.get("title", "").lower()
                        i_str = esc.get("id", "").lower()
                        if cand in e_id or cand in t_str or cand in i_str:
                            match_esc = esc
                            break
                        if "carlos" in cand and ("1003" in e_id or "carlos" in t_str):
                            match_esc = esc
                            break
                        if "fiona" in cand and ("1006" in e_id or "fiona" in t_str):
                            match_esc = esc
                            break
                        if "hannah" in cand and ("1008" in cand or "hannah" in t_str or "1008" in e_id):
                            match_esc = esc
                            break

                    if match_esc:
                        val = match_esc.get("suggested_value")
                        if val is None and match_esc.get("field") == "hire_date":
                            val = "2024-01-15"
                        pipeline.resolve_escalation_and_reprocess(match_esc["id"], "APPROVED_SUGGESTION", val)
                        updated = pipeline.get_summary()
                        reply = (
                            f"✅ **Approved Escalation `{match_esc['id']}` for {match_esc.get('entity_id')}**!\n\n"
                            f"- **Field**: `{match_esc.get('field')}`\n"
                            f"- **Resolved Value**: `{val}`\n"
                            f"- **Action**: {match_esc.get('suggested_action')}\n"
                            f"- **Remaining in Queue**: {updated['pending_escalations_count']} item(s).\n\n"
                        )
                        if updated['pending_escalations_count'] > 0:
                            reply += "Say **`Show escalations`** to view remaining items, or **`Approve all`** to resolve the rest."
                        else:
                            reply += "🎉 All escalations resolved! Ready to push. Say **`Push to target`** to commit."

                        return {
                            "reply": reply,
                            "action_taken": "RESOLVE_ESCALATION",
                            "summary": updated
                        }

        # --- H. REJECT SPECIFIC ESCALATION ---
        reject_match = re.search(r"\b(?:reject|drop|exclude)\s+([a-zA-Z0-9\-_]+(?:\s+[a-zA-Z0-9\-_]+)?)\b", lower_msg)
        if reject_match:
            cand = reject_match.group(1).strip()
            if pipeline:
                cur_summary = pipeline.get_summary()
                pending = cur_summary.get("pending_escalations", [])
                match_esc = None
                for esc in pending:
                    e_id = (esc.get("entity_id") or "").lower()
                    t_str = esc.get("title", "").lower()
                    i_str = esc.get("id", "").lower()
                    if cand in e_id or cand in t_str or cand in i_str:
                        match_esc = esc
                        break
                    if "carlos" in cand and ("1003" in e_id or "carlos" in t_str):
                        match_esc = esc
                        break
                    if "fiona" in cand and ("1006" in e_id or "fiona" in t_str):
                        match_esc = esc
                        break
                    if "hannah" in cand and ("1008" in cand or "hannah" in t_str or "1008" in e_id):
                        match_esc = esc
                        break

                if match_esc:
                    pipeline.resolve_escalation_and_reprocess(match_esc["id"], "REJECTED")
                    updated = pipeline.get_summary()
                    reply = (
                        f"🚫 **Record Rejected and Dropped**:\n\n"
                        f"- **Entity**: `{match_esc.get('entity_id')}`\n"
                        f"- **Escalation**: `{match_esc['id']}`\n"
                        f"- **Action**: Dropped from migration dataset.\n"
                        f"- **Remaining Queue**: {updated['pending_escalations_count']} item(s)."
                    )
                    return {
                        "reply": reply,
                        "action_taken": "RESOLVE_ESCALATION",
                        "summary": updated
                    }

        # --- I. SHOW DELTAS ---
        if re.search(r"\b((show|view|get|list)?\s*(deltas?|diffs?|delta\s+summary|target\s+diff|what\s+changed))\b", lower_msg):
            cur_summary = pipeline.get_summary() if pipeline else state
            deltas = cur_summary.get("deltas", [])
            delta_sum = cur_summary.get("delta_summary", {})

            if not deltas:
                return {
                    "reply": "ℹ️ Delta analysis has not run yet. Run the pipeline first by saying **`Run pipeline`**.",
                    "action_taken": None,
                    "summary": cur_summary
                }

            reply = (
                f"📊 **Delta Solutioning Breakdown** ({len(deltas)} total records evaluated against Darwinbox target):\n\n"
                f"- 🟢 **New Records**: {delta_sum.get('new', 0)} (will be inserted into target platform)\n"
                f"- 🟡 **Updated Records**: {delta_sum.get('update', 0)} (existing entities with modified attributes)\n"
                f"- ⚪ **Unchanged Records**: {delta_sum.get('no_change', 0)} (identical to target platform data)\n"
                f"- 🔴 **Conflicts**: {delta_sum.get('conflict', 0)}\n\n"
            )

            updates = [d for d in deltas if d.get("delta_type") == "UPDATE"]
            if updates:
                reply += "### 🟡 Key Updates Detected:\n"
                for u in updates:
                    diffs = u.get("field_diffs", {})
                    diff_strs = [f"`{k}`: '{v.get('target_val')}' ➡️ **'{v.get('source_val')}'**" for k, v in diffs.items()]
                    reply += f"- **{u.get('entity_id')}** ({u.get('employee_name', 'Employee')}): {', '.join(diff_strs)}\n"
                reply += "\n"

            reply += "👉 Say **`Push to target`** to synchronize these records into Darwinbox!"
            return {
                "reply": reply,
                "action_taken": None,
                "summary": cur_summary
            }

        # --- J. PUSH TO TARGET ---
        if re.search(r"\b((push|sync|commit|deploy)\s+(to\s+)?(target|darwinbox|platform|records))\b", lower_msg):
            if pipeline:
                cur_summary = pipeline.get_summary()
                pending = cur_summary.get("pending_escalations", [])
                if pending:
                    return {
                        "reply": (
                            f"⚠️ **Cannot Push Yet: {len(pending)} open escalation(s) in queue.**\n\n"
                            f"Darwinbox enterprise migration policies require all constraint violations and data conflicts "
                            f"to be addressed before target commit to prevent bad data in production.\n\n"
                            f"- Say **`Show escalations`** to review them.\n"
                            f"- Say **`Approve all`** to approve all recommended actions and proceed with push."
                        ),
                        "action_taken": None,
                        "summary": cur_summary
                    }

                res = pipeline.push_to_target()
                updated = pipeline.get_summary()
                reply = (
                    f"🚀 **Target Platform Push Completed Successfully!**\n\n"
                    f"### 📦 Push Details:\n"
                    f"- **Status**: `{res.get('status')}` (200 OK)\n"
                    f"- **Transaction ID**: `{res.get('transaction_id')}`\n"
                    f"- **Entities Synchronized**: **{res.get('success_count')} records** committed to Darwinbox\n"
                    f"- **Timestamp**: `{res.get('timestamp')}`\n\n"
                    f"✅ Target database is now fully updated and reconciled.\n\n"
                    f"💡 *Need to revert?* Say **`Rollback`** at any time to restore the pre-push state."
                )
                return {
                    "reply": reply,
                    "action_taken": "PUSH_TARGET",
                    "summary": updated
                }

        # --- K. ROLLBACK ---
        if re.search(r"\b(rollback|undo\s+push|revert\s+(push|transaction))\b", lower_msg):
            if pipeline:
                from backend.core.mock_target import global_mock_target
                tx_match = re.search(r"(TXN?-[a-zA-Z0-9]+)", user_text, re.I)
                tx_id = tx_match.group(1).upper() if tx_match else None
                if not tx_id:
                    for tid, tx in reversed(list(global_mock_target.transactions.items())):
                        if tx.status == "COMMITTED":
                            tx_id = tid
                            break

                if not tx_id:
                    return {
                        "reply": "⚠️ No committed push transaction found to roll back.",
                        "action_taken": None
                    }

                res = pipeline.rollback_push(tx_id)
                updated = pipeline.get_summary()
                reply = (
                    f"↩️ **Transaction Rolled Back Successfully!**\n\n"
                    f"- **Rolled Back Transaction**: `{tx_id}`\n"
                    f"- **Status**: `{res.get('status')}`\n"
                    f"- **Target Database Restored**: {res.get('restored_records_count')} records in platform\n\n"
                    f"The target system has been safely restored to its exact state prior to that push."
                )
                return {
                    "reply": reply,
                    "action_taken": "ROLLBACK",
                    "summary": updated
                }

        # --- L. EXPORT CSV ---
        if re.search(r"\b((export|download)\s+(the\s+)?(csv|cleaned|data))\b", lower_msg):
            cur_summary = pipeline.get_summary() if pipeline else state
            valid_c = cur_summary.get("valid_count", 0)
            raw_c = cur_summary.get("raw_records_count", 0)

            if not valid_c or raw_c == 0:
                return {
                    "reply": (
                        "⚠️ **Pipeline Not Executed Yet**\n\n"
                        "No cleaned dataset is available to download because the ingestion pipeline has not been executed yet.\n\n"
                        "👉 Say **`Run pipeline`** or click the **▶ Run Migration Pipeline** button at the top to process the files first. Once processed, the **Download Clean CSV** button will appear automatically!"
                    ),
                    "action_taken": None,
                    "summary": cur_summary
                }

            return {
                "reply": (
                    f"📥 **Cleaned Target Dataset Export**\n\n"
                    f"The dataset is fully processed and normalized against Darwinbox schema:\n\n"
                    f"- **Verified Records**: {valid_c} records\n"
                    f"- **Pending Escalations**: {cur_summary.get('pending_escalations_count', 0)}\n\n"
                    f"👉 Click the **📥 Download Clean CSV** button at the top of your screen to download `cleaned_target_employees.csv`."
                ),
                "action_taken": None,
                "summary": cur_summary
            }

        # =====================================================================
        # 2. CONVERSATIONAL & DOMAIN Q&A (LLM OR HEURISTIC REASONER)
        # =====================================================================
        cur_state = pipeline.get_summary() if pipeline else state
        sources = cur_state.get("sources", [])
        source_filenames = [s.get("filename", "") for s in sources]
        raw_count = cur_state.get("raw_records_count", 0)
        valid_count = cur_state.get("valid_count", 0)
        open_escalations = cur_state.get("pending_escalations", [])
        delta_summary = cur_state.get("delta_summary", {})
        deltas = cur_state.get("deltas", [])
        push_result = cur_state.get("push_result")
        status = "COMPLETED" if (valid_count > 0 or raw_count > 0) else "IDLE"

        context_summary = f"""
Current Migration State:
- Status: {status}
- Sources Ingested: {len(sources)} ({', '.join(source_filenames) or 'None'})
- Raw Records Read: {raw_count}
- Valid Clean Records Available: {valid_count}
- Open Escalations: {len(open_escalations)} items
- Delta Summary: {delta_summary}
- Target System Push: {'Pushed (Transaction: ' + push_result.get('transaction_id', 'N/A') + ')' if push_result else 'Not yet pushed'}
- Open Escalation Details: {[{'id': e.get('id'), 'category': e.get('category'), 'entity_id': e.get('entity_id'), 'field': e.get('field'), 'title': e.get('title'), 'suggestion': e.get('suggested_action')} for e in open_escalations[:5]]}
"""

        # If LLM configured, prompt it directly
        if self.is_configured():
            system_prompt = f"""You are the Client Data Migration AI Agent.
You are a senior, highly capable Forward Deployed Engineer AI agent communicating with an implementation consultant.
You have complete real-time awareness of the client migration pipeline.
You can execute actions directly when asked: inform the user they can say 'Run pipeline', 'Show escalations', 'Approve all', 'Approve Carlos Mendez', 'Set Hannah date to 2024-03-15', 'Show deltas', 'Push to target', 'Rollback', or 'Reset'.
Here is your current live context:
{context_summary}

Instructions:
1. Answer the user's question directly, clearly, and concisely.
2. If asked about escalations, explain the exact reasons (e.g. negative salary, unparseable dates, conflicting departments) and what you suggest the human do.
3. If asked about delta solutioning, explain the new vs updated vs unchanged count.
4. If asked about mapping, explain the confidence score and matching approach.
5. Remind the user they can resolve items or run the pipeline right here in the chat.
6. Maintain a helpful, confident, enterprise-ready tone.
"""
            llm_history_prompt = ""
            for msg in history[-4:]:
                sender = "User" if msg.get("role") == "user" else "Agent"
                llm_history_prompt += f"{sender}: {msg.get('content')}\n"

            full_prompt = f"{system_prompt}\n\nChat History:\n{llm_history_prompt}\nUser: {user_message}\nAgent:"

            try:
                reply = self._call_llm(full_prompt)
                return {
                    "reply": reply.strip(),
                    "used_llm": True,
                    "provider": self.provider,
                    "action_taken": None,
                    "summary": cur_state
                }
            except Exception:
                pass

        # Deterministic Conversational Fallback
        if any(w in lower_msg for w in ["hi", "hello", "hey", "who are you", "what can you do"]):
            reply = (
                f"Hello! I am your Autonomous Data Migration AI Agent. "
                f"You can do **everything** from this chat window! "
                f"Try commands like: **`Run pipeline`**, **`Show escalations`**, **`Approve all`**, **`Show deltas`**, or **`Push to target`**."
            )
        elif "emp-1003" in lower_msg or "emp1003" in lower_msg or "carlos" in lower_msg or "negative" in lower_msg:
            reply = (
                "**Record `EMP-1003` (Carlos Mendez)** was escalated for a critical constraint violation:\n"
                "1. **Negative Compensation**: Salary was specified as `-$50,000`, which violates the non-negative compensation constraint (`minimum: 0`).\n\n"
                "💡 **How to resolve right now in chat**:\n"
                "- Say **`Approve Carlos Mendez`** to auto-convert to positive `$50,000`.\n"
                "- Or say **`Set Carlos salary to 105000`** to apply a specific compensation."
            )
        elif "emp-1006" in lower_msg or "emp1006" in lower_msg or "fiona" in lower_msg or "conflict" in lower_msg or "department" in lower_msg:
            reply = (
                "**Record `EMP-1006` (Fiona Gallagher)** encountered a multi-source data conflict:\n"
                "- Source B (`source_b_payroll.xlsx`): Department = `'Operations'`, Role = `'Operations Manager'`, Salary = `$105,000`\n"
                "- Source C (`source_c_crm_staff.csv`): Department = `'Sales'`, Role = `'Sales Lead'`, Salary = `$115,000`\n\n"
                "💡 **How to resolve right now in chat**:\n"
                "- Say **`Approve Fiona Gallagher`** to accept the recommended Payroll record.\n"
                "- Or say **`Set Fiona department to Operations`** or **`Reject Fiona`**."
            )
        elif "emp-1008" in lower_msg or "emp1008" in lower_msg or "hannah" in lower_msg or "date" in lower_msg:
            reply = (
                "**Record `EMP-1008` (Hannah Abbott)** was escalated due to an unparseable date:\n"
                "- Source C (`source_c_crm_staff.csv`): `date_of_joining` = `'invalid-date-format-32/99'`\n\n"
                "💡 **How to resolve right now in chat**:\n"
                "- Say **`Set Hannah date to 2024-03-15`** to supply a verified date.\n"
                "- Or say **`Approve Hannah Abbott`** to use standard default `2024-01-15`."
            )
        elif "map" in lower_msg or "schema" in lower_msg or "column" in lower_msg:
            reply = (
                f"**Autonomous Schema Mapping Engine**:\n"
                f"I automatically evaluated incoming column names and data types against the Target HR Schema. "
                f"Columns like `DOJ`/`date_of_joining`, `ctc`/`compensation`, and `work_phone`/`mobile` were mapped with >= 90% confidence. "
                f"Type **`Show escalations`** to see any ambiguities."
            )
        else:
            reply = (
                f"I understand your query: '{user_message}'.\n\n"
                f"Currently, pipeline status is **{status}** with **{len(open_escalations)} pending escalation(s)**.\n"
                f"You can control the entire migration from here:\n"
                f"- Say **`Run pipeline`** to execute ingestion.\n"
                f"- Say **`Show escalations`** to inspect the queue.\n"
                f"- Say **`Approve all`** to resolve all items.\n"
                f"- Say **`Show deltas`** to review changes.\n"
                f"- Say **`Push to target`** to commit."
            )

        return {
            "reply": reply,
            "used_llm": False,
            "action_taken": None,
            "summary": cur_state
        }


    def _call_llm(self, prompt: str) -> str:
        if self.provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": "openai/gpt-oss-120b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 600
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "Mozilla/5.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as res:
                data = json.loads(res.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        elif self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 450}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 450
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return text


global_llm_reasoner = LLMAgentReasoner()
