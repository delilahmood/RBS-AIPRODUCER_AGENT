from app.agents.tool_router import tool_router
import os
import json
import requests

STORAGE_DIR = os.path.join("app", "static", "assets", "storyboards")
os.makedirs(STORAGE_DIR, exist_ok=True)

# Même famille de modèles que le Model Sheet des personnages — l'utilisateur
# choisit, avec le même défaut (le plus fiable sur nos tests).
AVAILABLE_STORYBOARD_MODELS = [
    "qwen-image-edit-plus",
    "qwen-image-edit-max",
    "qwen-image-2.0-pro",
    "qwen-image-2.0",
    "wan2.7-image-pro",
]
DEFAULT_STORYBOARD_MODEL = "qwen-image-edit-plus"


class StoryboardArtAgent:
    """Génère l'image de repérage (storyboard) d'un plan, en combinant les
    images DÉJÀ SÉLECTIONNÉES des personnages présents (closeup ET fullbody —
    le fullbody porte l'info vêtements/silhouette que le closeup n'a pas) et
    du décor du plan comme références. Deux modes :
    - 'single' : une image, la composition du plan
    - 'grid'   : une grille 3x3 montrant la progression du plan dans le temps,
                 avec une vraie variété de plans/angles (pas 9 fois le même cadrage)

    L'agent se comporte comme un storyboard artist professionnel : maîtrise
    des tailles de plan (wide/medium/close-up/extreme close-up), des angles
    de caméra (low/high/eye-level/dutch tilt/over-the-shoulder) et de la
    lumière — inspiré directement d'exemples de production réels
    (PixVerse/Seedance) partagés par l'utilisateur.
    """

    def __init__(self):
        self.router = tool_router

    def _expand_shot_to_beats(self, shot: dict, num_beats: int = 9, character_names: list = None) -> list:
        """Décompose un plan unique en N panneaux de storyboard professionnel,
        avec variété réelle de plans/angles — pas une simple progression
        narrative répétitive. Ne bloque jamais : liste vide si échec, auquel
        cas on repasse silencieusement en mode single-scene."""
        chars_note = ""
        if character_names:
            chars_note = (
                f"Characters present in this shot: {', '.join(character_names)}. "
                f"If there is more than one character, ALTERNATE between them across panels "
                f"(shot / reverse-shot pattern) rather than always framing everyone together."
            )

        system_prompt = f"""
You are a professional storyboard artist and cinematographer, fluent in film grammar:
shot sizes (wide shot, medium shot, close-up, extreme close-up), camera angles (low angle,
high angle, eye-level, dutch tilt, over-the-shoulder), and lighting (key/fill/rim light,
silhouette, practicals).

Break down ONE shot into exactly {num_beats} sequential panels for a professional cinematic
storyboard grid.

RULES:
1. Each panel MUST use a DIFFERENT shot size and/or camera angle than its neighbors — vary
   the coverage like a real storyboard (e.g. wide establishing, then medium, then close-up,
   then a reaction shot, then back to wide). Never repeat the same framing across all panels.
2. {chars_note}
3. Stay strictly faithful to the shot's description, camera movement, and mood provided — do
   not invent a different scene or new characters.
4. For each panel, briefly state the shot size/angle AND the action or expression happening
   (e.g. "Low angle medium shot: Kael raises his sword, eyes fierce").
5. Respond ONLY in valid JSON, in the same language as the description provided.

Format: {{"beats": ["panel 1: shot size/angle + action/expression", ...]}}
(exactly {num_beats} entries)
"""
        user_prompt = (
            f"Shot description: {shot.get('description') or ''}\n"
            f"Camera movement: {shot.get('camera_movement') or ''}\n"
            f"Mood: {shot.get('mood') or ''}"
        )
        raw = self.router.generate(user_prompt, system_prompt)
        try:
            data = json.loads(raw.replace("```json", "").replace("```", "").strip())
            beats = data.get("beats", [])
            return beats[:num_beats] if beats else []
        except Exception:
            return []

    def _build_prompt(self, shot: dict, style_label: str, mode: str = "single", beats: list = None) -> str:
        parts = [
            "You are a professional storyboard artist translating a script shot into a visual "
            "storyboard panel, using proper film grammar (shot size, camera angle, lighting) — "
            "not a generic illustration.",
            "CHARACTER IDENTITY LOCK: same characters and same environment as the reference "
            "images provided — do not alter their face, outfit, proportions, or defining features.",
            f"SCENE: {shot.get('description') or ''}",
        ]
        if shot.get("mood"):
            parts.append(f"MOOD: {shot['mood']}")

        if mode == "grid" and beats:
            beats_str = "; ".join(f"Panel {i + 1} — {b}" for i, b in enumerate(beats))
            parts.append(f"BEATS: {beats_str}")
            parts.append(
                "COMPOSITION: arrange as a clean 3x3 grid of 9 sequential panels, each with a "
                "DISTINCT shot size and/or camera angle (mix wide/medium/close-up and "
                "eye-level/low/high angle across panels) — a professional storyboard grid with "
                "real cinematic variety, not 9 repeats of the same framing."
            )
        else:
            parts.append(
                "COMPOSITION: single cinematic frame representing this shot, using the shot size "
                "and camera angle implied by the camera movement below."
            )

        if shot.get("camera_movement"):
            parts.append(f"CINEMATOGRAPHY: {shot['camera_movement']}")
        if style_label:
            parts.append(f"STYLE: {style_label} style, cinematic painterly composition")

        parts.append(
            "RULES: no panel borders rendered, no dividing lines, no text, no captions, "
            "no numbers, no watermark, no dialogue bubbles."
        )
        return " ".join(parts)

    def _download_and_store(self, remote_url: str, scene_id: int, label: str) -> str:
        ext = ".png"
        if "." in remote_url.split("?")[0].rsplit("/", 1)[-1]:
            ext = "." + remote_url.split("?")[0].rsplit(".", 1)[-1]
        filename = f"scene{scene_id}_{label}{ext}"
        local_path = os.path.join(STORAGE_DIR, filename)

        response = requests.get(remote_url, timeout=90)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)

        return f"/static/assets/storyboards/{filename}"

    def generate_storyboard_frame(self, shot: dict, reference_image_paths: list, visual_styles: list,
                                   model: str = None, batch_number: int = 1, mode: str = "single",
                                   character_names: list = None) -> dict:
        """mode: 'single' (une image) ou 'grid' (grille 3x3 de progression).
        reference_image_paths : idéalement closeup ET fullbody par personnage
        + décor (voir appelant). character_names : pour l'alternance shot/
        reverse-shot en mode grille si plusieurs personnages.
        Retourne {url, prompt_used, model_used, duration_sec, error}."""
        model = model if model in AVAILABLE_STORYBOARD_MODELS else DEFAULT_STORYBOARD_MODEL
        style_label = " + ".join(visual_styles) if visual_styles else ""

        beats = None
        if mode == "grid":
            beats = self._expand_shot_to_beats(shot, num_beats=9, character_names=character_names)
            if not beats:
                mode = "single"  # repli silencieux si l'expansion échoue

        prompt = self._build_prompt(shot, style_label, mode=mode, beats=beats)

        if not reference_image_paths:
            result = self.router.generate_image(prompt)
        else:
            result = self.router.generate_image_edit(prompt, reference_image_paths, model=model)

        if not result:
            return {"url": None, "prompt_used": prompt, "model_used": model, "duration_sec": None, "error": True}

        try:
            local_url = self._download_and_store(result["url"], shot.get("id"), f"b{batch_number}")
            return {
                "url": local_url, "prompt_used": prompt, "model_used": result.get("model", model),
                "duration_sec": result["duration_sec"], "error": False,
            }
        except Exception as e:
            print(f"❌ [StoryboardArt] Échec téléchargement de l'image : {e}")
            return {"url": None, "prompt_used": prompt, "model_used": model, "duration_sec": result["duration_sec"], "error": True}
