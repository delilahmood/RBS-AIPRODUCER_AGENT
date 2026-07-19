from app.agents.tool_router import tool_router
import json


class ShotBreakdownAgent:
    """Découpage technique (shot breakdown) : transforme le script en une
    liste de plans individuels — qui, où, quel mouvement de caméra, quelle
    durée (contrainte à 10s max, cohérent avec les limites Wan/HappyHorse).
    Miroir de CastingAgent/LocationScoutAgent, mais produit des Scene."""

    MAX_SHOT_DURATION = 10.0

    def __init__(self):
        self.router = tool_router

    def break_down_episode(self, script_content: str, episode_title: str,
                            characters: list, locations: list, is_last_episode: bool, is_serie: bool):
        """characters: liste de {id, name, role}. locations: liste de {id, name}.
        Retourne {"shots": [...]} ou None."""
        char_list_str = "\n".join(f"- {c['name']} (id={c['id']}, rôle: {c.get('role', '')})" for c in characters)
        loc_list_str = "\n".join(f"- {l['name']} (id={l['id']})" for l in locations) or "(aucun lieu identifié pour l'instant)"

        closing_rule = (
            "Le DERNIER plan de cet épisode doit se terminer sur un cliffhanger si c'est le dernier épisode "
            "de la saison ET qu'une suite est prévue ; sinon il doit clore proprement l'action de l'épisode."
            if is_last_episode else
            "Cet épisode n'est pas le dernier de la saison : son dernier plan peut se terminer sur une tension "
            "qui enchaîne naturellement vers l'épisode suivant."
        )

        system_prompt = f"""
Tu es un premier assistant réalisateur (1st AD) qui prépare le découpage technique (shot breakdown)
d'un Short Drama à partir du script final.

RÈGLES CRITIQUES :
1. Découpe le script en plans (shots) individuels, dans l'ordre chronologique.
2. Chaque plan doit durer AU MAXIMUM {self.MAX_SHOT_DURATION} secondes. Un plan trop long dans le script
   doit être scindé en plusieurs plans plus courts (ex: un dialogue de 20s = 2-3 plans).
3. Pour chaque plan, identifie les personnages RÉELLEMENT présents et visibles dans le cadre, en utilisant
   UNIQUEMENT les IDs de cette liste (ne jamais inventer d'ID) :
{char_list_str}
4. Pour chaque plan, identifie le lieu où il se déroule, en utilisant UNIQUEMENT les IDs de cette liste
   (mets null si aucun ne correspond clairement) :
{loc_list_str}
5. Décris le mouvement de caméra de façon concrète et professionnelle (ex: "low angle tracking shot, 35mm",
   "static wide shot", "handheld close-up push-in").
6. {closing_rule}
7. RÈGLE DE LANGUE : Réponds ENTIÈREMENT dans la même langue que celle utilisée dans le script fourni.
8. Réponds UNIQUEMENT en JSON valide.

Format JSON requis :
{{
    "shots": [
        {{
            "number": 1,
            "description": "Description visuelle concise de l'action du plan",
            "camera_movement": "Type de plan + mouvement de caméra",
            "mood": "Ambiance du plan en quelques mots",
            "dialogue": "Réplique(s) de ce plan, ou null si aucune",
            "character_ids": [liste d'IDs entiers des personnages visibles dans ce plan],
            "location_id": id entier du lieu, ou null,
            "duration_seconds": nombre (maximum {self.MAX_SHOT_DURATION}),
            "is_cliffhanger": true/false,
            "cliffhanger_description": "résumé du cliffhanger si is_cliffhanger est vrai, sinon null"
        }}
    ]
}}
"""
        user_prompt = f"Titre de l'épisode : {episode_title}\n\nScript :\n{script_content}"

        raw = self.router.generate(user_prompt, system_prompt)
        try:
            data = json.loads(raw.replace("```json", "").replace("```", "").strip())
            # Garde-fou : forcer la contrainte de durée même si le modèle a dérivé
            for shot in data.get("shots", []):
                if shot.get("duration_seconds", 0) and shot["duration_seconds"] > self.MAX_SHOT_DURATION:
                    shot["duration_seconds"] = self.MAX_SHOT_DURATION
            return data
        except Exception:
            return None
