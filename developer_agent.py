from google import genai
from google.genai import types

def run_developer_agent(blueprint_json_str: str, api_key: str | None = None) -> str:
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    
    system_instruction = (
        "You are an expert Unity C# gameplay programmer. "
        "Return ONLY one fenced C# code block and nothing outside the code block. "
        "The code must be immediately usable in Unity."
    )
    prompt = (
        "Convert this JSON blueprint into a complete Unity C# finite state machine controller.\n"
        "Hard requirements:\n"
        "- Include using UnityEngine;\n"
        "- Declare one public class whose name is derived from npc_profile.system_name and inherits MonoBehaviour.\n"
        "- Use an enum-based state machine for NPC states.\n"
        "- Include public void StartDialogue().\n"
        "- Include public void ChooseOption(int index).\n"
        "- Include a CheckCondition(...) method, or an equivalent condition-checking function with a clear name.\n"
        "- Store dialogue nodes and options in serializable C# data structures.\n"
        "- Implement state transitions from option next_node_id values.\n"
        "- Do not include TODO, placeholder text, ellipses, pseudocode, markdown explanations, or comments that describe missing work.\n"
        "- Do not write any prose outside the code block.\n\n"
        f"JSON blueprint:\n{blueprint_json_str}"
    )
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1,
        ),
    )
    return response.text
