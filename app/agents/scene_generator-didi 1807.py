import os
import time
import json
from dashscope import VideoSynthesis
from app.agents.tool_router import tool_router, VIDEO_API_KEY

STORAGE_DIR = os.path.join("app", "static", "assets", "videos")
os.makedirs(STORAGE_DIR, exist_ok=True)

# Wan par défaut : moins cher (~1.50$ la vidéo de 10s en 1080p contre ~2.50-2.80$
# pour HappyHorse), donc plus d'essais possibles pour le même budget. HappyHorse
# reste disponible pour les plans où un mouvement unique très complexe
# (rotation, action fluide) justifie son coût plus élevé.
AVAILABLE_VIDEO_MODELS = [
    "wan2.7-r2v-2026-06-12",
    "happyhorse-1.1-r2v",
]
DEFAULT_VIDEO_MODEL = "wan2.7-r2v-2026-06-12"
DEFAULT_RESOLUTION = "720P"
AVAILABLE_RESOLUTIONS = ["720P", "1080P"]


class SceneGeneratorAgent:
    """Agent "Shot Director" : analyse chaque plan (personnages, décor,
    action, émotion, cadrage, lumière, continuité) et construit un prompt
    vidéo optimisé pour le modèle choisi, en préservant la cohérence visuelle.

    Structure de prompt (FORMAT/REFERENCES/RENDER DISCIPLINE/SCENE/STYLE/
    STATIC LOCKS/DYNAMIC MOTION/AUDIO-VOICE/TIMELINE/RULES/NEGATIVE) reprise
    directement d'exemples de production réels (PixVerse/Seedance) partagés
    par l'utilisateur — un format éprouvé, pas une improvisation.

    Le vocabulaire de DYNAMIC MOTION s'adapte au GENRE de l'action (combat =
    intensité/rapidité/frappes, romance = tendresse/lenteur, comédie =
    exagération...) via un appel texte léger avant l'appel vidéo — voir
    _generate_action_beats.

    ✅ Utilise la vraie classe `dashscope.VideoSynthesis` (confirmée en lisant
    le code source du SDK installé). Chemins de fichiers locaux acceptés
    directement dans `media` (préfixe "file://") — le SDK les upload
    automatiquement vers le stockage Alibaba (OSS), pas besoin d'hébergement
    public pour tester.

    Les DEUX modèles supportés ont des conventions de prompt différentes,
    confirmées par la documentation/exemples officiels :
    - Wan 2.7 R2V : balises @image1/@image2/... associant explicitement
      chaque référence à un sujet précis.
    - HappyHorse R2V : découpage temporel natif ("[0-Xs] Shot N - Type: ...").
    """

    def __init__(self):
        self.router = tool_router

    def _to_file_reference(self, local_path: str) -> str:
        """Convertit un chemin disque local en référence "file://" que le
        SDK dashscope sait uploader automatiquement vers OSS."""
        if not local_path:
            return None
        if local_path.startswith("http") or local_path.startswith("oss://"):
            return local_path  # déjà une vraie URL, rien à faire
        abs_path = os.path.abspath(local_path)
        return f"file://{abs_path}"

    def _build_reference_list(self, storyboard_path: str, character_refs: list, location_ref: dict):
        """Construit la liste ordonnée des références + leur label associé
        (utilisé pour les balises @imageN de Wan). Retourne (paths, labels)."""
        paths, labels = [], []
        if storyboard_path:
            paths.append(storyboard_path)
            labels.append("the target shot composition, story continuity, and framing")
        for c in (character_refs or []):
            paths.append(c["path"])
            labels.append(c["name"])
        if location_ref:
            paths.append(location_ref["path"])
            labels.append(f"the {location_ref['name']} location")
        return paths, labels

    def _generate_action_beats(self, shot: dict, character_names: list, has_dialogue: bool) -> dict:
        """Appel texte (peu coûteux, PAS l'appel vidéo) qui : 1) adapte le
        vocabulaire d'action au GENRE réel de la scène (combat = intensité/
        rapidité/frappes ; romance = tendresse/lenteur ; comédie =
        exagération ; tension/horreur = brusquerie) et 2) construit un
        minutage TIMELINE explicite. Ne bloque jamais : None si échec, auquel
        cas on retombe sur une version plus simple, générique."""
        duration = min(shot.get("duration_seconds", 10) or 10, 10)
        chars_note = f"Characters in this shot: {', '.join(character_names)}." if character_names else ""

        system_prompt = f"""
You are a professional action director and cinematographer writing a video generation prompt.

Given a single shot's description, camera movement, mood, and duration, produce:
1. A vivid DYNAMIC MOTION description, using vocabulary that matches the GENRE and INTENSITY
   of what is ACTUALLY happening in the shot — for example: a combat shot needs fast, intense,
   forceful verbs (strikes, parries, lunges, impacts, recoils); a tender or romantic shot needs
   slow, gentle, lingering verbs (reaches, brushes, lingers, exhales); a comedic shot needs
   exaggerated, snappy verbs (recoils, gawks, double-takes, deflates); a tense or fearful shot
   needs sharp, unsettling verbs (flinches, freezes, recoils, creeps). Do not use a neutral,
   generic tone if the scene calls for something more specific.
2. A TIMELINE breaking the {duration:.0f}-second shot into 3-4 timestamped beats (e.g.
   "0:00-0:03 ...", "0:03-0:06 ...") describing the concrete progression of action, camera, and
   expression moment by moment — like a real shot list, not a vague summary.

{chars_note}

RULES:
- Stay strictly faithful to the shot's own description — do not invent new events or characters.
- This is live-action video: describe REAL, CONTINUOUS physical motion, never a static pose or fade.
- Respond ONLY in valid JSON, in the same language as the description provided.

Format: {{"dynamic_motion": "...", "timeline": "0:00-0:0Xs ...; 0:0X-0:0Ys ..."}}
"""
        user_prompt = (
            f"Shot description: {shot.get('description') or ''}\n"
            f"Camera movement: {shot.get('camera_movement') or ''}\n"
            f"Mood: {shot.get('mood') or ''}\n"
            f"Duration: {duration:.0f}s\n"
            + (f"Dialogue: {shot.get('dialogue')}" if has_dialogue and shot.get("dialogue") else "No dialogue in this shot.")
        )
        raw = self.router.generate(user_prompt, system_prompt)
        try:
            data = json.loads(raw.replace("```json", "").replace("```", "").strip())
            if data.get("dynamic_motion") and data.get("timeline"):
                return data
            return None
        except Exception:
            return None

    def _build_wan_prompt(self, shot: dict, labels: list, style_label: str, has_dialogue: bool,
                           action_beats: dict = None) -> str:
        tags = ", ".join(f"@image{i + 1} ({label})" for i, label in enumerate(labels))
        duration = min(shot.get("duration_seconds", 10) or 10, 10)

        parts = [
            f"FORMAT: {duration:.0f}s / cinematic live-action.",
            f"REFERENCES: {tags}. Do not mix or alter identities between references.",
            "RENDER DISCIPLINE: Use the referenced storyboard for composition, identity, and "
            "story continuity only — if it shows multiple panels or a grid, treat them as "
            "sequential story beats to fold into ONE continuous shot, not a layout to "
            "reproduce. No panel borders, no grid lines, no storyboard furniture, no text, "
            "in the final output.",
            f"SCENE: {shot.get('description') or ''}",
        ]
        if style_label:
            parts.append(f"STYLE: {style_label}, cinematic painterly composition, premium quality.")
        parts.append(
            "STATIC LOCKS: character identities, outfits, and the environment must remain "
            "perfectly consistent with the reference images throughout — no drift, no face morphing."
        )

        if action_beats:
            parts.append(f"DYNAMIC MOTION: {action_beats['dynamic_motion']}")
        else:
            motion = shot.get("camera_movement") or "steady cinematic camera"
            parts.append(
                f"DYNAMIC MOTION: {motion}. Over the course of the shot: {shot.get('description') or ''} "
                f"This is live action footage with continuous physical motion throughout — not a "
                f"static image or a slow fade."
            )
        if shot.get("mood"):
            parts.append(f"MOOD: {shot['mood']}")

        if has_dialogue and shot.get("dialogue"):
            parts.append(f'AUDIO/VOICE: the character speaks: "{shot["dialogue"]}", synchronized natural lip-sync.')
        else:
            parts.append("AUDIO/VOICE: no dialogue — automatically generated ambient sound and "
                          "orchestral score matching the mood.")

        if action_beats:
            parts.append(f"TIMELINE: {action_beats['timeline']}")

        parts.append(
            "RULES: sequential real-time motion, premium cinematic quality, no panel borders, "
            "no split screen, no text overlays, no captions, no watermark."
        )
        parts.append(
            "NEGATIVE: no face morphing, no identity drift, no freeze-frame, no static shot, "
            "no extra characters not in the references, no panel grid reproduced in the output."
        )
        return " ".join(parts)

    def _build_happyhorse_prompt(self, shot: dict, labels: list, style_label: str, has_dialogue: bool,
                                  action_beats: dict = None) -> str:
        duration = min(shot.get("duration_seconds", 10) or 10, 10)
        ref_note = ", ".join(labels) if labels else "the reference images"

        parts = [
            f"FORMAT: {duration:.0f}s / 720P / cinematic live-action.",
            f"REFERENCES: {ref_note}.",
            "RENDER DISCIPLINE: use the referenced storyboard for identity and story continuity "
            "only — render ONE continuous live-action clip, not a reproduction of any panel "
            "grid. No panel borders, no storyboard furniture, no text, in the final output.",
        ]

        if action_beats:
            parts.append(action_beats["timeline"])
            parts.append(f"DYNAMIC MOTION: {action_beats['dynamic_motion']}")
        else:
            shot_type = shot.get("camera_movement") or "Medium Shot"
            parts.append(
                f"[0-{duration:.0f}s] Shot 1 - {shot_type}: {shot.get('description') or ''} This is "
                f"live action footage with continuous physical motion throughout the full duration."
            )

        parts.append(f"Character(s) and setting match {ref_note} exactly, consistent identity and outfit throughout.")
        if style_label:
            parts.append(f"Style: {style_label}, cinematic painterly composition, premium quality.")
        if shot.get("mood"):
            parts.append(f"Mood: {shot['mood']}.")

        if has_dialogue and shot.get("dialogue"):
            parts.append(f'Dialogue: "{shot["dialogue"]}", natural multilingual lip-sync.')
        else:
            parts.append("No dialogue — automatically generated ambient sound and background "
                          "music matching the mood.")

        parts.append(
            "No panel borders, no split screen, no text overlays, no captions, no watermark, "
            "no face morphing, no freeze-frame, no static shot."
        )
        return " ".join(parts)

    def _build_prompt(self, shot: dict, labels: list, style_label: str, has_dialogue: bool, model: str,
                       action_beats: dict = None) -> str:
        if model.startswith("happyhorse"):
            return self._build_happyhorse_prompt(shot, labels, style_label, has_dialogue, action_beats)
        return self._build_wan_prompt(shot, labels, style_label, has_dialogue, action_beats)

    def _download_and_store(self, remote_url: str, scene_id: int, label: str) -> str:
        import requests
        filename = f"scene{scene_id}_{label}.mp4"
        local_path = os.path.join(STORAGE_DIR, filename)

        response = requests.get(remote_url, timeout=180, stream=True)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return f"/static/assets/videos/{filename}"

    def generate_scene_video(self, shot: dict, storyboard_path: str, character_refs: list, location_ref: dict,
                              style_label: str, aspect_ratio: str = "16:9", model: str = None,
                              resolution: str = None, batch_number: int = 1, has_dialogue: bool = True,
                              custom_prompt: str = None) -> dict:
        """storyboard_path : chemin disque local (/app/static/...) du
        storyboard sélectionné. character_refs : liste de {"name": str,
        "path": str} (chemins locaux des portraits sélectionnés).
        location_ref : {"name": str, "path": str} ou None.
        custom_prompt : si fourni, remplace entièrement le prompt
        auto-construit (et saute l'enrichissement action/timeline) — permet
        à l'utilisateur de retoucher le prompt à la main avant de régénérer.
        Retourne {url, prompt_used, model_used, duration_sec, error}."""
        model = model if model in AVAILABLE_VIDEO_MODELS else DEFAULT_VIDEO_MODEL
        resolution = resolution if resolution in AVAILABLE_RESOLUTIONS else DEFAULT_RESOLUTION

        local_paths, labels = self._build_reference_list(storyboard_path, character_refs, location_ref)
        if not local_paths:
            return {"url": None, "prompt_used": None, "model_used": model, "duration_sec": None,
                    "error": True, "error_message": "No reference images available for this shot."}

        # Chemins locaux -> références "file://" (upload automatique par le SDK vers OSS)
        file_refs = [self._to_file_reference(p) for p in local_paths]
        for p in local_paths:
            if not os.path.isfile(p):
                return {"url": None, "prompt_used": None, "model_used": model, "duration_sec": None,
                        "error": True, "error_message": f"Reference file not found on disk: {p}"}

        if custom_prompt:
            prompt = custom_prompt
        else:
            character_names = [c["name"] for c in (character_refs or [])]
            action_beats = self._generate_action_beats(shot, character_names, has_dialogue)
            prompt = self._build_prompt(shot, labels, style_label, has_dialogue, model, action_beats)

        duration = int(min(shot.get("duration_seconds", 10) or 10, 10))
        media = [{"type": "reference_image", "url": u} for u in file_refs]

        start = time.time()
        try:
            # request_timeout : paramètre confirmé dans le code source du SDK
            # dashscope (common/constants.py: REQUEST_TIMEOUT_KEYWORD =
            # "request_timeout"), qui remplace le défaut de 300s — insuffisant
            # pour HappyHorse (génération audio+vidéo synchronisée, plus
            # lourde qu'un simple rendu vidéo).
            task = VideoSynthesis.async_call(
                model=model,
                api_key=VIDEO_API_KEY,
                prompt=prompt,
                media=media,
                resolution=resolution,
                ratio=aspect_ratio,
                duration=duration,
                request_timeout=600,
            )
            result = VideoSynthesis.wait(task, api_key=VIDEO_API_KEY, request_timeout=600)

            if result.status_code != 200 or not result.output or result.output.task_status != "SUCCEEDED":
                error_msg = getattr(result, "message", None) or f"Task status: {getattr(result.output, 'task_status', 'unknown')}"
                raise RuntimeError(error_msg)

            remote_video_url = result.output.video_url
            local_url = self._download_and_store(remote_video_url, shot.get("id"), f"b{batch_number}")
            return {
                "url": local_url, "prompt_used": prompt, "model_used": model,
                "duration_sec": round(time.time() - start, 2), "error": False,
            }
        except Exception as e:
            print(f"❌ [SceneGenerator] Échec génération vidéo : {e}")
            return {
                "url": None, "prompt_used": prompt, "model_used": model,
                "duration_sec": round(time.time() - start, 2), "error": True, "error_message": str(e),
            }
