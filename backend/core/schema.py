import json
import os
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class FieldDefinition(BaseModel):
    name: str
    type: str
    required: bool = False
    unique: bool = False
    enum: Optional[List[str]] = None
    format: Optional[str] = None
    minimum: Optional[float] = None
    default: Optional[Any] = None
    description: str = ""
    aliases: List[str] = []

class TargetSchema(BaseModel):
    entity: str
    version: str
    description: str
    fields: Dict[str, FieldDefinition]

    @classmethod
    def load_from_file(cls, path: str = "data/target_schema.json") -> "TargetSchema":
        if not os.path.isabs(path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path = os.path.join(base_dir, path)
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        
        field_objs = {}
        for fname, fdef in raw.get("fields", {}).items():
            field_objs[fname] = FieldDefinition(
                name=fname,
                type=fdef.get("type", "string"),
                required=fdef.get("required", False),
                unique=fdef.get("unique", False),
                enum=fdef.get("enum"),
                format=fdef.get("format"),
                minimum=fdef.get("minimum"),
                default=fdef.get("default"),
                description=fdef.get("description", ""),
                aliases=[a.lower() for a in fdef.get("aliases", [])]
            )
        
        return cls(
            entity=raw.get("entity", "Entity"),
            version=raw.get("version", "1.0"),
            description=raw.get("description", ""),
            fields=field_objs
        )

# Global singleton loader
target_schema = TargetSchema.load_from_file()
