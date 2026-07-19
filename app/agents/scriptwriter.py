from app.agents.tool_router import tool_router
import json


class ScriptwriterAgent:
    def __init__(self):
        self.router = tool_router

    def _word_limit(self, duration_seconds: int) -> str:
        if duration_seconds <= 60:
            return "120 and 150 words"
        elif duration_seconds <= 120:
            return "240 and 300 words"
        else:
            return "360 and 450 words"

    def generate_episodes(
        self,
        synopsis: str,
        hook: str,
        characters: list,
        duration_seconds: int,
        episode_count: int,
        is_serie: bool,
        genres: list = None,
        narrative_style: str = None,
    ):
        """
        Generate the complete season in a single request to preserve narrative
        consistency between episodes.
        
        

        - Episode 1 starts directly from the project's hook.
        - Every episode ends with a cliffhanger except the last one.
        - The final episode ends with a cliffhanger only if another season is planned.
          Otherwise, the story must conclude completely.
        """

        word_limit = self._word_limit(duration_seconds)

        def _storytelling_instruction(style: str) -> str:
            if not style:
                return ""

            style = style.strip().lower()

            if style == "first person":
                return """
        7. STORYTELLING STYLE (MANDATORY): FIRST PERSON

        - Write the entire script from the protagonist's point of view.
        - Whenever narration is used, it must use first-person ("I", "me", "my").
        - Allow the audience to experience the protagonist's emotions and thoughts directly.
        - Never switch to third-person narration.
        - Dialogue should remain natural.
        """

            elif style == "third person":
                return """
        7. STORYTELLING STYLE (MANDATORY): THIRD PERSON — VOICEOVER NARRATION ONLY

        - The ENTIRE episode must be written as continuous third-person VOICEOVER NARRATION,
          like a narrator describing the story — NOT character dialogue.
        - Do NOT include ANY character dialogue lines. No "NAME: ..." lines at all in this mode.
          Anything a character would have said must instead be conveyed through narration
          (e.g. write "She begged him to stay" — never a spoken line in quotes or dialogue format).
        - Use [ACTION] blocks only, each describing one short, vivid visual beat — written so
          each block can later map cleanly onto a single filmed shot.
        - Keep the tone cinematic and objective, like a documentary or trailer narrator — not
          the character's own inner voice (that would be First Person).
        - Never use first-person narration ("I", "we").
        """

            elif style == "dialogue driven":
                return """
        7. STORYTELLING STYLE (MANDATORY): DIALOGUE DRIVEN

        - Dialogue is the primary storytelling device.
        - Most scenes should be driven by conversations.
        - Keep narration concise.
        - Avoid long descriptive paragraphs.
        - Every conversation must:
            • advance the story,
            • reveal character,
            • increase emotion,
            • or create suspense.
        - Let dialogue carry the emotional weight of the episode.
        """

            return ""

        closing_rule = (
            "The LAST episode must end with a cliffhanger that naturally sets up the next season."
            if is_serie
            else
            "The LAST episode must fully conclude the story with a satisfying resolution. "
            "No unanswered questions and no cliffhanger."
        )

        genres_str = ", ".join(genres) if genres else "Not specified"

        storytelling_instruction = _storytelling_instruction(narrative_style)

        system_prompt = f"""
        You are an expert screenwriter specializing in vertical short dramas
        (ReelShort, TikTok, DramaBox style).

        The selected genres and storytelling style are mandatory creative constraints.

        Genres:
        {genres_str}

        RULES:

        1. Generate EXACTLY {episode_count} episode(s), numbered from 1 to {episode_count}.

        2. Each episode must contain between {word_limit}.

        3. Use [ACTION] for action descriptions and UPPERCASE character names for dialogue —
        UNLESS the storytelling style below says otherwise (e.g. Third Person = voiceover only, no dialogue lines).

        4. STORY STRUCTURE (CRITICAL):
        - Episode 1 must begin immediately after this hook:
            "{hook}"

        - Every episode except the last must end with a strong cliffhanger that makes
            the audience want to continue immediately.

        - For every cliffhanger, provide a one-sentence summary inside
            "cliffhanger_description". This sentence will be used as the opening context
            for the following episode, so it must accurately summarize the ending.

        - The following episode must continue directly from the previous cliffhanger.
            Do not introduce unexplained time skips.

        - {closing_rule}

        5. GENRES (MANDATORY)

        The selected genres must influence:
        - the tone,
        - the pacing,
        - the atmosphere,
        - the conflicts,
        - the dialogue,
        - the emotional progression.

        Never ignore the selected genres.

        6. LANGUAGE RULE

        Write EVERYTHING (titles, scripts and descriptions) in the SAME language as the provided synopsis.

        {storytelling_instruction}

        7. Respond ONLY with valid JSON.

        Do not include any explanation outside the JSON.

        Required JSON format:

        {{
            "episodes": [
                {{
                    "episode_number": 1,
                    "title": "Highly engaging episode title",
                    "script_content": "Complete formatted script",
                    "ends_with_cliffhanger": true,
                    "cliffhanger_description": "One-sentence cliffhanger summary (null if none)"
                }}
            ]
        }}
        """


        user_prompt = f"""
        Synopsis:
        {synopsis}

        Characters:
        {characters}

        Genres:
        {genres_str}

        Storytelling Style:
        {narrative_style}

        Number of episodes:
        {episode_count}
        """

        raw = self.router.generate(user_prompt, system_prompt)

        try:
            data = json.loads(
                raw.replace("```json", "").replace("```", "").strip()
            )

            episodes = data.get("episodes", [])

            # Safety check to ensure the final episode follows the expected ending rule.
            if episodes and not is_serie:
                episodes[-1]["ends_with_cliffhanger"] = False
                episodes[-1]["cliffhanger_description"] = None

            return {"episodes": episodes}

        except Exception:
            return None