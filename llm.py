import json
import re
import time
import logging

from openai import OpenAI
from config import OPENAI_BASE_URL, OPENAI_API_KEY, PLANNER_MODEL

log = logging.getLogger(__name__)

client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are an autonomous drone flight planner controlling a Tello EDU drone.
Given a user instruction and current telemetry, output the commands to execute it.

Available commands:
  {"cmd": "move",   "direction": "forward|back|left|right|up|down", "cm": <int 20-500>}
  {"cmd": "rotate", "direction": "cw|ccw", "degrees": <int 1-360>}
  {"cmd": "hover",  "seconds": <float>}
  {"cmd": "flip",   "direction": "l|r|f|b"}

Rules:
1. Output ONLY valid JSON: {"commands": [...]}. No markdown. No explanation.
2. Max 8 commands per batch.
3. Battery < 20% -> return {"commands": [{"cmd": "hover", "seconds": 1}]} and warn nothing else.
4. 1 meter = 100 cm. Convert units as needed.
5. For a square of size X: move forward X, rotate cw 90, move forward X, rotate cw 90, move forward X, rotate cw 90, move forward X.
6. NEVER add a land or done command. Landing is handled exclusively by the user.
7. Only output movement commands. Nothing else.
"""

SAFE_HOVER = [{"cmd": "hover", "seconds": 2}]


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?|```", "", text).strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.error(f"JSON parse failed. Raw:\n{text}")
        return {"commands": SAFE_HOVER}


def plan_next_commands(goal: str, telemetry: dict, history: list) -> tuple:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {
            "role": "user",
            "content": (
                f"Instruction: {goal}\n"
                f"Telemetry: {json.dumps(telemetry)}\n\n"
                'Return ONLY: {"commands": [...]}'
            ),
        },
    ]

    try:
        t0 = time.perf_counter()
        response = client.chat.completions.create(
            model=PLANNER_MODEL,
            messages=messages,
            max_tokens=400,
            temperature=0.1,
        )
        t1 = time.perf_counter()

        raw = response.choices[0].message.content.strip()
        log.info(f"🤖 Raw: {raw}")

        t2 = time.perf_counter()
        parsed   = _parse_json(raw)
        commands = parsed.get("commands", parsed)
        t3 = time.perf_counter()

        if not isinstance(commands, list):
            commands = SAFE_HOVER

        # Strip any land/done commands the model sneaks in anyway
        commands = [c for c in commands if c.get("cmd") not in ("land", "done", "takeoff")]

        if not commands:
            commands = SAFE_HOVER

        llm_ms   = (t1 - t0) * 1000
        parse_ms = (t3 - t2) * 1000
        usage    = response.usage

        latency = {
            "llm_ms":            round(llm_ms, 1),
            "parse_ms":          round(parse_ms, 2),
            "total_ms":          round(llm_ms + parse_ms, 1),
            "prompt_tokens":     usage.prompt_tokens     if usage else None,
            "completion_tokens": usage.completion_tokens if usage else None,
            "tokens_per_sec":    round(usage.completion_tokens / (llm_ms / 1000), 1)
                                 if usage and llm_ms > 0 else None,
        }
        return commands, latency

    except Exception as e:
        log.error(f"LLM error: {e}")
        print(f"\n⚠️  LLM error: {e}")
        print(f"   Run:  ollama pull {PLANNER_MODEL}\n")
        dummy = {"llm_ms": 0, "parse_ms": 0, "total_ms": 0,
                 "prompt_tokens": None, "completion_tokens": None, "tokens_per_sec": None}
        return SAFE_HOVER, dummy