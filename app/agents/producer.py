from app.agents.tool_router import tool_router
import json


class ProducerAgent:
    def __init__(self):
        self.router = tool_router

    def generate_story_architect(self, project_idea: str, duration_seconds: int = 60):
        """
        Story Architect Skill

        Analyze a project idea and generate the complete project structure as JSON.
        """

        system_prompt = """
You are "RBS Producer AI", an expert AI showrunner and screenwriter.
Your mission is to transform a raw project idea into a complete short-film structure.

STRICT RULES:
1. You must respond ONLY with a valid JSON object. Do not include any text before or after it.
2. The JSON format must match exactly the following structure:
{
    "synopsis": "A compelling story summary adapted to the requested duration.",
    "genre": "Main genre (e.g. Cyberpunk, Dark Fantasy)",
    "tone": "Overall atmosphere (e.g. Dark, Melancholic, Action)",
    "characters": [
        {
            "name": "Character name",
            "role": "Protagonist / Antagonist / Supporting",
            "description": "Detailed physical and psychological description.",
            "traits": ["Trait 1", "Trait 2"]
        }
    ],
    "locations": [
        {
            "name": "Location name",
            "description": "Detailed visual description of the environment."
        }
    ],
    "estimated_scenes": Approximate number of scenes required to fit the requested duration
}
3. Adjust the number of scenes to match the target duration.
"""

        user_prompt = f"""
Project idea: {project_idea}

Target duration: {duration_seconds} seconds.

Analyze the idea and generate the complete project structure in JSON format.
"""

        print("🧠 [Producer] Analyzing project idea with Qwen-Alibaba...")

        raw_response = self.router.generate(
            prompt=user_prompt,
            system_prompt=system_prompt
        )

        if not raw_response:
            print("❌ [Producer] No response received from the AI.")
            return None

        # Remove Markdown code fences before parsing the JSON response.
        try:
            clean_json = (
                raw_response
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            project_data = json.loads(clean_json)

            print("✅ [Producer] Project structure generated successfully.")
            return project_data

        except json.JSONDecodeError as e:
            print(f"❌ [Producer] Failed to parse JSON response: {e}")
            print(f"Raw response: {raw_response[:200]}...")
            return None


# Global instance
producer_agent = ProducerAgent()