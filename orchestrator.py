from design_agent import run_design_agent
from developer_agent import run_developer_agent
from bulk_generator import run_bulk_generator
from schemas import GenerateNpcRequest

class Orchestrator:
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
        
        bulk_dialogues = run_bulk_generator(blueprint, count=10)
        logs.append("Bonus ambient dialogues batch generated via 2.5 Flash.")
        
        return {
            "status": "SUCCESS",
            "logs": logs,
            "blueprint": blueprint,
            "code": code,
            "bonus_assets": bulk_dialogues
        }
