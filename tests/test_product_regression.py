import json
import os
import inspect
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import bulk_generator
import design_agent
import orchestrator as orchestrator_module
from main import create_generation_job, generate_npc_assets, get_generation_job
from orchestrator import Orchestrator, load_env_file
from qa_agent import run_qa_agent
from schemas import GenerateNpcRequest, NPC_BLUEPRINT_RESPONSE_SCHEMA


SAMPLE_BLUEPRINT = {
    "npc_profile": {
        "system_name": "archive_memory_keeper",
        "display_name": "기억 수집가",
        "personality_tags": ["신중함", "집착"],
        "faction": "Archive Wardens",
        "base_states": ["Idle", "Trusting"],
    },
    "dialogue_system": {
        "root_node": "root",
        "nodes": {
            "root": {
                "speaker": "npc",
                "state_context": "Idle",
                "dialogue_text": "기록은 숨을 쉽니다.",
                "options": [
                    {
                        "option_text": "기억을 묻는다",
                        "next_node_id": "trust",
                        "required_conditions": {},
                    }
                ],
            },
            "trust": {
                "speaker": "npc",
                "state_context": "Trusting",
                "dialogue_text": "잃어버린 이름을 찾고 있군요.",
                "options": [],
            },
        },
    },
    "runtime_simulation_sandbox": {
        "validation_status": "READY",
        "agent_conversations": [
            {"turn": 1, "player_action": "인사", "npc_response": "쉿."},
            {"turn": 2, "player_action": "질문", "npc_response": "기록을 보세요."},
            {"turn": 3, "player_action": "설득", "npc_response": "따라오세요."},
        ],
    },
}

VALID_CODE = """```csharp
using UnityEngine;
public class ArchiveMemoryKeeperController : MonoBehaviour {
    enum State { Idle, Trusting }
    public void StartDialogue() {}
    public void ChooseOption(int index) {}
    bool CheckCondition(string key) { return true; }
}
```"""


class ProductRegressionTests(unittest.TestCase):
    def test_health_reports_missing_model_key_and_writable_storage(self):
        with tempfile.TemporaryDirectory(dir=".") as tmpdir:
            orchestrator = Orchestrator(output_dir=Path(tmpdir))
            with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}, clear=False):
                status = orchestrator.health_status()

        self.assertEqual(status["status"], "degraded")
        self.assertFalse(status["checks"]["gemini_api_key"])
        self.assertTrue(status["checks"]["generation_storage_writable"])

    def test_health_reports_ok_when_model_key_is_configured(self):
        with tempfile.TemporaryDirectory(dir=".") as tmpdir:
            orchestrator = Orchestrator(output_dir=Path(tmpdir))
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "GOOGLE_API_KEY": ""}, clear=False):
                status = orchestrator.health_status()

        self.assertEqual(status["status"], "ok")
        self.assertTrue(status["checks"]["gemini_api_key"])
        self.assertTrue(status["checks"]["generation_storage_writable"])

    def test_generate_returns_503_when_model_key_is_missing(self):
        request = GenerateNpcRequest(user_prompt="테스트 NPC")

        with patch("main.orchestrator.has_model_api_key", return_value=False):
            with self.assertRaises(HTTPException) as raised:
                generate_npc_assets(request)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("GEMINI_API_KEY", raised.exception.detail)

    def test_mocked_pipeline_saves_successful_generation(self):
        with tempfile.TemporaryDirectory(dir=".") as tmpdir:
            orchestrator = Orchestrator(output_dir=Path(tmpdir))
            with patch.object(
                orchestrator_module,
                "run_design_agent",
                return_value=json.dumps(SAMPLE_BLUEPRINT, ensure_ascii=False),
            ), patch.object(
                orchestrator_module,
                "run_developer_agent",
                return_value=VALID_CODE,
            ), patch.object(
                orchestrator_module,
                "run_bulk_generator",
                return_value=["기록은 아직 젖어 있습니다."],
            ):
                result = orchestrator.execute_pipeline(GenerateNpcRequest(user_prompt="테스트 NPC"))
                saved = orchestrator.get_generation(result["generation_id"])
                listed = orchestrator.list_generations()

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["qa_report"]["status"], "PASSED")
        self.assertEqual(result["qa_report"]["issue_count"], 0)
        self.assertEqual(result["summary"]["display_name"], "기억 수집가")
        self.assertEqual(result["summary"]["state_count"], 2)
        self.assertEqual(result["summary"]["dialogue_count"], 3)
        self.assertEqual(result["unity_metadata"]["recommended_filename"], "ArchiveMemoryKeeperController.cs")
        self.assertIsNotNone(saved)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["summary"]["qa_status"], "PASSED")

    def test_generation_job_api_completes_and_exposes_result(self):
        with tempfile.TemporaryDirectory(dir=".") as tmpdir:
            test_orchestrator = Orchestrator(output_dir=Path(tmpdir))
            with patch("main.orchestrator", test_orchestrator), patch.dict(
                os.environ,
                {"GEMINI_API_KEY": "test-key", "GOOGLE_API_KEY": ""},
                clear=False,
            ), patch.object(
                orchestrator_module,
                "run_design_agent",
                return_value=json.dumps(SAMPLE_BLUEPRINT, ensure_ascii=False),
            ), patch.object(
                orchestrator_module,
                "run_developer_agent",
                return_value=VALID_CODE,
            ), patch.object(
                orchestrator_module,
                "run_bulk_generator",
                return_value=["기록은 아직 젖어 있습니다."],
            ):
                job = create_generation_job(GenerateNpcRequest(user_prompt="테스트 NPC"))
                for _ in range(50):
                    current = get_generation_job(job["job_id"])
                    if current["status"] == "COMPLETED":
                        break
                    time.sleep(0.02)

        self.assertEqual(current["status"], "COMPLETED")
        self.assertEqual(current["stage"], "saved")
        self.assertEqual(current["result"]["status"], "SUCCESS")
        self.assertIsNotNone(current["generation_id"])

    def test_qa_agent_flags_invalid_assets(self):
        bad_blueprint = json.dumps(
            {
                "npc_profile": {},
                "dialogue_system": {"root_node": "missing", "nodes": {}},
                "runtime_simulation_sandbox": {"agent_conversations": []},
            }
        )
        report = run_qa_agent(bad_blueprint, "public class Broken {}")

        self.assertEqual(report["status"], "FAILED")
        self.assertGreater(report["issue_count"], 0)
        self.assertFalse(report["dialogue_tree_valid"])
        self.assertFalse(report["unity_code_valid"])

    def test_bulk_generator_parses_json_list_response(self):
        class Response:
            text = '["첫 번째 대사", "두 번째 대사"]'

        class Models:
            def generate_content(self, **kwargs):
                return Response()

        class Client:
            models = Models()

        with patch.object(bulk_generator.genai, "Client", Client):
            result = bulk_generator.run_bulk_generator("{}")

        self.assertEqual(result, ["첫 번째 대사", "두 번째 대사"])

    def test_dockerfile_uses_default_port_and_health_endpoint(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("EXPOSE 8000", dockerfile)
        self.assertIn("ENV PORT 8000", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("/api/v1/health", dockerfile)
        self.assertIn('"--port", "8000"', dockerfile)

    def test_environment_example_documents_model_key_without_hiding_it(self):
        env_example = Path(".env.example").read_text(encoding="utf-8")
        gitignore = Path(".gitignore").read_text(encoding="utf-8")

        self.assertIn("GEMINI_API_KEY=", env_example)
        self.assertIn("GOOGLE_API_KEY=", env_example)
        self.assertIn(".env.*", gitignore)
        self.assertIn("!.env.example", gitignore)

    def test_gemini_response_schema_avoids_unsupported_additional_properties(self):
        serialized_schema = json.dumps(NPC_BLUEPRINT_RESPONSE_SCHEMA)

        self.assertNotIn("additionalProperties", serialized_schema)

    def test_design_agent_uses_prompt_contract_for_dynamic_dialogue_nodes(self):
        source = inspect.getsource(design_agent.run_design_agent)

        self.assertNotIn("response_schema=", source)
        self.assertIn("dialogue_system.nodes must be a non-empty object", source)

    def test_env_file_loader_reads_model_key_without_overriding_existing_env(self):
        with tempfile.TemporaryDirectory(dir=".") as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# local secrets",
                        'GEMINI_API_KEY="from-env-file"',
                        "GOOGLE_API_KEY=from-google-file",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"GOOGLE_API_KEY": "already-set"}, clear=True):
                load_env_file(env_path)
                self.assertEqual(os.environ["GEMINI_API_KEY"], "from-env-file")
                self.assertEqual(os.environ["GOOGLE_API_KEY"], "already-set")

    def test_generation_lookup_rejects_path_traversal_and_ignores_bad_json(self):
        with tempfile.TemporaryDirectory(dir=".") as tmpdir:
            output_dir = Path(tmpdir)
            orchestrator = Orchestrator(output_dir=output_dir)
            valid_payload = {
                "generation_id": "valid-generation",
                "created_at": "2026-05-30T00:00:00+00:00",
                "status": "SUCCESS",
                "metrics": {},
                "input": {},
            }
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "valid-generation.json").write_text(json.dumps(valid_payload), encoding="utf-8")
            (output_dir / "broken-generation.json").write_text("{not valid json", encoding="utf-8")

            self.assertIsNone(orchestrator.get_generation("../valid-generation"))
            self.assertIsNone(orchestrator.get_generation("nested/valid-generation"))
            self.assertIsNone(orchestrator.get_generation("nested\\valid-generation"))
            self.assertIsNone(orchestrator.get_generation("broken-generation"))
            self.assertEqual(orchestrator.get_generation("valid-generation")["status"], "SUCCESS")
            self.assertEqual(
                [item["generation_id"] for item in orchestrator.list_generations()],
                ["valid-generation"],
            )


if __name__ == "__main__":
    unittest.main()
