from app.agents.tool_router import tool_router
import json


class CastingAgent:
    def __init__(self):
        self.router = tool_router

    def generate_characters(self, synopsis: str, duration_seconds: int):
        if duration_seconds <= 30:
            max_persos = 2
        elif duration_seconds <= 60:
            max_persos = 3
        elif duration_seconds <= 120:
            max_persos = 4
        else:
            max_persos = 5
        max_persos_plus_1 = max_persos + 1

        system_prompt = f"""
⚠️ LANGUAGE RULE — READ THIS FIRST, IT OVERRIDES EVERYTHING BELOW: Your ENTIRE response MUST
be written in the SAME language as the synopsis provided below. If the synopsis is in French,
respond entirely in French. If it is in English, respond entirely in English. Detect its
actual language and mirror it exactly.

You are a Short Drama Casting Director.

RULES:
1. Create up to {max_persos} DISTINCT MAIN characters (people/beings) maximum. This is a cap
   on featured, recurring characters with a full sheet — minor, one-off background characters
   may still appear later in the script without needing a sheet here.
2. Avoid heavy psychology. Keep it visual and conflict-driven.
3. DUAL-FORM RULE (mechanical, apply literally): if ONE of these {max_persos} characters has
   TWO distinct physical appearances (curse, transformation, animal ↔ human form, permanent
   disguise, etc.), you MUST create TWO separate JSON entries for THIS specific character —
   one per appearance, reusing the same first name followed by a form qualifier in parentheses
   (e.g. "Wren (Human Form)" and "Wren (Rabbit Form)"). This is the ONLY case where the total
   JSON array may contain {max_persos_plus_1} entries instead of {max_persos} — never more, and
   never for more than one character at a time. Each sheet must have its own "visual_trait"
   matching ONLY that specific appearance. In the "secret" field of EACH sheet, clearly state
   the link ("Secretly the same person as Wren (Rabbit Form), transformed by a curse") so it's
   usable downstream.
4. Respond ONLY with valid JSON.

Required JSON format:
{{
    "characters": [
        {{
            "name": "Character name",
            "alias": "Nickname or title if any (otherwise null)",
            "role": "Protagonist/Antagonist/Supporting",
            "age": "Approximate age (integer)",
            "traits": ["3 to 5 short personality traits (e.g. 'impulsive', 'loyal')"],
            "objective": "Immediate objective in 1 sentence",
            "visual_trait": "A distinctive visual feature recognizable within two seconds",
            "secret": "What the character is hiding",
            "arc_potential": "Character development potential for Season 2, in 1 sentence"
        }}
    ]
}}
"""
        user_prompt = f"Synopsis: {synopsis}. Duration: {duration_seconds}s."

        raw = self.router.generate(user_prompt, system_prompt)
        try:
            return json.loads(raw.replace("```json", "").replace("```", "").strip())
        except Exception:
            return None
