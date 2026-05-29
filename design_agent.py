from google import genai
from google.genai import types

from schemas import NPC_BLUEPRINT_RESPONSE_SCHEMA


def run_design_agent(
    user_prompt: str,
    genre: str = "RPG",
    lore_summary: str = "Distopian Incinerator Zone",
    max_dialogue_depth: int = 3,
) -> str:
    # 2.5-flash 무료 쿼터 및 결제 안정 환경으로 완벽 대응
    client = genai.Client()
    
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
        f"Concept: {user_prompt}"
    )
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=NPC_BLUEPRINT_RESPONSE_SCHEMA,
            temperature=0.3,
        ),
    )
    return response.text
