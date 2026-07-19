from app.agents.tool_router import tool_router
import json


class ShowrunnerAgent:
    def __init__(self):
        self.router = tool_router

    def generate_synopsis(
        self,
        idea: str,
        duration_seconds: int,
        project_format: str,
        genres: list = None,
        narrative_style: str = None,
    ):
        # Determine generation constraints based on the target duration.
        if duration_seconds <= 60:
            word_limit = "30 to 60 words (3 to 5 lines)"
            structure = "Inciting incident + Immediate obstacle + Ending cliffhanger"
            char_limit = 2
        elif duration_seconds <= 120:
            word_limit = "80 to 120 words (1 compact paragraph)"
            structure = "Opening hook + Dramatic turning point + Major cliffhanger"
            char_limit = 3
        else:
            word_limit = "150 to 250 words (2 to 3 paragraphs)"
            structure = (
                "Act 1 (Setup) + Act 2 (Confrontation) + "
                "Act 3 (Climax & Cliffhanger)"
            )
            char_limit = 4

        system_prompt = f"""
You are a world-class screenwriter and executive producer specializing in vertical short dramas
(ReelShort, TikTok Drama, Instagram Reels).

LANGUAGE RULE (HIGHEST PRIORITY):
Write your ENTIRE response (synopsis, hook, cliffhanger, and production_note)
in the SAME language as the ORIGINAL PROJECT IDEA provided by the user.

The project title may intentionally use another language for stylistic purposes.
Ignore the title when determining the output language and rely ONLY on the language
used in the project idea.

If the idea mixes multiple languages, use the dominant language.

YOUR MISSION:

1. Write a highly engaging synopsis optimized for a duration of {duration_seconds} seconds.

2. Evaluate your own synopsis as if you were an executive producer assessing
its commercial potential.

WRITING RULES:

1. No unnecessary exposition. Focus on action, conflict, and raw emotion.

2. Capture the audience immediately with the first sentence.

3. End with a powerful cliffhanger.

4. You MUST include every important element mentioned in the original idea
(characters, objects, locations, events).


5. GENRE, STORYTELLING STYLE (Narrative) & TONE RULE (CRITICAL) (CRITICAL):

The selected genres and narrative style are NOT decorative labels.
They must actively shape the plot, conflicts, pacing, atmosphere, and emotional impact.


The selected genres define WHAT story is told.

The selected Storytelling Style (Narrative style : First Person, Thirs Person or Dialogue Drive)
 defines HOW the synopsis must be narrated.

Apply the selected storytelling style consistently throughout the synopsis.

Storytelling Style rules:

• First Person
The synopsis must be narrated directly by the protagonist using "I".
Express personal emotions and thoughts naturally.

• Third Person
The synopsis must be narrated by an external narrator describing the protagonist and events.

• Dialogue Driven
The synopsis should be built primarily around character interactions and conversations.
Keep narration concise and let dialogue and emotional exchanges drive the story.

For Genre, for example,  if Romance is selected, the romantic tension
(attraction, jealousy, affection, heartbreak, impossible choices...)
must be a central driving force of the story.

If multiple genres are selected, blend them naturally into the same narrative
instead of focusing on only one.
6. Respond ONLY with valid JSON.

Required JSON format:

{{
    "synopsis": "{word_limit}",
    "hook": "A one-sentence hook that instantly grabs attention",
    "cliffhanger": "The final tension in one sentence",
    "production_note": {{
        "completion_rate_prediction": "Estimated completion rate (e.g. 85%)",
        "target_audience": "Target audience including age and interests",
        "viral_triggers": [
            "Three elements likely to make the content go viral"
        ],
        "series_potential": "Low / Medium / High with a one-sentence explanation",
        "monetization": "Recommended monetization strategy",
        "hook_strength": "Hook score out of 10",
        "cliffhanger_effectiveness": "Cliffhanger score out of 10"
    }}
}}

PRODUCTION NOTE GUIDELINES:

- completion_rate_prediction:
Estimate the percentage of viewers likely to watch until the end,
based on the strength of the hook and cliffhanger.

- target_audience:
Identify the ideal audience by age range and interests.

- viral_triggers:
List three specific elements that encourage sharing
(plot twist, emotional moment, iconic dialogue, visuals...).

- series_potential:
Evaluate whether the story naturally supports sequels
and explain why.

- monetization:
Recommend the most suitable strategy
(advertising, subscription, product placement, franchise...).

- hook_strength:
Score out of 10.
Any score below 7 indicates the hook should be rewritten.

- cliffhanger_effectiveness:
Score out of 10.
Any score below 8 indicates the ending should be stronger.

Example:

{{
    "completion_rate_prediction": "85%",
    "target_audience": "18–35 years old, fans of cyberpunk and psychological thrillers",
    "viral_triggers": [
        "Unexpected family twist",
        "Highly shareable neon aesthetic",
        "Iconic final line"
    ],
    "series_potential": "High - The mother protects an even darker secret that can be explored in future seasons.",
    "monetization": "In-stream advertising + ReelShort Season 2 subscription",
    "hook_strength": 9,
    "cliffhanger_effectiveness": 8
}}
"""

        genres_str = ", ".join(genres) if genres else "Not specified"
        style_str = narrative_style or "Not specified"

        user_prompt = (
            f"Project idea: {idea}. "
            f"Target duration: {duration_seconds} seconds. "
            f"Format: {project_format}. "
            f"Genres (to actively shape the story): {genres_str}. "
            f"Narrative style: {style_str}."
        )

        print("[Showrunner] Generating synopsis and production analysis...")

        raw = self.router.generate(user_prompt, system_prompt)

        try:
            clean_json = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)

        except json.JSONDecodeError as e:
            print(f"[Showrunner] JSON parsing error: {e}")
            print(f"Raw response: {raw[:300]}...")
            return None