import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

VIDEOS_DIR = os.path.join("app", "static", "assets", "videos")
COVERS_DIR = os.path.join("app", "static", "assets", "covers")
ASSEMBLED_DIR = os.path.join("app", "static", "assets", "assembled")
os.makedirs(COVERS_DIR, exist_ok=True)
os.makedirs(ASSEMBLED_DIR, exist_ok=True)

# Police système utilisée pour le texte du cover — Pillow est TOUJOURS plus
# fiable qu'un modèle d'image pour du texte lisible (les modèles d'image
# produisent régulièrement du texte déformé ou illisible). Chemin confirmé
# présent sur Ubuntu 22.04/24.04 (image de base recommandée pour l'ECS) —
# si absent au déploiement, repli automatique sur la police par défaut de
# Pillow (moins jolie mais jamais bloquant).
FONT_PATH_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def build_assembly_report(episode, scenes: list) -> dict:
    """Construit le rapport avant assemblage : combien de plans, durée totale
    des plans DISPONIBLES (vidéo sélectionnée et terminée), et la liste des
    plans manquants — pour que l'utilisateur décide en connaissance de cause,
    jamais de blocage strict."""
    ordered = sorted(scenes, key=lambda s: s.number)
    available, missing = [], []
    total_duration = 0.0

    for scene in ordered:
        video_asset = next(
            (a for a in (scene.assets or []) if a.asset_type == "video" and a.is_selected and a.status == "completed"),
            None
        )
        if video_asset:
            available.append({"scene_id": scene.id, "number": scene.number, "duration_seconds": scene.duration_seconds})
            total_duration += scene.duration_seconds or 0
        else:
            missing.append({"scene_id": scene.id, "number": scene.number, "description": scene.description})

    return {
        "total_shots": len(ordered),
        "available_count": len(available),
        "available_shots": available,
        "missing_shots": missing,
        "total_duration_seconds": round(total_duration, 1),
        "can_assemble": len(available) > 0,
    }


def assemble_episode_video(scenes: list, episode_id: int, cover_path: str = None) -> str:
    """Concatène les clips vidéo SÉLECTIONNÉS des plans disponibles, dans
    l'ordre des numéros de plan (ordre Shot Breakdown = ordre narratif) —
    opération purement mécanique via ffmpeg, aucun appel IA. Les résolutions
    différentes entre plans (720P/1080P) sont uniformisées automatiquement
    pendant la concaténation pour éviter tout échec. cover_path : si fourni
    (et le fichier existe), ajoute une intro de 2s avec l'image du cover
    (silencieuse — un vrai son d'intro généré par IA demanderait un tout
    nouveau pipeline audio, hors scope pour l'instant). Lève une exception
    explicite si ffmpeg échoue — jamais d'échec silencieux."""
    ordered = sorted(scenes, key=lambda s: s.number)
    clip_paths = []
    for scene in ordered:
        video_asset = next(
            (a for a in (scene.assets or []) if a.asset_type == "video" and a.is_selected and a.status == "completed"),
            None
        )
        if video_asset and video_asset.file_url:
            local_path = os.path.join("app", video_asset.file_url.lstrip("/"))
            if os.path.isfile(local_path):
                clip_paths.append(local_path)

    if not clip_paths:
        raise ValueError("No available video clips to assemble for this episode.")

    output_filename = f"episode{episode_id}_assembled.mp4"
    output_path = os.path.join(ASSEMBLED_DIR, output_filename)

    has_intro = bool(cover_path and os.path.isfile(cover_path))

    # Filtre ffmpeg avec normalisation (résolution/fps/format audio communs)
    # plutôt qu'une simple concaténation de fichiers — plus robuste face à
    # des clips générés avec des réglages différents (720P vs 1080P, avec ou
    # sans audio).
    inputs = []
    filter_parts = []
    concat_inputs = ""
    idx = 0

    if has_intro:
        # Image en boucle 2s (vidéo) + piste audio silencieuse de 2s associée
        # (obligatoire : le filtre concat exige une paire [vidéo][audio] par
        # segment, même quand ce segment n'a naturellement pas de son).
        inputs += ["-loop", "1", "-t", "2", "-i", cover_path]
        inputs += ["-f", "lavfi", "-t", "2", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        filter_parts.append(
            f"[{idx}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{idx}];"
        )
        concat_inputs += f"[v{idx}][{idx + 1}:a]"
        idx += 2

    for path in clip_paths:
        inputs += ["-i", path]
        filter_parts.append(
            f"[{idx}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{idx}];"
        )
        concat_inputs += f"[v{idx}][{idx}:a]"
        idx += 1

    n_segments = (1 if has_intro else 0) + len(clip_paths)
    filter_complex = "".join(filter_parts) + f"{concat_inputs}concat=n={n_segments}:v=1:a=1[outv][outa]"

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-c:a", "aac", "-preset", "fast",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-2000:]}")

    return f"/static/assets/assembled/{output_filename}"


def build_key_art_prompt(tool_router, title: str, episode_label: str, character_refs: list,
                          location_ref: dict, style_label: str) -> str:
    """Prompt Director (Qwen-VL) agissant comme un directeur artistique
    d'affiche (key art) — voit RÉELLEMENT les personnages et le décor de
    l'épisode, et rédige un prompt de cover vendeur, pas un simple fond
    illustré. Contrairement au storyboard, ici l'IA rend elle-même le
    titre/numéro d'épisode comme un vrai lettrage d'affiche, intégré à la
    composition. Retourne le prompt final (texte brut, pas de JSON) — ou une
    version de repli générique si l'appel échoue (jamais bloquant)."""
    image_labels = []
    for char in (character_refs or []):
        name = char.get("name", "Character")
        if char.get("closeup_path"):
            image_labels.append((f"CHARACTER — {name} (closeup):", char["closeup_path"]))
        if char.get("fullbody_path"):
            image_labels.append((f"CHARACTER — {name} (fullbody):", char["fullbody_path"]))
    if location_ref and location_ref.get("path"):
        image_labels.append((f"LOCATION — {location_ref.get('name', 'Location')}:", location_ref["path"]))

    fallback_prompt = (
        f"{style_label} cinematic key art poster" if style_label else "cinematic key art poster"
    ) + f", bold poster typography reading \"{title}\" and \"{episode_label}\" integrated into the composition, dramatic lighting, high quality, detailed"

    if not image_labels:
        return fallback_prompt

    system_prompt = f"""
You are a professional key art designer (movie/show poster artist) creating a
promotional cover image for a short drama episode.

You can SEE the actual character references (closeup and fullbody) and the location
reference for this story. These images define what EXISTS — use them as the visual
foundation for the poster. Do not alter faces, proportions or defining features.

Your job: write a SINGLE, rich image-generation prompt for a compelling, sellable
poster-style key art. Unlike a plain illustrated background, it must:
- Feature the character(s) prominently, in a dynamic, iconic pose that captures the
  story's tone and genre at a glance.
- Use the location as an atmospheric backdrop that supports the mood, not the main subject.
- Render the title "{title}" and the label "{episode_label}" as bold, legible poster
  typography, designed into the composition like a real movie poster (not a generic
  caption slapped on top) — matching the mood and style of the artwork.
- Establish dramatic lighting, color grading and composition that would make someone
  want to click and watch.

Respond with ONLY the final image-generation prompt text — no JSON, no preamble, no
explanation, no quotation marks around it.
"""
    user_prompt = f"Title: {title}\nEpisode label: {episode_label}\nStyle: {style_label or 'Not specified'}"

    raw = tool_router.generate_vision_multi(user_prompt, system_prompt, image_labels)
    return raw.strip() if raw else fallback_prompt


def apply_logo(image_path: str, logo_path: str, episode_id) -> str:
    """Colle le logo du studio par-dessus l'image générée par l'IA. Reste en
    Pillow (pas confié à l'IA) : un logo de marque doit être reproduit au
    pixel près, ce qu'un modèle d'image ne garantit jamais — contrairement au
    titre/texte, désormais rendu directement par l'IA dans l'artwork."""
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    if logo_path and os.path.isfile(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo_w = int(w * 0.15)
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h))
        margin = int(w * 0.03)
        img.paste(logo, (margin, margin), logo)

    filename = f"episode{episode_id}_cover.png"
    output_path = os.path.join(COVERS_DIR, filename)
    img.convert("RGB").save(output_path)
    return f"/static/assets/covers/{filename}"


def aspect_ratio_to_size(aspect_ratio: str) -> str:
    """Convertit le ratio du projet (format 'largeur:hauteur') en résolution
    concrète pour l'appel de génération d'image — le cover doit respecter le
    même ratio que le reste du projet (vertical pour un Short Drama, large
    pour un Short Movie)."""
    mapping = {
        "16:9": "1664*936",
        "9:16": "936*1664",
        "1:1": "1024*1024",
    }
    return mapping.get(aspect_ratio, "936*1664")  # défaut : vertical (format le plus courant pour un cover)