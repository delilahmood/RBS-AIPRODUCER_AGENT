from app.agents.tool_router import tool_router


class StyleExtractorService:
    """Analyse une image de référence et en extrait un prompt de style
    textuel, structuré et réutilisable pour la génération visuelle future
    (personnages, storyboard...). Deux usages distincts :
    - 'world'     : ambiance, décor, palette, lumière (pas de personnage)
    - 'character' : style de rendu des personnages (medium, ombrage, trait)
    Toujours en anglais (langue des prompts image), et STRICTEMENT limité au
    style de rendu — jamais de description de la personne/du décor précis ou
    des vêtements, seulement medium/palette/lumière/qualité."""

    def __init__(self):
        self.router = tool_router

    def extract_style(self, image_path: str, kind: str) -> str:
        if kind == "world":
            focus = (
                "Describe the VISUAL STYLE of this reference image for a world/environment: "
                "artistic medium (e.g. digital painting, anime, realistic...), dominant color "
                "palette, lighting mood (dark, warm, cool, neon...), level of detail, overall "
                "composition/rendering technique. Do NOT describe the specific narrative content "
                "(this exact place) — ONLY the STYLE to reproduce for other settings in the same universe."
            )
        else:
            focus = (
                "Describe the VISUAL RENDERING STYLE of characters in this reference image: "
                "artistic medium, level of stylization (realistic, semi-realistic, anime, cartoon...), "
                "line/outline type, shading and lighting technique, typical color palette, overall "
                "rendering quality. Do NOT describe who this specific character is, their identity, "
                "their pose, or their clothing/outfit in any way — ONLY the rendering STYLE (medium, "
                "line work, shading, palette, quality) to apply to OTHER characters in the same universe."
            )

        system_prompt = f"""
⚠️ LANGUAGE RULE — READ THIS FIRST: Your ENTIRE response MUST be written in ENGLISH,
regardless of what language is used elsewhere in this project. This text is used
directly as an image-generation prompt, which requires English.

You are an art director preparing style guidelines for an AI image generation team.
{focus}

RULES:
1. Answer in 2 to 4 short, dense sentences, directly usable as a style prompt.
2. No formatting, no bullet points — just plain text ready to paste into a prompt.
3. STRICTLY style only: artistic medium, color palette, lighting/shading technique,
   line quality, level of detail, overall rendering quality. NEVER mention a person,
   their identity, their pose, or any clothing/outfit detail — that belongs to the
   character or location description, not to this style guideline.
"""
        user_prompt = "Analyze this image and give the corresponding style prompt."

        result = self.router.generate_vision(user_prompt, system_prompt, image_path)
        return result