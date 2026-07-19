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

# Modes de panneaux disponibles côté interface. "one_frame" reste à part
# (jamais de décomposition). "auto" laisse le Prompt Director choisir lui-même
# entre 4/6/9 selon la densité d'action — indisponible en mode template seul
# (repli sur 3x3 dans ce cas, voir generate_storyboard_frame).
PANEL_MODE_CONFIG = {
    "2x2": {"panel_count": 4, "layout": "2x2"},
    "3x3": {"panel_count": 9, "layout": "3x3"},
}


class StoryboardArtAgent:
    """Génère l'image de repérage (storyboard) d'un plan. Système HYBRIDE :

    - mode "one_frame" : une seule image, ancrage vision léger (1 image, 1 appel)
    - mode "2x2"/"3x3"/"auto" :
        * use_prompt_director=True (défaut) : Qwen VL (qwen3.7-plus) VOIT
          réellement les fiches personnages (closeup+fullbody) ET le décor,
          et conçoit les panneaux en conséquence — ancré dans ce qui EXISTE
          vraiment, pas dans une description texte qui peut avoir dérivé.
          En "auto", il choisit lui-même 4/6/9 panneaux selon la densité
          d'action ; en "2x2"/"3x3" il respecte le compte imposé.
        * use_prompt_director=False : ancien template texte seul (moins cher,
          plus rapide), compte de panneaux fixé par le mode (9 par défaut si
          "auto" est demandé sans Prompt Director, puisque le texte seul ne
          sait pas juger la densité d'action aussi finement).

    Repli automatique et silencieux vers le template texte si l'appel vision
    échoue — la génération n'est jamais bloquée.
    """

    def __init__(self):
        self.router = tool_router

    # ------------------------------------------------------------------
    # Ancrage léger (mode one_frame) — inchangé depuis la version précédente
    # ------------------------------------------------------------------
    def _ground_character_appearance(self, reference_image_path: str) -> str:
        """Vision call sur UNE image de référence (la première de la liste,
        pour limiter le coût à +1 appel par génération plutôt que +1 par
        personnage) pour vérifier ce qu'elle montre RÉELLEMENT, plutôt que de
        se fier uniquement au texte "visual_trait" qui peut être incomplet ou
        avoir dérivé de ce que l'image a effectivement produit. Retourne une
        description courte, ou chaîne vide si échec (ne bloque jamais)."""
        system_prompt = """
You are a visual continuity checker for a storyboard artist.
Look at this reference image and describe in 1-2 short sentences exactly what
it shows: the character's face, hair, outfit, and any distinctive visual
features actually visible in the image. Be concrete and specific — this
description will be used to keep the character's appearance consistent in a
new storyboard panel. Respond in plain text, no JSON, no preamble.
"""
        result = self.router.generate_vision("Describe this reference image.", system_prompt, reference_image_path)
        return result.strip() if result else ""

    # ------------------------------------------------------------------
    # Prompt Director (vision, multi-images) — nouveau
    # ------------------------------------------------------------------
    def _analyze_shot_with_vision(self, shot: dict, structured_characters: list, structured_location: dict,
                                   character_names: list, previous_shot: dict, next_shot: dict,
                                   style_label: str, forced_panel_count: int = None,
                                   forced_layout: str = None) -> dict:
        """Qwen VL (qwen3.7-plus) voit RÉELLEMENT les fiches personnages
        (closeup+fullbody) et le décor, et conçoit les panneaux du storyboard
        en conséquence — ancré dans ce que les références montrent vraiment,
        pas dans une description texte qui peut avoir dérivé de l'image
        générée. Retourne {} si aucune image disponible ou si l'appel échoue
        (repli silencieux vers _expand_shot_to_beats côté appelant)."""
        image_labels = []
        for char in (structured_characters or []):
            name = char.get("name", "Character")
            if char.get("closeup_path"):
                image_labels.append((f"CHARACTER — {name} (closeup):", char["closeup_path"]))
            if char.get("fullbody_path"):
                image_labels.append((f"CHARACTER — {name} (fullbody):", char["fullbody_path"]))
        if structured_location and structured_location.get("path"):
            loc_name = structured_location.get("name", "Location")
            image_labels.append((f"LOCATION — {loc_name}:", structured_location["path"]))

        if not image_labels:
            return {}

        if forced_panel_count:
            panel_instruction = f'You MUST use exactly {forced_panel_count} panels, laid out as "{forced_layout}".'
        else:
            panel_instruction = (
                "Decide how many panels this shot needs based on its duration and action density:\n"
                '  4 panels (layout "2x2") for shots <= 6s or a single simple beat;\n'
                '  6 panels (layout "2x3") for 7-8s or moderate action;\n'
                '  9 panels (layout "3x3") for 9-10s or dense, evolving action.\n'
                "Never pad with redundant panels: fewer meaningful panels beat many repetitive ones."
            )

        panel_count_hint = str(forced_panel_count) if forced_panel_count else "4 | 6 | 9"
        layout_hint = f'"{forced_layout}"' if forced_layout else '"2x2" | "2x3" | "3x3"'

        system_prompt = f"""
You are a professional storyboard artist and cinematographer, fluent in film grammar:
shot sizes (wide, medium, close-up, extreme close-up), camera angles (low, high,
eye-level, dutch tilt, over-the-shoulder), and lighting. You also think like a
director about WHY a shot exists in the story.

You can SEE the actual production references for this shot: the character sheets
(closeup and fullbody) and the location plate. These images define what EXISTS.
Your job is to design the storyboard grid for ONE shot, grounded in these references.

REFERENCE GROUNDING (CRITICAL):
- The references are the single source of truth for appearance: outfits, props,
  physical features, and the set's actual layout, depth and lighting.
- Your beats must be EXECUTABLE with what the references show. Anchor actions and
  compositions in real visible elements (e.g. "she grips the torn edge of her cloak",
  "leaning against the lamppost on the left of the location plate") — never stage an
  action requiring a prop, costume piece or set element that no reference contains.
  If the shot description mentions an object absent from all references, stage it
  minimally and generically, without inventing distinctive details.
- You DIRECT, you do not DESCRIBE: never re-describe the characters' appearance or
  the set in your beats — the reference images already carry that. Each beat states
  only shot size/angle + action/expression/staging.

PANEL COUNT:
{panel_instruction}

VISUAL STYLE:
- The project's visual style is provided as input (e.g. manhwa, anime, realistic,
  gothic painterly). Adapt your CINEMATOGRAPHIC GRAMMAR to it: manhwa/anime styles
  favor bold, expressive coverage (extreme angles, dramatic close-ups on eyes,
  dutch tilts, exaggerated reaction framings); realistic styles demand restrained,
  grounded coverage (subtle expressions, natural angles, measured camera moves).
- NEVER describe the rendering style itself in the beats (no "in anime style", no
  "manhwa linework") — the reference images and the downstream image prompt already
  enforce the visual style. Your beats direct framing, action and emotion only.

STORYBOARD RULES:
1. Panels are sequential in time and each uses a DIFFERENT shot size and/or angle
   than its neighbors — real cinematic coverage, never the same framing twice in a row.
2. If several characters are present, ALTERNATE between them (shot/reverse-shot),
   assigning the right emotion to the right face at the right moment, consistent
   with the faces shown in the character references.
3. Stay strictly faithful to the shot's description, camera movement and mood —
   do not invent new events or characters.
4. If dialogue is provided, the panels covering it show the speaking/listening
   expressions and staging — never text, captions or speech bubbles.
5. If the shot is a cliffhanger, the FINAL panel must land exactly on the
   cliffhanger moment, framed for maximum impact.
6. Use the continuity context (previous/next shot) if provided: the first panel
   must inherit the visual state coming from the previous shot (transformation
   stage, injuries, objects held), and the last panel must hand over cleanly to
   the next.
7. Respond ONLY in valid JSON, in the same language as the shot description.

Format: {{
  "narrative_purpose": "why this shot exists in the story, 1 short sentence",
  "emotional_arc": "how the emotion evolves across this shot, 1 short sentence",
  "continuity_note": "what must visually carry over from/to neighboring shots, or empty string",
  "panel_count": {panel_count_hint},
  "layout": {layout_hint},
  "beats": ["Panel 1 - shot size/angle: action/expression/staging", ...]
}}
("beats" must contain exactly panel_count entries)
"""
        chars_note = f"Characters present in this shot: {', '.join(character_names)}." if character_names else ""
        continuity_note = ""
        if previous_shot or next_shot:
            continuity_note = "CONTINUITY CONTEXT:\n"
            if previous_shot:
                continuity_note += f"- Previous shot: {previous_shot.get('description') or ''}\n"
            if next_shot:
                continuity_note += f"- Next shot: {next_shot.get('description') or ''}\n"

        user_prompt = (
            f"Shot description: {shot.get('description') or ''}\n"
            f"Camera movement: {shot.get('camera_movement') or ''}\n"
            f"Mood: {shot.get('mood') or ''}\n"
            f"Duration: {shot.get('duration_seconds', 9)}s\n"
            f"Is cliffhanger: {shot.get('is_cliffhanger', False)}\n"
            f"Dialogue: {shot.get('dialogue') or 'None'}\n"
            f"Visual style: {style_label or 'Not specified'}\n"
            f"{chars_note}\n"
            f"{continuity_note}"
        )

        raw = self.router.generate_vision_multi(user_prompt, system_prompt, image_labels)
        if not raw:
            return {}
        try:
            data = json.loads(raw.replace("```json", "").replace("```", "").strip())
            if not data.get("beats"):
                return {}
            panel_count = forced_panel_count or data.get("panel_count") or len(data["beats"])
            data["beats"] = data["beats"][:panel_count]
            data["panel_count"] = panel_count
            data["layout"] = forced_layout or data.get("layout") or "3x3"
            return data
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Template texte seul (repli, ou si Prompt Director désactivé)
    # ------------------------------------------------------------------
    def _expand_shot_to_beats(self, shot: dict, num_beats: int = 9, character_names: list = None,
                               previous_shot: dict = None, next_shot: dict = None) -> dict:
        """Analyse le contexte narratif du plan (but narratif, arc émotionnel,
        continuité avec les plans voisins) ET le décompose en N panneaux — en
        UN SEUL appel, pour ne pas doubler le coût. Version texte seul, pas
        d'image (moins cher, plus rapide, mais pas ancré dans les références
        réelles) — utilisée quand le Prompt Director est désactivé, ou en
        repli si l'appel vision échoue. previous_shot/next_shot :
        {"description": ...} des plans adjacents, si disponibles.
        Retourne {"narrative_purpose", "emotional_arc", "continuity_note",
        "beats"} ou {} si échec."""
        chars_note = ""
        if character_names:
            chars_note = (
                f"Characters present in this shot: {', '.join(character_names)}. "
                f"If there is more than one character, ALTERNATE between them across panels "
                f"(shot / reverse-shot pattern) rather than always framing everyone together."
            )

        continuity_note = ""
        if previous_shot or next_shot:
            continuity_note = "CONTINUITY CONTEXT (use this to keep the story coherent across shots):\n"
            if previous_shot:
                continuity_note += f"- Previous shot: {previous_shot.get('description') or ''}\n"
            if next_shot:
                continuity_note += f"- Next shot: {next_shot.get('description') or ''}\n"
            continuity_note += (
                "If this shot shows a state change (e.g. a transformation, an injury, an "
                "object changing hands), make sure the FIRST panel reflects the state coming "
                "from the previous shot, not an unexplained new state."
            )

        system_prompt = f"""
You are a professional storyboard artist and cinematographer, fluent in film grammar:
shot sizes (wide shot, medium shot, close-up, extreme close-up), camera angles (low angle,
high angle, eye-level, dutch tilt, over-the-shoulder), and lighting (key/fill/rim light,
silhouette, practicals). You also think like a director about WHY a shot exists in the
story, not just what it looks like.

First, briefly analyze this shot's role in the story. Then break it down into exactly
{num_beats} sequential panels for a professional cinematic storyboard grid.

RULES:
1. Each panel MUST use a DIFFERENT shot size and/or camera angle than its neighbors — vary
   the coverage like a real storyboard (e.g. wide establishing, then medium, then close-up,
   then a reaction shot, then back to wide). Never repeat the same framing across all panels.
2. {chars_note}
3. Stay strictly faithful to the shot's description, camera movement, and mood provided — do
   not invent a different scene or new characters.
4. {continuity_note}
5. For each panel, briefly state the shot size/angle AND the action or expression happening
   (e.g. "Low angle medium shot: Kael raises his sword, eyes fierce").
6. Respond ONLY in valid JSON, in the same language as the description provided.

Format: {{
    "narrative_purpose": "why this shot exists in the story, in 1 short sentence",
    "emotional_arc": "how the emotion evolves across this shot, in 1 short sentence",
    "continuity_note": "what must visually carry over from/to neighboring shots, or empty string if not applicable",
    "beats": ["panel 1: shot size/angle + action/expression", ...]
}}
(exactly {num_beats} entries in "beats")
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
            if not beats:
                return {}
            data["beats"] = beats[:num_beats]
            return data
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Construction du prompt image final
    # ------------------------------------------------------------------
    def _build_prompt(self, shot: dict, style_label: str, mode: str = "one_frame", analysis: dict = None,
                       grounded_appearance: str = "") -> str:
        identity_lock = (
            "CHARACTER IDENTITY LOCK: same characters and same environment as the reference "
            "images provided — do not alter their face, outfit, proportions, or defining "
            "features. This lock applies ONLY to the specific named characters shown in the "
            "reference images. If the scene mentions any OTHER person not among the reference "
            "images (e.g. a background character, a stranger, an unnamed passerby), invent them "
            "as a completely distinct, independent individual — never reuse the reference "
            "character's face, body, or likeness for them, even if no visual reference exists "
            "for that other person."
        )
        if grounded_appearance:
            identity_lock += f" What the reference image actually shows: {grounded_appearance}"
        parts = [identity_lock]
        if analysis and analysis.get("narrative_purpose"):
            parts.append(f"NARRATIVE PURPOSE: {analysis['narrative_purpose']}")
        parts.append(f"SCENE: {shot.get('description') or ''}")
        if shot.get("mood"):
            parts.append(f"MOOD: {shot['mood']}")
        if analysis and analysis.get("emotional_arc"):
            parts.append(f"EMOTIONAL ARC: {analysis['emotional_arc']}")
        if analysis and analysis.get("continuity_note"):
            parts.append(f"CONTINUITY: {analysis['continuity_note']}")

        beats = analysis.get("beats") if analysis else None
        if mode != "one_frame" and beats:
            layout = analysis.get("layout", "3x3")
            panel_count = analysis.get("panel_count", len(beats))
            beats_str = "; ".join(f"Panel {i + 1} — {b}" for i, b in enumerate(beats))
            parts.append(f"BEATS: {beats_str}")
            parts.append(
                f"COMPOSITION: arrange as a clean {layout} grid of {panel_count} sequential panels, "
                "each with a DISTINCT shot size and/or camera angle (mix wide/medium/close-up and "
                "eye-level/low/high angle across panels) — a professional storyboard grid with "
                "real cinematic variety, not repeated identical framing."
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

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------
    def generate_storyboard_frame(self, shot: dict, reference_image_paths: list, visual_styles: list,
                                   model: str = None, batch_number: int = 1, mode: str = "one_frame",
                                   character_names: list = None, previous_shot: dict = None,
                                   next_shot: dict = None, structured_characters: list = None,
                                   structured_location: dict = None, use_prompt_director: bool = True) -> dict:
        """mode : 'one_frame' (une image), '2x2' (4 panneaux), '3x3' (9
        panneaux), ou 'auto' (le Prompt Director choisit 4/6/9 lui-même).
        reference_image_paths : liste PLATE (closeup+fullbody+décor), utilisée
        pour l'appel de génération d'image lui-même — toujours nécessaire.
        structured_characters/structured_location : mêmes références mais
        organisées par personnage/décor, nécessaires UNIQUEMENT pour le
        Prompt Director (mode != one_frame + use_prompt_director=True) — si
        absentes, repli automatique sur le template texte.
        use_prompt_director : True (défaut) pour l'analyse vision multi-images
        ; False pour l'ancien template texte seul (plus rapide, moins cher,
        mais pas ancré dans les références réelles).
        Retourne {url, prompt_used, model_used, duration_sec, error}."""
        model = model if model in AVAILABLE_STORYBOARD_MODELS else DEFAULT_STORYBOARD_MODEL
        style_label = " + ".join(visual_styles) if visual_styles else ""

        analysis = None
        grounded_appearance = ""

        if mode == "one_frame":
            # Ancrage léger existant, inchangé : 1 image, 1 appel.
            if reference_image_paths:
                grounded_appearance = self._ground_character_appearance(reference_image_paths[0])
        else:
            forced = PANEL_MODE_CONFIG.get(mode)  # None si mode == "auto"

            if use_prompt_director and structured_characters is not None:
                analysis = self._analyze_shot_with_vision(
                    shot, structured_characters, structured_location, character_names,
                    previous_shot, next_shot, style_label,
                    forced_panel_count=forced["panel_count"] if forced else None,
                    forced_layout=forced["layout"] if forced else None,
                )

            if not analysis:
                # Repli : ancien template texte. "auto" sans Prompt Director
                # retombe sur 3x3/9 par défaut (le texte seul ne juge pas la
                # densité d'action aussi finement que la vision).
                num_beats = forced["panel_count"] if forced else 9
                layout = forced["layout"] if forced else "3x3"
                analysis = self._expand_shot_to_beats(
                    shot, num_beats=num_beats, character_names=character_names,
                    previous_shot=previous_shot, next_shot=next_shot
                )
                if analysis:
                    analysis["panel_count"] = num_beats
                    analysis["layout"] = layout
                else:
                    mode = "one_frame"  # double échec -> repli complet vers une image simple

        prompt = self._build_prompt(shot, style_label, mode=mode, analysis=analysis, grounded_appearance=grounded_appearance)

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
