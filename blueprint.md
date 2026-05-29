# Build with Gemini XPRIZE: NPC Simulator Architecture Blueprint
**Author:** Jeon Huijun (전희준)  
**Date:** May 2026  
**Target Platform:** Google Cloud Run (Serverless Production Ecosystem)

---

## 1. System Architecture Overview
The NPC Simulator is a production-grade, AI-Native multi-agent pipeline designed to solve the resource constraints of small-scale and indie game studios. By decoupling game logic design from engine-specific implementation, the system orchestrates a deterministic flow from raw natural language input into validated, production-ready Unity C# Finite State Machine (FSM) components.

```
[ User Input / Client App ]
             │ (HTTP POST /api/v1/generate)
             ▼
┌────────────────────────────────────────────────────────┐
│              Google Cloud Run Container                │
│                                                        │
│   ┌────────────────────────────────────────────────┐   │
│   │               FastAPI Wrapper                  │   │
│   └───────────────────────┬────────────────────────┘   │
│                           ▼                            │
│   ┌────────────────────────────────────────────────┐   │
│   │            Master Orchestrator Loop            │   │
│   └───┬───────────────────┬────────────────────▲───┘   │
│       │                   │                    │       │
│       │ (Step 1)          │ (Step 2)           │ (3-2) │
│       ▼                   ▼                    │ Self  │
│ ┌───────────┐       ┌───────────┐       ┌──────┴────┐  │
│ │Design Agent│       │Dev Agent  │       │QA/Valid   │  │
│ │(2.5 Flash)│       │(2.5 Flash)│       │Agent (Pro)│  │
│ └─────┬─────┘       └─────┬─────┘       └──────▲────┘  │
│       │                   │                    │       │
│       └─► [JSON Schema]  └─► [C# Source] ─────┘ (3-1) │
│                                                 Check  │
└────────────────────────────────────────────────────────┘
```

---

## 2. Layered Breakdown

### Layer 1: The API Gateway (FastAPI)
The entry point exposes a secure REST API that accepts user parameters asynchronously. It serves as the interface between external client tools (e.g., custom Unity Editor Extensions or web dashboards) and the internal Python orchestration logic.

### Layer 2: Multi-Agent Orchestration & Structured Outputs
1. **Design Agent (Gemini 2.5 Flash):** Ingests descriptive prose and interprets state constraints. Outputs are strictly enforced into deterministic JSON through the shared `NPC_BLUEPRINT_RESPONSE_SCHEMA` in `schemas.py`.
2. **Developer Agent (Gemini 2.5 Flash):** Transforms the validated JSON specification into standard PascalCase Object-Oriented C# scripts containing explicit states, events, and dynamic dialogue routers.

### Layer 3: The Validation & Self-Healing Loop
* **QA Agent:** Inspects syntax, counts brackets, and checks for logical mapping slips.
* **Self-Healing Mechanics:** If validation failures occur, the script logs the raw trace, structures it as an error context packet, and prompts a corrective iteration loop up to 3 times before final response deployment.

---

## 3. Production Deployment Strategy (Google Cloud Run)
The application is wrapped into an OCI-compliant container using Docker. The deployment configuration on Google Cloud Run brings three distinct competitive advantages for the XPRIZE business metrics criteria:
1. **Zero-Inactivity Cost:** The container scales down to 0 instances when idle, minimizing infrastructure cost baselines to absolute zero.
2. **Infinite Elasticity:** Spikes in game developer demand are met with instantaneous microsecond-level scaling.
3. **Security Isolation:** Each agent generation routine executes isolated within container runtime sandboxes, completely decoupling master infrastructure secrets from client scripts.
