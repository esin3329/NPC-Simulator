from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from orchestrator import Orchestrator
from schemas import GenerateNpcRequest

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

@app.get("/")
def dashboard():
    return FileResponse(BASE_DIR / "index.html")

@app.post("/api/v1/generate")
def generate_npc_assets(body: GenerateNpcRequest):
    try:
        return orchestrator.execute_pipeline(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/generations")
def list_generations():
    return {"generations": orchestrator.list_generations()}


@app.get("/api/v1/generations/{generation_id}")
def get_generation(generation_id: str):
    generation = orchestrator.get_generation(generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    return generation
