from google import genai
from google.genai import types


def run_design_agent(
    user_prompt: str,
    genre: str = "RPG",
    lore_summary: str = "Distopian Incinerator Zone",
    max_dialogue_depth: int = 3,
    api_key: str | None = None,
) -> str:
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    
    system_instruction = (
        "You are an expert game designer & narrative director. "
        "Analyze the world concept and generate a fully realized NPC system profile, "
        "a branching dialogue tree, and a 3-turn virtual validation conversation log. "
        "System names, IDs, operators, and keys must be strictly in English, "
        "and display names, options, and dialogue texts must be beautifully written in Korean. "
        "Every dialogue node must match the documented schema: speaker, state_context, "
        "dialogue_text, and options. Every option must include option_text, next_node_id, "
        "and required_conditions."
    )

    contents = (
        f"Genre: {genre}\n"
        f"World context: {lore_summary}\n"
        f"Max dialogue depth: {max_dialogue_depth}\n"
        f"Concept: {user_prompt}\n\n"
        "Return exactly one JSON object with this contract:\n"
        "{\n"
        '  "npc_profile": {\n'
        '    "system_name": "english_snake_case_id",\n'
        '    "display_name": "Korean display name",\n'
        '    "personality_tags": ["Korean tag"],\n'
        '    "faction": "English faction id or name",\n'
        '    "base_states": ["Idle", "Guarded", "Trusting"]\n'
        "  },\n"
        '  "dialogue_system": {\n'
        '    "root_node": "root",\n'
        '    "nodes": {\n'
        '      "root": {\n'
        '        "speaker": "npc",\n'
        '        "state_context": "Idle",\n'
        '        "dialogue_text": "Korean line",\n'
        '        "options": [\n'
        '          {"option_text": "Korean option", "next_node_id": "node_2", "required_conditions": {}}\n'
        "        ]\n"
        "      },\n"
        '      "node_2": {\n'
        '        "speaker": "npc",\n'
        '        "state_context": "Guarded",\n'
        '        "dialogue_text": "Korean line",\n'
        '        "options": []\n'
        "      }\n"
        "    }\n"
        "  },\n"
        '  "runtime_simulation_sandbox": {\n'
        '    "validation_status": "READY",\n'
        '    "agent_conversations": [\n'
        '      {"turn": 1, "player_action": "Korean action", "npc_response": "Korean response"},\n'
        '      {"turn": 2, "player_action": "Korean action", "npc_response": "Korean response"},\n'
        '      {"turn": 3, "player_action": "Korean action", "npc_response": "Korean response"}\n'
        "    ]\n"
        "  }\n"
        "}\n\n"
        "Hard validation rules:\n"
        "- dialogue_system.nodes must be a non-empty object, not an array and not an empty object.\n"
        "- dialogue_system.root_node must be one of the keys in dialogue_system.nodes.\n"
        "- Every option.next_node_id must reference an existing key in dialogue_system.nodes.\n"
        "- Every node.state_context must be one of npc_profile.base_states.\n"
        "- runtime_simulation_sandbox.agent_conversations must contain at least 3 turns."
    )
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return response.text
