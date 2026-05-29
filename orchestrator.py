from design_agent import run_design_agent
from developer_agent import run_developer_agent
from bulk_generator import run_bulk_generator
from qa_agent import run_qa_agent, run_self_healing_agent

class Orchestrator:
    MAX_HEALING_ATTEMPTS = 3

    def execute_pipeline(self, user_concept: str) -> dict:
        logs = []
        blueprint = run_design_agent(user_concept)
        logs.append("Design complete via 1.5 Pro.")
        
        code = run_developer_agent(blueprint)
        logs.append("C# Code compiled via 1.5 Pro.")

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
