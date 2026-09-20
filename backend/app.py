import os
import glob
from typing import List, Optional, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.core.schema import target_schema
from backend.core.pipeline import global_agent_pipeline, global_pipeline_state
from backend.core.mock_target import global_mock_target
from backend.core.llm_agent import global_llm_reasoner

app = FastAPI(
    title="AI Data Migration & Integration Agent",
    description="Autonomous data migration agent with defensible escalation boundary and HITL UI",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Target directory paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "sample_sources")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

class EscalationResolveRequest(BaseModel):
    escalation_id: str
    resolution_type: str  # "APPROVED_SUGGESTION" | "MANUAL_OVERRIDE" | "REJECTED"
    resolved_value: Optional[Any] = None

class RollbackRequest(BaseModel):
    transaction_id: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []

@app.post("/api/chat")
def chat_with_agent(req: ChatRequest):
    """
    Interactive conversation endpoint with the Migration AI Agent.
    """
    state_dump = global_agent_pipeline.get_summary()
    res = global_llm_reasoner.chat(
        user_message=req.message,
        history=req.history or [],
        state=state_dump,
        pipeline=global_agent_pipeline
    )
    if "summary" not in res or res["summary"] is None:
        res["summary"] = global_agent_pipeline.get_summary()
    return res

@app.get("/api/schema")
def get_schema():
    return target_schema.model_dump()

@app.get("/api/pipeline/status")
def get_status():
    return global_agent_pipeline.get_summary()

@app.post("/api/pipeline/run-sample")
def run_sample_pipeline():
    """Run pipeline against the 3 pre-built sample datasets (CSV + XLSX)"""
    sample_files = glob.glob(os.path.join(DATA_DIR, "*.*"))
    if not sample_files:
        raise HTTPException(status_code=404, detail="No sample files found in data/sample_sources")
    
    file_inputs = [{"path": p} for p in sample_files if p.endswith((".csv", ".xlsx", ".xls"))]
    result = global_agent_pipeline.run_pipeline(file_inputs)
    return result

@app.post("/api/pipeline/upload")
async def upload_files_and_run(files: List[UploadFile] = File(...)):
    """Upload custom client files and run autonomous migration"""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    file_inputs = []
    for f in files:
        content = await f.read()
        file_inputs.append({
            "filename": f.filename,
            "content": content
        })

    result = global_agent_pipeline.run_pipeline(file_inputs)
    return result

@app.post("/api/escalation/resolve")
def resolve_escalation(req: EscalationResolveRequest):
    try:
        updated_summary = global_agent_pipeline.resolve_escalation_and_reprocess(
            escalation_id=req.escalation_id,
            resolution_type=req.resolution_type,
            resolved_value=req.resolved_value
        )
        return {"status": "success", "summary": updated_summary}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/target/push")
def push_to_target():
    try:
        res = global_agent_pipeline.push_to_target()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/target/rollback")
def rollback_transaction(req: RollbackRequest):
    try:
        res = global_agent_pipeline.rollback_push(req.transaction_id)
        return res
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/csv")
def export_cleaned_csv():
    output_csv = os.path.join(BASE_DIR, "data", "migrated_output", "cleaned_target_employees.csv")
    if not os.path.exists(output_csv):
        raise HTTPException(status_code=404, detail="No migrated output found. Run the pipeline first.")
    return FileResponse(
        output_csv,
        media_type="text/csv",
        filename="cleaned_target_employees.csv"
    )

@app.post("/api/target/reset")
def reset_all():
    global_pipeline_state.reset()
    global_mock_target.reset_to_seed()
    return {"status": "reset_completed"}

# Serve frontend static assets
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Frontend not found at " + index_file}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
