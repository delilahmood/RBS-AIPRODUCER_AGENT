from app.agents.tool_router import tool_router
import json


class LocationScoutAgent:
    """Analyse le script (pas juste le synopsis, pour une liste fiable et
    dédupliquée) et en extrait les lieux distincts qui y sont réellement
    utilisés — miroir du CastingAgent, mais pour les décors."""

    def __init__(self):
        self.router = tool_router

    def scout_locations(self, script_texts: list, synopsis: str):
        combined_script = "\n\n---\n\n".join(script_texts)

        system_prompt = """
⚠️ LANGUAGE RULE — READ THIS FIRST: Your ENTIRE response MUST be written in ENGLISH,
regardless of the language the script is written in. Translate and adapt as needed — do
not respond in the script's original language.

You are a location scout for a Short Drama.

RULES:
1. Identify ONLY the locations actually used in the script provided — do not invent any.
2. Merge mentions of the same location into a single entry (e.g. "the manor" and "the
   manor's hallway" = one location if consistent), unless they are clearly distinct spaces.
3. Only include locations with real visual weight in the story — not fleeting mentions.
4. ⚠️ CRITICAL RULE — ENVIRONMENT ONLY, NEVER NARRATIVE: Every field ("description",
   "key_visual_details") must describe ONLY the physical space itself — its architecture,
   objects, lighting, atmosphere. NEVER mention any character by name, by role, or by
   pronoun referring to a specific person, and NEVER describe what happens there narratively
   (no "this is where X meets Y", no "X hides here", no actions or events). This location
   description will be used directly as an image prompt for an EMPTY environment with no
   people in it — any reference to a character or an event involving people will cause the
   image model to generate people in the scene, which must never happen.
   BAD example: "This eerie clocktower is where the cursed boy first meets the girl who broke his spell."
   GOOD example: "An eerie, time-forgotten clocktower frozen at midnight, filled with swirling dust
   and a magical cracked mirror embedded in the wall."
5. Respond ONLY in valid JSON.

Required JSON format:
{
    "locations": [
        {
            "name": "Short, clear location name",
            "description": "1-2 sentence narrative description of the SPACE ITSELF ONLY (no characters, no events)",
            "mood": "Mood/atmosphere in a few words (e.g. 'dark, oppressive')",
            "key_visual_details": "Recurring, striking visual elements of THIS SPACE ONLY (architecture, lighting, key objects) — no characters, no actions"
        }
    ]
}
"""
        user_prompt = f"Synopsis (context): {synopsis}\n\nFull script:\n{combined_script}"

        raw = self.router.generate(user_prompt, system_prompt)
        try:
            return json.loads(raw.replace("```json", "").replace("```", "").strip())
        except Exception:
            return None
