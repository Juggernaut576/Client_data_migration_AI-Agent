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
        return self._custom_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    @property
    def provider(self) -> str:
        key = self.api_key or ""
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

    def chat(self, user_message: str, history: List[Dict[str, str]], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conversational assistant method allowing the user to converse with the agent.
        """
        # Prepare context summary from migration state
        # Prepare context summary from migration state
        sources = state.get("sources", [])
        source_filenames = [s.get("filename", "") for s in sources]
        raw_count = state.get("raw_records_count", 0)
        valid_count = state.get("valid_count", 0)
        open_escalations = state.get("pending_escalations", [])
        delta_summary = state.get("delta_summary", {})
        deltas = state.get("deltas", [])
        push_result = state.get("push_result")
        mappings = state.get("column_mappings", {})
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
Here is your current live context:
{context_summary}

Instructions:
1. Answer the user's question directly, clearly, and concisely.
2. If asked about escalations, explain the exact reasons (e.g. negative salary, unparseable dates, conflicting departments) and what you suggest the human do.
3. If asked about delta solutioning, explain the new vs updated vs unchanged count.
4. If asked about mapping, explain the confidence score and matching approach.
5. If the user asks you to perform an action (e.g. 'run the migration', 'push to target', 'resolve'), explain that you will assist and guide them or summarize what happens when they click the corresponding action button.
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
                    "provider": self.provider
                }
            except Exception as e:
                # Fall through to conversational intent engine
                pass

        # Smart Deterministic Agent Conversational Fallback
        lower_msg = user_message.lower()

        if any(w in lower_msg for w in ["hi", "hello", "hey", "who are you", "what can you do"]):
            reply = (
                f"Hello! I am your Autonomous Data Migration AI Agent. "
                f"I handle end-to-end ingestion, schema mapping, normalization, delta detection, and target push. "
                f"Right now, pipeline status is **{status}** with **{len(open_escalations)} open escalation(s)**. "
                f"You can ask me questions like: *'Why did you escalate EMP-1003?'*, *'Summarize clean records'*, *'What are the deltas?'*, or *'Can I push to target?'*."
            )
        elif "emp-1003" in lower_msg or "emp1003" in lower_msg or "carlos" in lower_msg or "negative" in lower_msg:
            reply = (
                "**Record `EMP-1003` (Carlos Mendez)** was escalated for a critical constraint violation:\n"
                "1. **Negative Compensation**: Salary was specified as `-$50,000`, which violates the enterprise non-negative compensation constraint (`minimum: 0`).\n\n"
                "💡 **Agent Recommendation**: I paused automatic ingestion for this record. In the Escalation Queue, you can 1-click **Approve Suggestion** to convert it to positive `$50,000` or use **Manual Override** to set the verified compensation."
            )
        elif "emp-1006" in lower_msg or "emp1006" in lower_msg or "fiona" in lower_msg or "conflict" in lower_msg or "department" in lower_msg:
            reply = (
                "**Record `EMP-1006` (Fiona Gallagher)** encountered a multi-source data conflict:\n"
                "- Source B (`source_b_payroll.xlsx`): Department = `'Operations'`, Role = `'Operations Manager'`, Salary = `$105,000`\n"
                "- Source C (`source_c_crm_staff.csv`): Department = `'Sales'`, Role = `'Sales Lead'`, Salary = `$115,000`\n\n"
                "💡 **Agent Recommendation**: As an agent, I do not silently guess organizational departments or salaries. I have surfaced this conflict in the Escalation Queue so you can review and select the authoritative record."
            )
        elif "emp-1008" in lower_msg or "emp1008" in lower_msg or "hannah" in lower_msg or "date" in lower_msg:
            reply = (
                "**Record `EMP-1008` (Hannah Abbott)** was escalated due to an unparseable date:\n"
                "- Source C (`source_c_crm_staff.csv`): `date_of_joining` = `'invalid-date-format-32/99'`\n\n"
                "💡 **Agent Recommendation**: Deterministic date parsing cannot safely infer month/day for `32/99`. Please use **Manual Override** in the Escalation Queue to enter the verified start date in `YYYY-MM-DD` format."
            )
        elif "delta" in lower_msg or "diff" in lower_msg or "change" in lower_msg:
            if not deltas:
                reply = "Delta analysis has not run yet. Once you trigger the pipeline, I will compare incoming client records against existing records in the target platform database."
            else:
                new_c = delta_summary.get("new", 0)
                upd_c = delta_summary.get("update", 0)
                no_c = delta_summary.get("no_change", 0)
                conflict_c = delta_summary.get("conflict", 0)
                reply = (
                    f"**Delta Analysis Summary**:\n"
                    f"- 🟢 **New Records**: {new_c} will be inserted into the target system.\n"
                    f"- 🟡 **Updated Records**: {upd_c} have modified attributes (e.g. EMP-1002 Bob Johnson title/salary update).\n"
                    f"- ⚪ **Unchanged**: {no_c} records already match target records bit-for-bit.\n"
                    f"- 🔴 **Conflicts**: {conflict_c} require review prior to commit.\n\n"
                    f"You can view the per-field diff breakdown in the Delta Solutioning section before pushing."
                )
        elif any(w in lower_msg for w in ["push", "safe", "ready", "target"]):
            if len(open_escalations) > 0:
                reply = (
                    f"⚠️ There are still **{len(open_escalations)} unresolved escalations** in the queue. "
                    f"While the system can push the {valid_count} valid records, "
                    f"I recommend reviewing or approving the pending escalations first so no client employee is left behind."
                )
            else:
                reply = (
                    f"✅ **Ready for Push!** All {valid_count} records are valid and all escalations have been addressed. "
                    f"Click **'Synchronize to Target Platform'** to execute the transactional batch API call. "
                    f"Full rollback snapshots are enabled in case of any target rejection."
                )
        elif "map" in lower_msg or "schema" in lower_msg or "column" in lower_msg:
            reply = (
                f"**Autonomous Schema Mapping Engine**:\n"
                f"I automatically evaluated incoming column names and data types against the Target HR Schema. "
                f"Columns like `DOJ`/`date_of_joining`, `ctc`/`compensation`, and `work_phone`/`mobile` were mapped with >= 90% confidence "
                f"using Dice coefficient string similarity, target aliases, and regex value profiling."
            )
        elif "clean" in lower_msg or "normalize" in lower_msg or "fix" in lower_msg:
            reply = (
                "**Autonomous Cleanup Actions Performed**:\n"
                "1. Normalized diverse date formats (`MM/DD/YYYY`, `DD-MM-YYYY`, `DD/MM/YYYY`, `12-Nov-2019`) to standard ISO 8601 `YYYY-MM-DD`.\n"
                "2. Standardized phone numbers into clean international format (`+1-XXX-XXX-XXXX`).\n"
                "3. Trimmed stray whitespace and applied Title Casing to names and departments.\n"
                "4. Consolidated exact duplicate rows across multiple source exports into single unified entity records."
            )
        elif "rollback" in lower_msg or "undo" in lower_msg:
            reply = (
                "The Target Platform API includes **Transactional Snapshots**. If an unexpected issue occurs after pushing to the mock target system, you can trigger a 1-click **Rollback** to revert the target platform back to its pre-push state."
            )
        else:
            key_hint = ""
            if not self.is_configured():
                key_hint = "\n\n*(Note: To enable full generative LLM responses, you can set `GEMINI_API_KEY` or `OPENAI_API_KEY` in your `.env` file).* "
            reply = (
                f"I am actively monitoring the migration pipeline (Current status: **{status}**).\n\n"
                f"Here is what you can ask me:\n"
                f"- *'Why was EMP-1003 escalated?'*\n"
                f"- *'Explain the conflict on EMP-1006'*\n"
                f"- *'Show delta summary'*\n"
                f"- *'What cleaning steps did you take?'*\n"
                f"- *'Is it safe to push to target?'*{key_hint}"
            )

        return {
            "reply": reply,
            "used_llm": False,
            "provider": "local_agent"
        }

    def _call_llm(self, prompt: str) -> str:
        if self.provider == "gemini":
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
