import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from design_agent import run_design_agent
from developer_agent import run_developer_agent
from bulk_generator import run_bulk_generator
from qa_agent import run_qa_agent, run_self_healing_agent
from schemas import GenerateNpcRequest, NpcBlueprint


def load_env_file(env_path: Path | None = None) -> None:
    path = env_path or Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class Orchestrator:
    MAX_HEALING_ATTEMPTS = 3
    MAX_DESIGN_RETRIES = 2

    def __init__(self, output_dir: Path | None = None) -> None:
        load_env_file()
        self.output_dir = output_dir or Path(__file__).resolve().parent / "outputs" / "generations"
        self._jobs: dict[str, dict] = {}
        self._jobs_lock = threading.Lock()
        self.max_active_jobs = int(os.getenv("MAX_ACTIVE_JOBS", "2"))
        self.max_healing_attempts = int(os.getenv("MAX_HEALING_ATTEMPTS", str(self.MAX_HEALING_ATTEMPTS)))
        self.bonus_dialogue_count = int(os.getenv("BONUS_DIALOGUE_COUNT", "10"))
        self.persist_generations = os.getenv("PERSIST_GENERATIONS", "true").lower() not in {"0", "false", "no"}

    def has_model_api_key(self, request: GenerateNpcRequest | None = None) -> bool:
        return bool(
            (request and request.client_api_key)
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

    def health_status(self) -> dict:
        checks = {
            "gemini_api_key": self.has_model_api_key(),
            "generation_storage_writable": not self.persist_generations,
        }

        if self.persist_generations:
            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                probe_path = self.output_dir / ".healthcheck"
                probe_path.write_text("ok", encoding="utf-8")
                probe_path.unlink(missing_ok=True)
                checks["generation_storage_writable"] = True
            except OSError:
                checks["generation_storage_writable"] = False

        return {
            "status": "ok" if all(checks.values()) else "degraded",
            "checks": checks,
            "config": {
                "persist_generations": self.persist_generations,
                "max_active_jobs": self.max_active_jobs,
                "max_healing_attempts": self.max_healing_attempts,
                "bonus_dialogue_count": self.bonus_dialogue_count,
            },
        }

    def _validate_blueprint(self, raw_blueprint: str) -> tuple[str | None, str | None]:
        try:
            parsed = json.loads(raw_blueprint)
        except json.JSONDecodeError as exc:
            return None, f"Blueprint JSON parsing failed: {exc.msg} at line {exc.lineno}, column {exc.colno}."

        try:
            model = NpcBlueprint.model_validate(parsed)
        except ValidationError as exc:
            return None, f"Blueprint schema validation failed: {exc.errors()}"

        return model.model_dump_json(indent=2), None

    def _build_metrics(
        self,
        started_at: float,
        healing_attempts: int,
        model_calls: int,
        final_status: str,
    ) -> dict:
        return {
            "latency_ms": round((time.perf_counter() - started_at) * 1000),
            "healing_attempts": healing_attempts,
            "model_calls": model_calls,
            "final_status": final_status,
        }

    def _build_unity_metadata(self, blueprint: str, code: str) -> dict:
        try:
            parsed = json.loads(blueprint)
        except json.JSONDecodeError:
            parsed = {}

        system_name = parsed.get("npc_profile", {}).get("system_name") or "generated_npc"
        fallback_class = "".join(part.capitalize() for part in re.split(r"[^a-zA-Z0-9]+", system_name) if part)
        fallback_class = f"{fallback_class or 'GeneratedNpc'}Controller"
        match = re.search(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", code or "")
        class_name = match.group(1) if match else fallback_class
        return {
            "class_name": class_name,
            "recommended_filename": f"{class_name}.cs",
            "engine": "Unity",
            "language": "C#",
        }

    def _build_result_summary(self, payload: dict) -> dict:
        try:
            blueprint = json.loads(payload.get("blueprint") or "{}")
        except json.JSONDecodeError:
            blueprint = {}

        profile = blueprint.get("npc_profile", {})
        nodes = blueprint.get("dialogue_system", {}).get("nodes", {})
        states = profile.get("base_states", [])
        bonus_assets = payload.get("bonus_assets", [])
        qa_report = payload.get("qa_report", {}) or {}
        issues_by_severity = qa_report.get("issues_by_severity", {}) or {}
        critical_issues = issues_by_severity.get("critical", [])

        return {
            "display_name": profile.get("display_name") or "Untitled NPC",
            "system_name": profile.get("system_name") or "",
            "faction": profile.get("faction") or "",
            "state_count": len(states) if isinstance(states, list) else 0,
            "dialogue_count": (len(nodes) if isinstance(nodes, dict) else 0)
            + (len(bonus_assets) if isinstance(bonus_assets, list) else 0),
            "qa_status": qa_report.get("status") or payload.get("status"),
            "issue_count": qa_report.get("issue_count", 0),
            "critical_issue_count": len(critical_issues) if isinstance(critical_issues, list) else 0,
            "production_readiness": qa_report.get("production_readiness") or "UNKNOWN",
            "healing_attempts": payload.get("metrics", {}).get("healing_attempts", 0),
            "latency_ms": payload.get("metrics", {}).get("latency_ms", 0),
            "model_calls": payload.get("metrics", {}).get("model_calls", 0),
        }

    def _save_generation(self, generation_id: str, payload: dict) -> None:
        if not self.persist_generations:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_dir / f"{generation_id}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _safe_request_dump(self, request: GenerateNpcRequest) -> dict:
        return request.model_dump(exclude={"client_api_key"})

    def list_generations(self) -> list[dict]:
        if not self.output_dir.exists():
            return []

        generations = []
        for path in sorted(self.output_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            generations.append(
                {
                    "generation_id": payload.get("generation_id", path.stem),
                    "created_at": payload.get("created_at"),
                    "status": payload.get("status"),
                    "metrics": payload.get("metrics", {}),
                    "summary": payload.get("summary") or self._build_result_summary(payload),
                    "unity_metadata": payload.get("unity_metadata", {}),
                    "input": payload.get("input", {}),
                }
            )
        return generations

    def get_generation(self, generation_id: str) -> dict | None:
        if not generation_id or "/" in generation_id or "\\" in generation_id:
            return None

        path = self.output_dir / f"{generation_id}.json"
        if not path.exists():
            return None

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _set_job(self, job_id: str, **updates: object) -> None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.update(updates)
            job["updated_at"] = datetime.now(UTC).isoformat()

    def create_generation_job(self, request: GenerateNpcRequest) -> dict:
        job_id = uuid4().hex
        now = datetime.now(UTC).isoformat()
        job = {
            "job_id": job_id,
            "status": "QUEUED",
            "stage": "queued",
            "created_at": now,
            "updated_at": now,
            "generation_id": None,
            "result": None,
            "error": None,
        }
        with self._jobs_lock:
            active_count = sum(1 for item in self._jobs.values() if item.get("status") in {"QUEUED", "RUNNING"})
            if active_count >= self.max_active_jobs:
                return {
                    "status": "REJECTED",
                    "error": "Too many active generation jobs. Please retry after another job finishes.",
                    "max_active_jobs": self.max_active_jobs,
                }
            self._jobs[job_id] = job

        thread = threading.Thread(target=self._run_generation_job, args=(job_id, request), daemon=True)
        thread.start()
        return job

    def get_generation_job(self, job_id: str) -> dict | None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _run_generation_job(self, job_id: str, request: GenerateNpcRequest) -> None:
        def progress(stage: str, message: str) -> None:
            self._set_job(job_id, status="RUNNING", stage=stage, message=message)

        try:
            result = self.execute_pipeline(request, progress_callback=progress)
            self._set_job(
                job_id,
                status="COMPLETED",
                stage="saved",
                generation_id=result.get("generation_id"),
                result=result,
                message="Generation saved.",
            )
        except Exception as exc:
            self._set_job(job_id, status="FAILED", stage="failed", error=str(exc), message=str(exc))

    def execute_pipeline(self, request: GenerateNpcRequest, progress_callback=None) -> dict:
        started_at = time.perf_counter()
        generation_id = uuid4().hex
        created_at = datetime.now(UTC).isoformat()
        logs = []
        model_calls = 0
        healing_attempts = 0
        blueprint = None
        last_blueprint_error = None
        last_raw_blueprint = None
        api_key = request.client_api_key

        if progress_callback:
            progress_callback("design", "Design Agent is building the NPC blueprint.")

        for attempt in range(1, self.MAX_DESIGN_RETRIES + 2):
            last_raw_blueprint = run_design_agent(
                user_prompt=request.user_prompt,
                genre=request.world_setting.genre,
                lore_summary=request.world_setting.lore_summary,
                max_dialogue_depth=request.max_dialogue_depth,
                api_key=api_key,
            )
            model_calls += 1
            blueprint, last_blueprint_error = self._validate_blueprint(last_raw_blueprint)
            if blueprint:
                logs.append(f"Design complete via 2.5 Flash on attempt {attempt}.")
                break

            logs.append(f"Design validation attempt {attempt} failed: {last_blueprint_error}")

        if not blueprint:
            qa_report = run_qa_agent(last_raw_blueprint or "{}", "", attempt=1)
            if last_blueprint_error and last_blueprint_error not in qa_report["issues"]:
                qa_report["issues"].insert(0, last_blueprint_error)
            qa_report["issue_count"] = len(qa_report["issues"])
            qa_report["status"] = "FAILED"
            qa_report["schema_valid"] = False
            qa_report["production_readiness"] = "FAILED"
            qa_report["overall_score"] = 0
            qa_report["issues_by_severity"]["critical"] = qa_report["issues_by_severity"].get("critical", [])
            if last_blueprint_error and last_blueprint_error not in qa_report["issues_by_severity"]["critical"]:
                qa_report["issues_by_severity"]["critical"].insert(0, last_blueprint_error)
            final_status = "NEEDS_REVIEW"
            metrics = self._build_metrics(started_at, healing_attempts, model_calls, final_status)
            payload = {
                "generation_id": generation_id,
                "created_at": created_at,
                "status": final_status,
                "logs": logs,
                "blueprint": "{}",
                "code": "",
                "qa_report": qa_report,
                "self_healing": [qa_report],
                "bonus_assets": [],
                "metrics": metrics,
            }
            payload["unity_metadata"] = self._build_unity_metadata(payload["blueprint"], payload["code"])
            payload["summary"] = self._build_result_summary(payload)
            bundle = {"input": self._safe_request_dump(request), **payload}
            self._save_generation(generation_id, bundle)
            return payload

        if progress_callback:
            progress_callback("code", "Developer Agent is compiling the Unity controller.")
        code = run_developer_agent(blueprint, api_key=api_key)
        model_calls += 1
        logs.append("C# Code compiled via 2.5 Flash.")

        if progress_callback:
            progress_callback("qa", "QA Agent is validating schema, dialogue, and code readiness.")
        qa_report = run_qa_agent(blueprint, code, attempt=1)
        logs.append(f"QA Agent validation attempt 1: {qa_report['status']}.")

        healing_reports = [qa_report]
        for attempt in range(1, self.max_healing_attempts + 1):
            if qa_report["status"] == "PASSED":
                break

            logs.append(f"Self-healing iteration {attempt} started with {qa_report['issue_count']} issue(s).")
            if progress_callback:
                progress_callback("self-healing", f"Self-healing iteration {attempt} is repairing issues.")
            code = run_self_healing_agent(blueprint, code, qa_report, api_key=api_key)
            model_calls += 1
            healing_attempts += 1
            qa_report = run_qa_agent(blueprint, code, attempt=attempt + 1)
            healing_reports.append(qa_report)
            logs.append(f"QA Agent validation attempt {attempt + 1}: {qa_report['status']}.")

        if progress_callback:
            progress_callback("bonus-assets", "Bonus ambient dialogue batch is being generated.")
        bulk_dialogues = run_bulk_generator(blueprint, count=self.bonus_dialogue_count, api_key=api_key)
        model_calls += 1
        logs.append("Bonus ambient dialogues batch generated via 2.5 Flash.")

        final_status = "SUCCESS" if qa_report["status"] == "PASSED" else "NEEDS_REVIEW"
        metrics = self._build_metrics(started_at, healing_attempts, model_calls, final_status)
        payload = {
            "generation_id": generation_id,
            "created_at": created_at,
            "status": final_status,
            "logs": logs,
            "blueprint": blueprint,
            "code": code,
            "qa_report": qa_report,
            "self_healing": healing_reports,
            "bonus_assets": bulk_dialogues,
            "metrics": metrics,
        }
        payload["unity_metadata"] = self._build_unity_metadata(blueprint, code)
        payload["summary"] = self._build_result_summary(payload)
        bundle = {"input": self._safe_request_dump(request), **payload}
        if progress_callback:
            progress_callback("saved", "Saving generation bundle.")
        self._save_generation(generation_id, bundle)
        return payload
