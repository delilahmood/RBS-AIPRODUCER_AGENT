from app.agents.tool_router import tool_router
from app.agents.character_visualizer import STORAGE_DIR, _slugify
import os
import requests
import base64


AVAILABLE_SHEET_MODELS = [
    "qwen-image-edit-plus",  # défaut : le plus fiable sur nos tests (respect strict de la
                             # consigne "4 panneaux", cohérence des couleurs d'yeux/fond)
    "qwen-image-edit-max",
    "qwen-image-2.0-pro",
    "qwen-image-2.0",
    "wan2.7-image-pro",
]
DEFAULT_SHEET_MODEL = "qwen-image-edit-plus"


class CharacterSheetAgent:
    """Construit le Model Sheet (planche de référence turnaround) d'un
    personnage à partir de son portrait déjà sélectionné. Un seul appel
    image-à-image, sans texte/légendes demandées au modèle (le rendu de
    texte par l'IA est peu fiable — la mise en forme éventuelle se fera
    par-dessus, pas par le modèle lui-même)."""

    SHEET_SIZE = "1664*936"  # 16:9

    def __init__(self):
        self.router = tool_router

    def _build_prompt(self, character: dict, style_label: str, character_style_prompt: str) -> str:
        traits = ", ".join(character.get("traits") or [])
        parts = [
            "Character turnaround model sheet, same character as the reference image, "
            "consistent identity, outfit, and proportions across all views",
            "exactly 4 panels arranged in a clean horizontal row: "
            "(1) FULL BODY front view, head to feet fully visible, standing straight, neutral pose, "
            "(2) FULL BODY side/profile view, head to feet fully visible, "
            "(3) FULL BODY back view, head to feet fully visible, "
            "(4) close-up face portrait, shoulders up",
            "every full body panel must show the entire figure from head to feet with visible ground/feet, "
            "not cropped at the waist or knees",
            f"{style_label} style" if style_label else "",
            character.get("visual_trait") or "",
            f"personality: {traits}" if traits else "",
            character_style_prompt or "",
            "plain neutral flat background, consistent lighting across all views, "
            "purely visual reference sheet with no annotations, no sketches, no captions, no watermark",
        ]
        return ", ".join(p for p in parts if p)

    def _download_and_store(self, remote_url: str, character_id: int, character_name: str, label: str) -> str:
        slug = _slugify(character_name)
        ext = ".png"
        if "." in remote_url.split("?")[0].rsplit("/", 1)[-1]:
            ext = "." + remote_url.split("?")[0].rsplit(".", 1)[-1]
        filename = f"{character_id}_{slug}_{label}{ext}"
        local_path = os.path.join(STORAGE_DIR, filename)

        response = requests.get(remote_url, timeout=90)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)

        return f"/static/assets/characters/{filename}"

    def generate_sheet(self, character: dict, portrait_path: str, visual_styles: list,
                        character_style_prompt: str = None, model: str = None,
                        batch_number: int = 1) -> dict:
        """Génère UNE planche à partir du portrait local (chemin disque, pas
        URL). Retourne {url, prompt_used, model_used, duration_sec, error}."""
        model = model if model in AVAILABLE_SHEET_MODELS else DEFAULT_SHEET_MODEL
        style_label = " + ".join(visual_styles) if visual_styles else ""
        prompt = self._build_prompt(character, style_label, character_style_prompt)

        result = self.router.generate_image_edit(prompt, [portrait_path], model=model, size=self.SHEET_SIZE)

        if not result:
            return {"url": None, "prompt_used": prompt, "model_used": model, "duration_sec": None, "error": True}

        try:
            local_url = self._download_and_store(
                result["url"], character.get("id"), character.get("name", "character"),
                f"sheet_b{batch_number}"
            )
            return {
                "url": local_url, "prompt_used": prompt, "model_used": model,
                "duration_sec": result["duration_sec"], "error": False,
            }
        except Exception as e:
            print(f"❌ [CharacterSheet] Échec téléchargement de la planche : {e}")
            return {"url": None, "prompt_used": prompt, "model_used": model, "duration_sec": result["duration_sec"], "error": True}
