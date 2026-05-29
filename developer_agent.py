from google import genai
from google.genai import types

def run_developer_agent(blueprint_json_str: str) -> str:
    client = genai.Client()
    
    system_instruction = "You are an expert Unity C# Programmer. Output ONLY valid C# code block."
    prompt = f"Convert this JSON blueprint into a Unity C# FSM controller class:\n{blueprint_json_str}"
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1,
        ),
    )
    return response.text