from app.agents.tool_router import tool_router
import os
import re
import requests

STORAGE_DIR = os.path.join("app", "static", "assets", "locations")
os.makedirs(STORAGE_DIR, exist_ok=True)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "location").strip().lower()).strip("-")
    return slug or "location"


class LocationDesignAgent:
    """Génère des propositions d'image de décor, en tenant compte du style
    visuel du projet (fusionné en un seul prompt si plusieurs styles) et du
    style d'environnement extrait de l'image de référence World (si fourni).
    Miroir de CharacterVisualizerAgent, mais utilise world_style_prompt au
    lieu de character_style_prompt — les décors et les personnages ne
    partagent pas le même usage du style de référence."""

    PROPOSAL_VARIANTS = [
        "wide establishing shot, clear view of the whole space",
        "alternate angle, atmospheric lighting, same space",
    ]

    def __init__(self):
        self.router = tool_router

    def _combined_style_label(self, visual_styles: list) -> str:
        if not visual_styles:
            return ""
        if len(visual_styles) == 1:
            return f"{visual_styles[0]} style"
        return " and ".join(visual_styles) + " hybrid style"

    def _strip_character_mentions(self, text: str, character_names: list) -> str:
        """Retire toute mention explicite d'un nom de personnage du texte —
        la description d'un lieu (générée par Location Scout à partir du
        script) peut légitimement mentionner qui s'y trouve, mais ce texte
        sert ensuite de PROMPT IMAGE pour un décor qui doit rester vide de
        tout personnage. Ne pas se contenter de l'instruction "no characters"
        seule : un nom propre explicite dans le texte a plus de poids qu'une
        consigne négative générique."""
        if not text or not character_names:
            return text or ""
        cleaned = text
        for name in character_names:
            if not name:
                continue
            # Coupure sur les limites de mot, insensible à la casse
            cleaned = re.sub(rf"\b{re.escape(name)}\b", "someone", cleaned, flags=re.IGNORECASE)
        return cleaned

    def _build_prompt(self, location: dict, style_label: str, world_style_prompt: str, variant_index: int,
                       character_names: list = None) -> str:
        description = self._strip_character_mentions(location.get("description") or "", character_names)
        key_visual = self._strip_character_mentions(location.get("key_visual_details") or "", character_names)

        parts = [
            f"{style_label} environment concept art" if style_label else "environment concept art",
            location.get("name", "location"),
            description,
            f"mood: {location.get('mood')}" if location.get("mood") else "",
            key_visual,
            self.PROPOSAL_VARIANTS[variant_index],
        ]
        if world_style_prompt:
            parts.append(world_style_prompt)
        parts.append("empty environment with absolutely no people, no characters, no figures, no silhouettes — pure architecture and landscape only, high quality, detailed")

        return ", ".join(p for p in parts if p)

    def _download_and_store(self, remote_url: str, location_id: int, location_name: str, label: str) -> str:
        slug = _slugify(location_name)
        ext = ".png"
        if "." in remote_url.split("?")[0].rsplit("/", 1)[-1]:
            ext = "." + remote_url.split("?")[0].rsplit(".", 1)[-1]
        filename = f"{location_id}_{slug}_{label}{ext}"
        local_path = os.path.join(STORAGE_DIR, filename)

        response = requests.get(remote_url, timeout=60)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)

        return f"/static/assets/locations/{filename}"

    def generate_proposals(self, location: dict, visual_styles: list, world_style_prompt: str = None,
                            batch_number: int = 1, character_names: list = None, model: str = None) -> list:
        """Retourne 2 propositions : {proposal_number, url, prompt_used,
        model_used, duration_sec, error} — URL déjà permanente (téléchargée).
        character_names : noms de tous les personnages du projet, pour
        s'assurer qu'aucun n'apparaît dans le prompt du décor.
        model : 'wan2.2-t2i-plus' (défaut), 'wan2.6-t2i' ou 'wan2.7-image-pro'."""
        proposals = []
        style_label = self._combined_style_label(visual_styles)
        kwargs = {"model": model} if model else {}

        for i in range(2):
            prompt = self._build_prompt(location, style_label, world_style_prompt, i, character_names)
            result = self.router.generate_image(prompt, **kwargs)

            if result:
                try:
                    local_url = self._download_and_store(
                        result["url"], location.get("id"), location.get("name", "location"),
                        f"b{batch_number}p{i + 1}"
                    )
                    proposals.append({
                        "proposal_number": i + 1, "url": local_url, "prompt_used": prompt,
                        "model_used": result["model"], "duration_sec": result["duration_sec"], "error": False,
                    })
                except Exception as e:
                    print(f"❌ [LocationDesign] Échec téléchargement image : {e}")
                    proposals.append({
                        "proposal_number": i + 1, "url": None, "prompt_used": prompt,
                        "model_used": result["model"], "duration_sec": result["duration_sec"], "error": True,
                    })
            else:
                proposals.append({
                    "proposal_number": i + 1, "url": None, "prompt_used": prompt,
                    "model_used": "wan2.2-t2i-plus", "duration_sec": None, "error": True,
                })
        return proposals
