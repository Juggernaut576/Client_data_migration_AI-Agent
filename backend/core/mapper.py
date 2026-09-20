import re
from typing import Dict, List, Optional, Tuple, Any
from backend.core.schema import TargetSchema, FieldDefinition

class MappingProposal:
    def __init__(
        self,
        source_column: str,
        target_field: Optional[str],
        confidence: float,
        reasoning: str,
        is_ambiguous: bool = False,
        candidate_fields: Optional[List[Dict[str, Any]]] = None
    ):
        self.source_column = source_column
        self.target_field = target_field
        self.confidence = round(confidence, 2)
        self.reasoning = reasoning
        self.is_ambiguous = is_ambiguous
        self.candidate_fields = candidate_fields or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_column": self.source_column,
            "target_field": self.target_field,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "is_ambiguous": self.is_ambiguous,
            "candidate_fields": self.candidate_fields
        }

class SchemaMapper:
    def __init__(self, schema: TargetSchema, confidence_threshold: float = 0.75):
        self.schema = schema
        self.confidence_threshold = confidence_threshold

    @staticmethod
    def _normalize_string(text: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]", "", text).lower()

    @staticmethod
    def _string_similarity(a: str, b: str) -> float:
        norm_a = re.sub(r"[^a-zA-Z0-9]", "", a).lower()
        norm_b = re.sub(r"[^a-zA-Z0-9]", "", b).lower()
        if not norm_a or not norm_b:
            return 0.0
        if norm_a == norm_b:
            return 1.0
        if norm_a in norm_b or norm_b in norm_a:
            return 0.85
        # Bigram Dice coefficient
        pairs_a = {norm_a[i:i+2] for i in range(len(norm_a)-1)}
        pairs_b = {norm_b[i:i+2] for i in range(len(norm_b)-1)}
        if not pairs_a or not pairs_b:
            return 0.0
        intersection = len(pairs_a.intersection(pairs_b))
        return (2.0 * intersection) / (len(pairs_a) + len(pairs_b))

    def _evaluate_data_heuristics(self, sample_values: List[Any], field_def: FieldDefinition) -> float:
        """Examine non-null sample values to verify or boost field match."""
        valid_samples = [str(v).strip() for v in sample_values if v is not None and str(v).strip() != ""]
        if not valid_samples:
            return 0.0

        score = 0.0
        # Email heuristic
        if field_def.format == "email":
            email_matches = sum(1 for v in valid_samples if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v))
            if email_matches / len(valid_samples) > 0.6:
                score += 0.35

        # Date heuristic
        elif field_def.format == "date":
            date_matches = sum(1 for v in valid_samples if re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", v))
            if date_matches / len(valid_samples) > 0.6:
                score += 0.35

        # Phone heuristic
        elif field_def.format == "phone":
            phone_matches = sum(1 for v in valid_samples if re.search(r"(\+?\d[\d -]{7,}\d)", v))
            if phone_matches / len(valid_samples) > 0.6:
                score += 0.35

        # Numeric / Salary heuristic
        elif field_def.type == "number":
            numeric_matches = sum(1 for v in valid_samples if re.sub(r"[$,\s]", "", v).replace(".", "", 1).isdigit())
            if numeric_matches / len(valid_samples) > 0.6:
                score += 0.30

        # Enum / Status heuristic
        elif field_def.enum:
            enum_lower = [e.lower() for e in field_def.enum]
            enum_matches = sum(1 for v in valid_samples if v.lower() in enum_lower)
            if enum_matches / len(valid_samples) > 0.5:
                score += 0.40

        return min(score, 0.40)

    def map_column(self, col_name: str, sample_values: List[Any]) -> MappingProposal:
        norm_col = self._normalize_string(col_name)
        candidates = []

        for target_field_name, field_def in self.schema.fields.items():
            base_score = 0.0
            reasons = []

            # 1. Exact field name match
            if norm_col == self._normalize_string(target_field_name):
                base_score = 1.0
                reasons.append("Exact target field name match")
            
            # 2. Exact alias match
            elif any(norm_col == self._normalize_string(alias) for alias in field_def.aliases):
                base_score = 0.95
                matched_alias = next(alias for alias in field_def.aliases if norm_col == self._normalize_string(alias))
                reasons.append(f"Direct match with known alias '{matched_alias}'")
            
            # 3. Fuzzy similarity
            else:
                sim = self._string_similarity(col_name, target_field_name)
                for alias in field_def.aliases:
                    alias_sim = self._string_similarity(col_name, alias)
                    if alias_sim > sim:
                        sim = alias_sim
                if sim > 0.5:
                    base_score = sim * 0.75
                    reasons.append(f"Fuzzy name similarity ({sim:.2f})")

            # 4. Data value profiling heuristic
            heuristic_boost = self._evaluate_data_heuristics(sample_values, field_def)
            if heuristic_boost > 0:
                base_score = min(1.0, base_score + heuristic_boost)
                reasons.append(f"Sample value profile matched {field_def.type}/{field_def.format or 'pattern'}")

            if base_score > 0.3:
                candidates.append({
                    "target_field": target_field_name,
                    "score": round(base_score, 2),
                    "reasoning": "; ".join(reasons)
                })

        candidates.sort(key=lambda x: x["score"], reverse=True)

        if not candidates:
            return MappingProposal(
                source_column=col_name,
                target_field=None,
                confidence=0.0,
                reasoning="No plausible target field identified",
                is_ambiguous=True
            )

        top_candidate = candidates[0]
        is_ambiguous = False
        reasoning = top_candidate["reasoning"]

        # Check for ambiguity: multiple high-scoring candidates within narrow margin
        if len(candidates) > 1:
            second_candidate = candidates[1]
            if top_candidate["score"] < 0.85 and (top_candidate["score"] - second_candidate["score"]) < 0.12:
                is_ambiguous = True
                reasoning = (
                    f"Ambiguous collision: could map to '{top_candidate['target_field']}' "
                    f"({top_candidate['score']}) or '{second_candidate['target_field']}' ({second_candidate['score']})"
                )

        if top_candidate["score"] < self.confidence_threshold:
            is_ambiguous = True
            reasoning = f"Confidence {top_candidate['score']} is below autonomous threshold ({self.confidence_threshold})"

        return MappingProposal(
            source_column=col_name,
            target_field=top_candidate["target_field"],
            confidence=top_candidate["score"],
            reasoning=reasoning,
            is_ambiguous=is_ambiguous,
            candidate_fields=candidates[:3]
        )

    def map_dataset(self, columns: List[str], sample_rows: List[Dict[str, Any]]) -> Dict[str, MappingProposal]:
        mappings = {}
        for col in columns:
            if col.startswith("_"):
                continue
            col_samples = [row.get(col) for row in sample_rows[:20]]
            mappings[col] = self.map_column(col, col_samples)
        return mappings
