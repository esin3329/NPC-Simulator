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


@app.get("/api/v1/health")
def health():
    return orchestrator.health_status()


@app.post("/api/v1/generate")
def generate_npc_assets(body: GenerateNpcRequest):
    if not orchestrator.has_model_api_key():
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY or GOOGLE_API_KEY must be configured before generating NPC assets.",
        )

    try:
        return orchestrator.execute_pipeline(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generation-jobs", status_code=202)
def create_generation_job(body: GenerateNpcRequest):
    if not orchestrator.has_model_api_key():
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY or GOOGLE_API_KEY must be configured before generating NPC assets.",
        )

    return orchestrator.create_generation_job(body)


@app.get("/api/v1/generation-jobs/{job_id}")
def get_generation_job(job_id: str):
    job = orchestrator.get_generation_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return job


@app.get("/api/v1/generations")
def list_generations():
    return {"generations": orchestrator.list_generations()}


@app.get("/api/v1/generations/{generation_id}")
def get_generation(generation_id: str):
    generation = orchestrator.get_generation(generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    return generation
