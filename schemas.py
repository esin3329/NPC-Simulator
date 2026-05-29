from pydantic import BaseModel, Field


class WorldSetting(BaseModel):
    genre: str = "RPG"
    lore_summary: str = "Distopian Incinerator Zone"


class GenerateNpcRequest(BaseModel):
    world_setting: WorldSetting = Field(default_factory=WorldSetting)
    user_prompt: str
    max_dialogue_depth: int = Field(default=3, ge=1, le=8)


DIALOGUE_OPTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "option_text": {"type": "STRING"},
        "next_node_id": {"type": "STRING"},
        "required_conditions": {"type": "OBJECT"},
    },
    "required": ["option_text", "next_node_id", "required_conditions"],
}


DIALOGUE_NODE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "speaker": {"type": "STRING"},
        "state_context": {"type": "STRING"},
        "dialogue_text": {"type": "STRING"},
        "options": {
            "type": "ARRAY",
            "items": DIALOGUE_OPTION_SCHEMA,
        },
    },
    "required": ["speaker", "state_context", "dialogue_text", "options"],
}


NPC_BLUEPRINT_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "npc_profile": {
            "type": "OBJECT",
            "properties": {
                "system_name": {"type": "STRING"},
                "display_name": {"type": "STRING"},
                "personality_tags": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
                "faction": {"type": "STRING"},
                "base_states": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
            },
            "required": [
                "system_name",
                "display_name",
                "personality_tags",
                "faction",
                "base_states",
            ],
        },
        "dialogue_system": {
            "type": "OBJECT",
            "properties": {
                "root_node": {"type": "STRING"},
                "nodes": {
                    "type": "OBJECT",
                    "additionalProperties": DIALOGUE_NODE_SCHEMA,
                },
            },
            "required": ["root_node", "nodes"],
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
                            "npc_response": {"type": "STRING"},
                        },
                        "required": ["turn", "player_action", "npc_response"],
                    },
                },
            },
            "required": ["validation_status", "agent_conversations"],
        },
    },
    "required": [
        "npc_profile",
        "dialogue_system",
        "runtime_simulation_sandbox",
    ],
}
