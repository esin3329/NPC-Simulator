import json
import re
from typing import Any


CODE_FENCE_RE = re.compile(r"^```(?:csharp|cs|c#)?\s*|\s*```$", re.IGNORECASE)


def strip_code_fence(value: str) -> str:
    return CODE_FENCE_RE.sub("", str(value or "")).strip()


def _parse_json(value: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        return None, f"Blueprint JSON parsing failed: {exc.msg} at line {exc.lineno}, column {exc.colno}."

    if not isinstance(parsed, dict):
        return None, "Blueprint root must be a JSON object."
    return parsed, None


def _balanced_delimiters(code: str) -> list[str]:
    issues = []
    pairs = {"{": "}", "(": ")", "[": "]"}
    counts = {char: code.count(char) for char in "{}()[]"}

    for opener, closer in pairs.items():
        if counts[opener] != counts[closer]:
            issues.append(
                f"Unbalanced delimiters: found {counts[opener]} '{opener}' and {counts[closer]} '{closer}'."
            )
    return issues


def _validate_blueprint(blueprint: dict[str, Any]) -> list[str]:
    issues = []
    profile = blueprint.get("npc_profile")
    dialogue = blueprint.get("dialogue_system")
    sandbox = blueprint.get("runtime_simulation_sandbox")

    if not isinstance(profile, dict):
        issues.append("Missing or invalid npc_profile object.")
        profile = {}
    if not isinstance(dialogue, dict):
        issues.append("Missing or invalid dialogue_system object.")
        dialogue = {}
    if not isinstance(sandbox, dict):
        issues.append("Missing or invalid runtime_simulation_sandbox object.")
        sandbox = {}

    base_states = profile.get("base_states", [])
    if not isinstance(base_states, list) or not base_states:
        issues.append("npc_profile.base_states must be a non-empty list.")
        base_states = []

    nodes = dialogue.get("nodes", {})
    root_node = dialogue.get("root_node")
    if not isinstance(nodes, dict) or not nodes:
        issues.append("dialogue_system.nodes must be a non-empty object.")
        nodes = {}
    if not isinstance(root_node, str) or root_node not in nodes:
        issues.append("dialogue_system.root_node must point to an existing node id.")

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            issues.append(f"Node '{node_id}' must be an object.")
            continue

        state_context = node.get("state_context")
        if base_states and state_context not in base_states:
            issues.append(f"Node '{node_id}' uses unknown state_context '{state_context}'.")

        options = node.get("options", [])
        if not isinstance(options, list):
            issues.append(f"Node '{node_id}' options must be a list.")
            continue

        for index, option in enumerate(options):
            if not isinstance(option, dict):
                issues.append(f"Node '{node_id}' option {index} must be an object.")
                continue

            next_node_id = option.get("next_node_id")
            if next_node_id and next_node_id not in nodes:
                issues.append(f"Node '{node_id}' option {index} points to missing node '{next_node_id}'.")

    conversations = sandbox.get("agent_conversations", [])
    if not isinstance(conversations, list) or len(conversations) < 3:
        issues.append("runtime_simulation_sandbox.agent_conversations must include at least 3 turns.")

    return issues


def _validate_code(code: str) -> list[str]:
    issues = []
    clean_code = strip_code_fence(code)

    if not clean_code:
        return ["Generated C# code is empty."]

    issues.extend(_balanced_delimiters(clean_code))

    required_patterns = {
        "UnityEngine import": r"\busing\s+UnityEngine\s*;",
        "class declaration": r"\b(public\s+)?class\s+\w+",
        "MonoBehaviour inheritance": r":\s*MonoBehaviour\b",
        "enum state machine": r"\benum\s+\w+",
        "StartDialogue method": r"\bStartDialogue\s*\(",
        "ChooseOption method": r"\bChooseOption\s*\(\s*int\s+\w+",
        "condition checker": r"\b(CheckCondition|EvaluateCondition|MeetsCondition)\s*\(",
    }
    for label, pattern in required_patterns.items():
        if not re.search(pattern, clean_code):
            issues.append(f"Missing {label} in generated C# code.")

    if re.search(r"\b(TODO|placeholder)\b|\.\.\.", clean_code, re.IGNORECASE):
        issues.append("Generated C# code contains placeholder text.")

    return issues


def _severity_for_issue(issue: str) -> str:
    lower = issue.lower()
    if any(token in lower for token in ("parsing failed", "root must", "missing or invalid", "empty")):
        return "critical"
    if any(token in lower for token in ("missing", "unbalanced", "points to missing", "unknown state_context")):
        return "major"
    return "minor"


def _group_issues_by_severity(issues: list[str]) -> dict[str, list[str]]:
    grouped = {"critical": [], "major": [], "minor": []}
    for issue in issues:
        grouped[_severity_for_issue(issue)].append(issue)
    return grouped


def run_qa_agent(blueprint_json_str: str, code: str, attempt: int = 1) -> dict[str, Any]:
    issues = []
    schema_valid = True
    dialogue_tree_valid = True
    unity_code_valid = True

    blueprint, parse_error = _parse_json(blueprint_json_str)
    if parse_error:
        issues.append(parse_error)
        schema_valid = False
        dialogue_tree_valid = False
    elif blueprint is not None:
        blueprint_issues = _validate_blueprint(blueprint)
        issues.extend(blueprint_issues)
        schema_valid = not any(
            issue.startswith("Missing or invalid")
            or issue.startswith("Blueprint")
            or "must be a JSON object" in issue
            for issue in blueprint_issues
        )
        dialogue_tree_valid = not any("dialogue_system" in issue or issue.startswith("Node ") for issue in blueprint_issues)

    code_issues = _validate_code(code)
    issues.extend(code_issues)
    unity_code_valid = not code_issues

    issues_by_severity = _group_issues_by_severity(issues)
    critical_count = len(issues_by_severity["critical"])
    major_count = len(issues_by_severity["major"])
    minor_count = len(issues_by_severity["minor"])
    overall_score = max(0, 100 - critical_count * 35 - major_count * 15 - minor_count * 5)
    if critical_count:
        production_readiness = "FAILED"
    elif issues:
        production_readiness = "NEEDS_REVIEW"
    else:
        production_readiness = "READY"

    return {
        "agent": "qa_agent",
        "attempt": attempt,
        "status": "PASSED" if not issues else "FAILED",
        "issue_count": len(issues),
        "issues": issues,
        "overall_score": overall_score,
        "schema_valid": schema_valid,
        "dialogue_tree_valid": dialogue_tree_valid,
        "unity_code_valid": unity_code_valid,
        "production_readiness": production_readiness,
        "issues_by_severity": issues_by_severity,
    }


def run_self_healing_agent(blueprint_json_str: str, code: str, qa_report: dict[str, Any]) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client()

    system_instruction = (
        "You are a senior Unity C# repair agent. "
        "Return ONLY a complete corrected Unity C# code block. "
        "Do not explain your changes."
    )
    prompt = (
        "Repair the generated Unity C# FSM controller so it satisfies the QA report. "
        "Preserve the NPC behavior from the JSON blueprint and produce production-ready code.\n\n"
        f"JSON blueprint:\n{blueprint_json_str}\n\n"
        f"Current C# code:\n{code}\n\n"
        f"QA report:\n{json.dumps(qa_report, ensure_ascii=False, indent=2)}"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1,
        ),
    )
    return response.text
