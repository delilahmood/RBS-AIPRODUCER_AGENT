from app.agents.tool_router import tool_router
import os
import re
import requests

STORAGE_DIR = os.path.join("app", "static", "assets", "characters")
os.makedirs(STORAGE_DIR, exist_ok=True)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "character").strip().lower()).strip("-")
    return slug or "character"


class CharacterVisualizerAgent:
    """Génère des propositions d'images de personnage (portrait/closeup), en
    tenant compte du style visuel du projet (fusionné en un seul prompt si
    plusieurs styles sont sélectionnés — pas un jeu d'images par style) et du
    style de rendu des personnages extrait de l'image de référence (si fourni).

    Génère 2 propositions par personnage. Les images renvoyées par DashScope
    expirent sous 24h : elles sont donc immédiatement téléchargées et
    réhébergées de façon permanente (voir _download_and_store).
    """

    # Petites variations entre les 2 propositions, pour donner un vrai choix
    # plutôt que deux images quasi identiques.
    PROPOSAL_VARIANTS = [
        "front-facing portrait, neutral calm expression, soft studio lighting",
        "three-quarter view portrait, subtle intense expression, dramatic side lighting",
    ]

    def __init__(self):
        self.router = tool_router

    def _combined_style_label(self, visual_styles: list) -> str:
        if not visual_styles:
            return ""
        if len(visual_styles) == 1:
            return f"{visual_styles[0]} style"
        return " and ".join(visual_styles) + " hybrid style"

    def _build_prompt(self, character: dict, style_label: str, character_style_prompt: str, variant_index: int) -> str:
        traits = ", ".join(character.get("traits") or [])
        # Le nom peut porter une annotation de forme entre parenthèses (ex:
        # "Wren (Rabbit Form)") pour organiser les fiches d'un personnage à
        # double apparence — utile en base/affichage, mais dans LE PROMPT
        # IMAGE ça crée une ambiguïté (le modèle voit un nom humain "Wren" et
        # une étiquette "lapin" côte à côte, et produit un hybride). On la
        # retire ici : seul "visual_trait" doit porter la description visuelle.
        clean_name = re.sub(r"\s*\([^)]*\)\s*$", "", character.get("name", "character")).strip()

        parts = [
            f"{style_label} character portrait" if style_label else "character portrait",
            f"{clean_name}, {character.get('role', '')}",
            f"age {character['age']}" if character.get("age") else "",
            character.get("visual_trait") or "",
            f"personality: {traits}" if traits else "",
            self.PROPOSAL_VARIANTS[variant_index],
        ]
        if character_style_prompt:
            parts.append(character_style_prompt)
        parts.append("high quality, detailed, single character, clean background")

        return ", ".join(p for p in parts if p)

    def _download_and_store(self, remote_url: str, character_id: int, character_name: str, label: str) -> str:
        """Télécharge une image DashScope (lien expirant sous 24h) et la
        réhéberge de façon permanente sous static/assets/characters/.
        Retourne l'URL relative locale (ex: /static/assets/characters/...)."""
        slug = _slugify(character_name)
        ext = ".png"
        if "." in remote_url.split("?")[0].rsplit("/", 1)[-1]:
            ext = "." + remote_url.split("?")[0].rsplit(".", 1)[-1]
        filename = f"{character_id}_{slug}_{label}{ext}"
        local_path = os.path.join(STORAGE_DIR, filename)

        response = requests.get(remote_url, timeout=60)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)

        return f"/static/assets/characters/{filename}"

    def generate_proposals(self, character: dict, visual_styles: list, character_style_prompt: str = None,
                            batch_number: int = 1, model: str = None) -> list:
        """Retourne 2 propositions (style combiné, pas un jeu par style) :
        {proposal_number, url, prompt_used, model_used, duration_sec, error}
        — l'URL retournée est déjà permanente (téléchargée localement).
        model : 'wan2.2-t2i-plus' (défaut), 'wan2.6-t2i' ou 'wan2.7-image-pro'."""
        proposals = []
        style_label = self._combined_style_label(visual_styles)
        kwargs = {"model": model} if model else {}

        for i in range(2):
            prompt = self._build_prompt(character, style_label, character_style_prompt, i)
            result = self.router.generate_image(prompt, **kwargs)

            if result:
                try:
                    local_url = self._download_and_store(
                        result["url"], character.get("id"), character.get("name", "character"),
                        f"b{batch_number}p{i + 1}"
                    )
                    proposals.append({
                        "proposal_number": i + 1,
                        "url": local_url,
                        "prompt_used": prompt,
                        "model_used": result["model"],
                        "duration_sec": result["duration_sec"],
                        "error": False,
                    })
                except Exception as e:
                    print(f"❌ [CharacterVisualizer] Échec téléchargement image : {e}")
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
