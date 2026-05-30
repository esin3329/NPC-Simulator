# NPC Simulator Test Report

Date: 2026-05-30

## Summary

NPC Simulator was tested at the FastAPI/API layer, orchestration layer, QA validation layer, static frontend script layer, and live Gemini end-to-end generation path. The app starts on the default port `8000`, serves the dashboard, validates bad API requests, exposes storage/API-key health status, passes the automated regression suite, and successfully generated a live NPC bundle.

## Verified Behavior

| Area | Evidence | Result |
| --- | --- | --- |
| Python syntax/import health | `python -m py_compile main.py schemas.py orchestrator.py design_agent.py developer_agent.py qa_agent.py bulk_generator.py` | Passed |
| Automated regression suite | `python -m unittest discover -s tests -v` | 13 tests passed |
| Default local port | `uvicorn main:app --host 127.0.0.1 --port 8000` | Server started |
| Dashboard | `GET /` on port `8000` | `200 OK` |
| Dashboard preflight status | Frontend calls `/api/v1/health` on load | Shows missing API key before generation |
| Health endpoint | `GET /api/v1/health` | `200 OK`, reports current dependency state |
| Docker container health signal | Dockerfile `HEALTHCHECK` calls `/api/v1/health` | Configured |
| Environment setup guidance | `.env.example` and `.gitignore` regression test | Example key file is trackable, real env files ignored |
| Local env file loading | Regression test for `.env` parser | `.env` key loaded without overriding existing env |
| Missing model API key handling | `POST /api/v1/generate` without a key | `503 Service Unavailable` |
| Bad request validation | `POST /api/v1/generate` without `user_prompt` | `422 Unprocessable Content` |
| Mocked successful pipeline | Regression test with mocked Gemini calls | `SUCCESS`, QA `PASSED`, generation saved and listed |
| Live Gemini pipeline | `POST /api/v1/generate` with configured `.env` key | `SUCCESS`, QA `PASSED`, saved and listed |
| Generation lookup safety | Regression test with path traversal and bad JSON files | Unsafe IDs rejected, bad JSON ignored |
| Gemini schema compatibility | Regression tests for schema/prompt contract | Avoids unsupported `additionalProperties` and dynamic-node schema trap |
| QA failure detection | Regression test with invalid blueprint/code | QA `FAILED` with issues |
| Bonus dialogue parsing | Regression test with JSON list response | Parsed to Python list |

## Issues Found

1. Missing Gemini API key originally surfaced as a generic `500 Internal Server Error`.
   - Impact: Operators and users could not distinguish deployment misconfiguration from an application failure.
   - Fix applied: `/api/v1/generate` now returns `503 Service Unavailable` with a specific configuration message when neither `GEMINI_API_KEY` nor `GOOGLE_API_KEY` is configured.

2. There was no health endpoint for deployment checks.
   - Impact: Cloud Run or local operators had no simple preflight check for model key and generation storage.
   - Fix applied: Added `GET /api/v1/health`, returning `status` plus `gemini_api_key` and `generation_storage_writable` checks.

3. Bonus dialogue generation could return raw JSON text instead of structured data.
   - Impact: Frontend/download consumers could receive inconsistent `bonus_assets` shapes.
   - Fix applied: `run_bulk_generator` now parses a JSON list response and falls back to raw text if parsing fails or the payload is not a list.

4. There was no repeatable regression test suite.
   - Impact: Fixes could regress without a fast local signal.
   - Fix applied: Added `tests/test_product_regression.py` using only the standard `unittest` framework.

5. The dashboard only surfaced API key problems after a generation attempt.
   - Impact: Users could spend time entering a prompt before learning the backend was not ready.
   - Fix applied: The dashboard now calls `/api/v1/health` on load and after reset, then displays whether Gemini API key setup is required.

6. The Docker image had no container-level health signal.
   - Impact: Container platforms could not use the app's health endpoint to detect readiness/degraded states.
   - Fix applied: Added a Docker `HEALTHCHECK` that uses Python's standard library to call `/api/v1/health` on the configured `PORT`.

7. The README recommended `.env`, but the app did not load `.env` automatically.
   - Impact: Users could place a key in `.env` and still see health as degraded.
   - Fix applied: Added a small standard-library `.env` loader that reads project-root `.env` on orchestrator startup without overriding existing environment variables.

8. Gemini Developer API rejected `additionalProperties` in the response schema.
   - Impact: The first live generation attempt failed with `500 Internal Server Error`.
   - Fix applied: Removed unsupported `additionalProperties` from the Gemini response schema and added a regression test.

9. Removing `additionalProperties` made `dialogue_system.nodes` too weakly constrained for Gemini's structured output.
   - Impact: A live generation returned `NEEDS_REVIEW` because `nodes` was `{}` after three design attempts.
   - Fix applied: Moved the dynamic dialogue-node contract into the design prompt and stopped passing `response_schema` to the design call. The follow-up live generation returned `SUCCESS` with QA `PASSED`.

## Live Verification Result

With a configured local `.env` key, the final live test returned:

- `GET /api/v1/health`: `status: ok`
- `POST /api/v1/generate`: `status: SUCCESS`
- `generation_id`: `75ef4303eabe4f5a80db5601075ed500`
- QA: `PASSED`, `issue_count: 0`
- Metrics: `latency_ms: 127954`, `healing_attempts: 1`, `model_calls: 4`
- Assets: blueprint generated, Unity C# generated, 10 bonus dialogues generated
- Storage: generation saved under `outputs/generations/` and listed by `GET /api/v1/generations`

## Remaining Risk

- No required verification gap remains for the tested local product path.
- Operational risks remain around synchronous model latency and local container filesystem persistence.

## Improvement Backlog

- Add request timeout/progress handling around Gemini calls. The successful live run took about 128 seconds, which is long for a synchronous request.
- Add structured logging for `generation_id`, final status, latency, and model call count.
- Consider a persistent store or Cloud Storage integration for `outputs/generations/` in production.
- Add a lightweight browser-based smoke test for the dashboard after choosing a frontend test tool.
