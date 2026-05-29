from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from orchestrator import Orchestrator

app = FastAPI(title="XPRIZE NPC Multi-Agent Server")
orchestrator = Orchestrator()
BASE_DIR = Path(__file__).resolve().parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestBody(BaseModel):
    concept: str

@app.get("/")
def dashboard():
    return FileResponse(BASE_DIR / "index.html")

@app.post("/api/v1/generate")
def generate_npc_assets(body: RequestBody):
    try:
        return orchestrator.execute_pipeline(body.concept)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
