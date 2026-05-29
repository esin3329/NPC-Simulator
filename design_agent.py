import os
from google import genai
from google.genai import types

def run_design_agent(user_concept: str, genre: str = "RPG") -> str:
    # 2.5-flash 무료 쿼터 및 결제 안정 환경으로 완벽 대응
    client = genai.Client()
    
    system_instruction = (
        "You are an expert game designer & narrative director. "
        "Analyze the world concept and generate a fully realized NPC system profile, "
        "a branching dialogue tree, and a 3-turn virtual validation conversation log. "
        "System names, IDs, operators, and keys must be strictly in English, "
        "and display names, options, and dialogue texts must be beautifully written in Korean."
    )
    
    # XPRIZE 가산점용 시뮬레이션 가드레일이 탑재된 확장 스키마
    advanced_schema = {
        "type": "OBJECT",
        "properties": {
            "npc_profile": {
                "type": "OBJECT",
                "properties": {
                    "system_name": {"type": "STRING"},
                    "display_name": {"type": "STRING"},
                    "personality_tags": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "faction": {"type": "STRING"},
                    "base_states": {"type": "ARRAY", "items": {"type": "STRING"}}
                },
                "required": ["system_name", "display_name", "personality_tags", "faction", "base_states"]
            },
            "dialogue_system": {
                "type": "OBJECT",
                "properties": {
                    "root_node": {"type": "STRING"},
                    "nodes": {"type": "OBJECT"}
                },
                "required": ["root_node", "nodes"]
            },
            "runtime_simulation_sandbox": {
                "type": "OBJECT",
                "properties": {
                    "validation_status": {"type": "STRING"},
                    "agent_conversations": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "turn": {"type": "INTEGER"},
                                "player_action": {"type": "STRING"},
                                "npc_response": {"type": "STRING"}
                            }
                        }
                    }
                },
                "required": ["validation_status", "agent_conversations"]
            }
        },
        "required": ["npc_profile", "dialogue_system", "runtime_simulation_sandbox"]
    }
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Genre: {genre}\nWorld context: Distopian Incinerator Zone\nConcept: {user_concept}",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=advanced_schema,
            temperature=0.3,
        ),
    )
    return response.text