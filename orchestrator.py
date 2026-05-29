import json
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

class Orchestrator:
    MAX_HEALING_ATTEMPTS = 3
    MAX_DESIGN_RETRIES = 2

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path(__file__).resolve().parent / "outputs" / "generations"

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

    def _save_generation(self, generation_id: str, payload: dict) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_dir / f"{generation_id}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def execute_pipeline(self, request: GenerateNpcRequest) -> dict:
        started_at = time.perf_counter()
        generation_id = uuid4().hex
        created_at = datetime.now(UTC).isoformat()
        logs = []
        model_calls = 0
        healing_attempts = 0
        blueprint = None
        last_blueprint_error = None
        last_raw_blueprint = None

        for attempt in range(1, self.MAX_DESIGN_RETRIES + 2):
            last_raw_blueprint = run_design_agent(
                user_prompt=request.user_prompt,
                genre=request.world_setting.genre,
                lore_summary=request.world_setting.lore_summary,
                max_dialogue_depth=request.max_dialogue_depth,
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
            bundle = {"input": request.model_dump(), **payload}
            self._save_generation(generation_id, bundle)
            return payload
        
        code = run_developer_agent(blueprint)
        model_calls += 1
        logs.append("C# Code compiled via 2.5 Flash.")

        qa_report = run_qa_agent(blueprint, code, attempt=1)
        logs.append(f"QA Agent validation attempt 1: {qa_report['status']}.")

        healing_reports = [qa_report]
        for attempt in range(1, self.MAX_HEALING_ATTEMPTS + 1):
            if qa_report["status"] == "PASSED":
                break

            logs.append(f"Self-healing iteration {attempt} started with {qa_report['issue_count']} issue(s).")
            code = run_self_healing_agent(blueprint, code, qa_report)
            model_calls += 1
            healing_attempts += 1
            qa_report = run_qa_agent(blueprint, code, attempt=attempt + 1)
            healing_reports.append(qa_report)
            logs.append(f"QA Agent validation attempt {attempt + 1}: {qa_report['status']}.")
        
        bulk_dialogues = run_bulk_generator(blueprint, count=10)
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
        bundle = {"input": request.model_dump(), **payload}
        self._save_generation(generation_id, bundle)
        return payload
