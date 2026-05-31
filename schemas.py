from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorldSetting(BaseModel):
    genre: str = "RPG"
    lore_summary: str = "Distopian Incinerator Zone"


class GenerateNpcRequest(BaseModel):
    world_setting: WorldSetting = Field(default_factory=WorldSetting)
    user_prompt: str
    max_dialogue_depth: int = Field(default=3, ge=1, le=8)
    client_api_key: str | None = Field(default=None, exclude=True, min_length=8)


class DialogueOption(BaseModel):
    option_text: str
    next_node_id: str
    required_conditions: dict[str, Any] = Field(default_factory=dict)


class DialogueNode(BaseModel):
    speaker: str
    state_context: str
    dialogue_text: str
    options: list[DialogueOption] = Field(default_factory=list)


class NpcProfile(BaseModel):
    system_name: str
    display_name: str
    personality_tags: list[str] = Field(default_factory=list)
    faction: str
    base_states: list[str] = Field(min_length=1)


class DialogueSystem(BaseModel):
    root_node: str
    nodes: dict[str, DialogueNode] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_node_links(self) -> "DialogueSystem":
        if self.root_node not in self.nodes:
            raise ValueError("dialogue_system.root_node must reference an existing node id")

        for node_id, node in self.nodes.items():
            for index, option in enumerate(node.options):
                if option.next_node_id and option.next_node_id not in self.nodes:
                    raise ValueError(
                        f"dialogue_system.nodes.{node_id}.options.{index}.next_node_id references a missing node"
                    )
        return self


class AgentConversation(BaseModel):
    turn: int
    player_action: str
    npc_response: str


class RuntimeSimulationSandbox(BaseModel):
    validation_status: str
    agent_conversations: list[AgentConversation] = Field(min_length=3)


class NpcBlueprint(BaseModel):
    model_config = ConfigDict(extra="allow")

    npc_profile: NpcProfile
    dialogue_system: DialogueSystem
    runtime_simulation_sandbox: RuntimeSimulationSandbox


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
