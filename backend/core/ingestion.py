import os
import io
import pandas as pd
from typing import List, Dict, Any, Union

class IngestedSource:
    def __init__(self, filename: str, rows: List[Dict[str, Any]], columns: List[str]):
        self.filename = filename
        self.rows = rows
        self.columns = columns
        self.row_count = len(rows)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "row_count": self.row_count,
            "columns": self.columns,
            "preview": self.rows[:5]
        }

class IngestionEngine:
    @staticmethod
    def parse_file(file_path_or_buffer: Union[str, io.BytesIO], filename: str) -> IngestedSource:
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path_or_buffer, dtype=str)
        elif ext == ".csv":
            # Handle possible encoding differences
            try:
                df = pd.read_csv(file_path_or_buffer, dtype=str, encoding="utf-8")
            except UnicodeDecodeError:
                if isinstance(file_path_or_buffer, str):
                    df = pd.read_csv(file_path_or_buffer, dtype=str, encoding="latin-1")
                else:
                    file_path_or_buffer.seek(0)
                    df = pd.read_csv(file_path_or_buffer, dtype=str, encoding="latin-1")
        else:
            raise ValueError(f"Unsupported file format: {ext}. Only CSV and Excel (.xlsx/.xls) are supported.")
        
        # Clean header whitespace
        df.columns = [str(col).strip() for col in df.columns]
        
        # Add metadata for provenance
        rows = []
        for idx, row_dict in enumerate(df.to_dict(orient="records")):
            cleaned_row = {k: (v if pd.notna(v) and str(v).strip() != "" else None) for k, v in row_dict.items()}
            cleaned_row["_source_file"] = filename
            cleaned_row["_source_row"] = idx + 1
            rows.append(cleaned_row)

        return IngestedSource(filename=filename, rows=rows, columns=list(df.columns))

    @classmethod
    def ingest_files(cls, file_inputs: List[Dict[str, Any]]) -> List[IngestedSource]:
        """
        Accepts list of {'path': str} or {'filename': str, 'content': bytes}
        """
        results = []
        for item in file_inputs:
            if "path" in item:
                path = item["path"]
                filename = os.path.basename(path)
                results.append(cls.parse_file(path, filename))
            elif "content" in item and "filename" in item:
                buf = io.BytesIO(item["content"])
                results.append(cls.parse_file(buf, item["filename"]))
        return results
