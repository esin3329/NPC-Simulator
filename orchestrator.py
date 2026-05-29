from design_agent import run_design_agent
from developer_agent import run_developer_agent
from bulk_generator import run_bulk_generator
from qa_agent import run_qa_agent, run_self_healing_agent
from schemas import GenerateNpcRequest

class Orchestrator:
    MAX_HEALING_ATTEMPTS = 3

    def execute_pipeline(self, request: GenerateNpcRequest) -> dict:
        logs = []
        blueprint = run_design_agent(
            user_prompt=request.user_prompt,
            genre=request.world_setting.genre,
            lore_summary=request.world_setting.lore_summary,
            max_dialogue_depth=request.max_dialogue_depth,
        )
        logs.append("Design complete via 2.5 Flash.")
        
        code = run_developer_agent(blueprint)
        logs.append("C# Code compiled via 2.5 Flash.")

        qa_report = run_qa_agent(blueprint, code, attempt=1)
        logs.append(f"QA Agent validation attempt 1: {qa_report['status']}.")

        healing_reports = [qa_report]
        for attempt in range(1, self.MAX_HEALING_ATTEMPTS + 1):
            if qa_report["status"] == "PASSED":
                break

            logs.append(f"Self-healing iteration {attempt} started with {qa_report['issue_count']} issue(s).")
            code = run_self_healing_agent(blueprint, code, qa_report)
            qa_report = run_qa_agent(blueprint, code, attempt=attempt + 1)
            healing_reports.append(qa_report)
            logs.append(f"QA Agent validation attempt {attempt + 1}: {qa_report['status']}.")
        
        bulk_dialogues = run_bulk_generator(blueprint, count=10)
        logs.append("Bonus ambient dialogues batch generated via 2.5 Flash.")
        
        return {
            "status": "SUCCESS" if qa_report["status"] == "PASSED" else "NEEDS_REVIEW",
            "logs": logs,
            "blueprint": blueprint,
            "code": code,
            "qa_report": qa_report,
            "self_healing": healing_reports,
            "bonus_assets": bulk_dialogues
        }
