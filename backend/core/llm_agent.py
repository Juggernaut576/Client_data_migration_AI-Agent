import os
import json
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional

class LLMAgentReasoner:
    def __init__(self, api_key: Optional[str] = None, provider: str = "gemini"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.provider = "gemini" if (os.getenv("GEMINI_API_KEY") or (self.api_key and self.api_key.startswith("AIza"))) else "openai"
        if api_key:
            self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

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
            # Parse json from response
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

    def _call_llm(self, prompt: str) -> str:
        if self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
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
            with urllib.request.urlopen(req, timeout=8) as res:
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
