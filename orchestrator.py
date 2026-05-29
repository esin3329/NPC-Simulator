from design_agent import run_design_agent
from developer_agent import run_developer_agent
from bulk_generator import run_bulk_generator

class Orchestrator:
    def execute_pipeline(self, user_concept: str) -> dict:
        logs = []
        blueprint = run_design_agent(user_concept)
        logs.append("Design complete via 1.5 Pro.")
        
        code = run_developer_agent(blueprint)
        logs.append("C# Code compiled via 1.5 Pro.")
        
        bulk_dialogues = run_bulk_generator(blueprint, count=10)
        logs.append("Bonus ambient dialogues batch generated via 2.5 Flash.")
        
        return {
            "status": "SUCCESS",
            "logs": logs,
            "blueprint": blueprint,
            "code": code,
            "bonus_assets": bulk_dialogues
        }
