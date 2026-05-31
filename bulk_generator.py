import json

from google import genai
from google.genai import types

def run_bulk_generator(blueprint_json_str: str, count: int = 5, api_key: str | None = None) -> list | str:
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    
    system_instruction = "You are an Efficient Game Content Copywriter. Output natural Korean dialogues as a JSON list."
    prompt = f"Generate {count} additional ambient/daily dialogues for this blueprint:\n{blueprint_json_str}"
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.7
        )
    )
    try:
        parsed = json.loads(response.text)
    except json.JSONDecodeError:
        return response.text

    return parsed if isinstance(parsed, list) else response.text
