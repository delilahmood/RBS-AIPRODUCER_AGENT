from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os
import re
import shutil
import requests

from app.database import get_db
from app.models.episode import Episode
from app.models.episode_asset import EpisodeAsset
from app.models.scene import Scene
from app.models.project import Project
from app.models.character import Character
from app.models.character_asset import CharacterAsset
from app.models.location import Location
from app.models.location_assets import LocationAsset
from app.agents.tool_router import tool_router
from app.services.episode_assembly import build_assembly_report, assemble_episode_video, build_key_art_prompt, apply_logo

router = APIRouter(prefix="/api/episodes", tags=["episodes"])

STORAGE_DIR = os.path.join("app", "static", "assets", "covers")
os.makedirs(STORAGE_DIR, exist_ok=True)
LOGO_PATH = os.path.join("app", "static", "assets", "rbs_logo-transparent.png")

# Modèles image acceptant des références (contrairement à Wan T2I, qui génère
# à partir de texte seul et ne peut PAS intégrer les personnages) — retiré de
# la liste, nécessaire pour que les personnages apparaissent vraiment sur l'affiche.
COVER_MODELS = ["qwen-image-2.0-pro", "qwen-image-edit-plus", "qwen-image-edit-max", "qwen-image-2.0"]
DEFAULT_COVER_MODEL = "qwen-image-2.0-pro"

# Modèles à plafond confirmé (3 références max) — même contrainte que pour le
# Storyboard Art, voir storyboard_art.py pour le message d'erreur d'origine.
MODELS_WITH_3_IMAGE_CAP = {"qwen-image-2.0-pro", "qwen-image-2.0"}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "cover").strip().lower()).strip("-")
    return slug or "cover"


def _size_for_ratio(aspect_ratio: str) -> str:
    """Convertit le ratio du projet (Settings) en dimensions DashScope."""
    if aspect_ratio == "9:16":
        return "936*1664"
    if aspect_ratio == "16:9":
        return "1664*936"
    return "1024*1024"


@router.get("/{episode_id}/assembly-report")
async def get_assembly_report(episode_id: int, db: Session = Depends(get_db)):
    """Rapport avant assemblage : nombre de plans, durée, plans manquants —
    jamais de blocage strict, l'utilisateur décide en connaissance de cause."""
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    scenes = db.query(Scene).filter(Scene.episode_id == episode_id).all()
    report = build_assembly_report(episode, scenes)
    return report


class GenerateCoverRequest(BaseModel):
    model: Optional[str] = None


@router.post("/{episode_id}/generate-cover")
async def generate_episode_cover(episode_id: int, request: GenerateCoverRequest, db: Session = Depends(get_db)):
    """Génère une NOUVELLE proposition de cover (nouveau lot, l'historique
    précédent reste disponible). Un Prompt Director (Qwen-VL) voit RÉELLEMENT
    les personnages et le décor en référence, et rédige lui-même un prompt de
    key art vendeur — pas un simple gabarit texte fixe. Le titre/sous-titre
    sont rendus par l'IA directement dans la composition ; le logo, lui, est
    collé après coup via Pillow (précision de marque garantie, contrairement
    à un rendu IA)."""
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = db.query(Project).filter(Project.id == episode.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    model = request.model if request.model in COVER_MODELS else DEFAULT_COVER_MODEL
    size = _size_for_ratio(project.aspect_ratio)

    # Références personnages : 1 image par personnage (fullbody de préférence,
    # porte visage + tenue), plafonné pour les modèles à limite confirmée.
    characters = db.query(Character).filter(Character.project_id == project.id).all()
    character_refs = []
    ref_paths = []
    for char in characters:
        portrait = db.query(CharacterAsset).filter(
            CharacterAsset.character_id == char.id, CharacterAsset.asset_type == "portrait",
            CharacterAsset.is_selected == True
        ).first()
        fullbody = db.query(CharacterAsset).filter(
            CharacterAsset.character_id == char.id, CharacterAsset.asset_type == "reference_sheet",
            CharacterAsset.is_selected == True
        ).first()
        chosen = fullbody or portrait
        if chosen and chosen.file_url:
            path = os.path.join("app", chosen.file_url.lstrip("/"))
            if os.path.isfile(path):
                ref_paths.append(path)
                character_refs.append({"name": char.name, "fullbody_path": path if fullbody else None,
                                        "closeup_path": path if not fullbody else None})

    # Décor : le premier lieu utilisé par les plans de cet épisode — sert
    # d'arrière-plan atmosphérique, jamais le sujet principal de l'affiche.
    location_ref = None
    first_scene_with_location = db.query(Scene).filter(
        Scene.episode_id == episode_id, Scene.location_id.isnot(None)
    ).first()
    if first_scene_with_location:
        location_obj = db.query(Location).filter(Location.id == first_scene_with_location.location_id).first()
        loc_asset = db.query(LocationAsset).filter(
            LocationAsset.location_id == first_scene_with_location.location_id,
            LocationAsset.asset_type == "reference", LocationAsset.is_selected == True
        ).first()
        if loc_asset and loc_asset.file_url:
            path = os.path.join("app", loc_asset.file_url.lstrip("/"))
            if os.path.isfile(path):
                location_ref = {"name": location_obj.name if location_obj else "Location", "path": path}
                ref_paths.append(path)

    if model in MODELS_WITH_3_IMAGE_CAP and len(ref_paths) > 3:
        ref_paths = ref_paths[:3]

    style_label = " + ".join(project.visual_styles or []) if project.visual_styles else ""
    episode_label = f"Episode {episode.episode_number or episode.number}"

    # Prompt Director : Qwen-VL voit réellement les références et rédige le
    # prompt final — pas un gabarit Python statique.
    prompt = build_key_art_prompt(tool_router, project.title, episode_label, character_refs, location_ref, style_label)

    if ref_paths:
        result = tool_router.generate_image_edit(prompt, ref_paths, model=model, size=size)
    else:
        result = tool_router.generate_image(prompt, size=size)

    if not result:
        raise HTTPException(status_code=502, detail="Cover generation failed.")

    last_batch = db.query(EpisodeAsset).filter(
        EpisodeAsset.episode_id == episode_id, EpisodeAsset.asset_type == "cover"
    ).order_by(EpisodeAsset.generation_batch.desc()).first()
    next_batch = (last_batch.generation_batch + 1) if last_batch else 1

    slug = _slugify(project.title)
    tmp_filename = f"{episode_id}_{slug}_b{next_batch}_raw.png"
    tmp_path = os.path.join(STORAGE_DIR, tmp_filename)
    try:
        resp = requests.get(result["url"], timeout=60)
        resp.raise_for_status()
        with open(tmp_path, "wb") as f:
            f.write(resp.content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download generated cover: {e}")

    # Logo collé après coup (précision de marque garantie, pas confiée à l'IA)
    logo_path = LOGO_PATH if os.path.isfile(LOGO_PATH) else None
    final_url = apply_logo(tmp_path, logo_path, f"{episode_id}_b{next_batch}")
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    asset = EpisodeAsset(
        episode_id=episode_id, asset_type="cover", file_url=final_url,
        prompt_used=prompt, model_used=result.get("model", model), version=1,
        generation_batch=next_batch, is_selected=True, status="completed",
    )
    db.query(EpisodeAsset).filter(
        EpisodeAsset.episode_id == episode_id, EpisodeAsset.asset_type == "cover"
    ).update({"is_selected": False})
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {"asset_id": asset.id, "cover_url": asset.file_url, "prompt_used": prompt, "batch": next_batch}


class SelectCoverRequest(BaseModel):
    asset_id: int


@router.post("/{episode_id}/select-cover")
async def select_episode_cover(episode_id: int, request: SelectCoverRequest, db: Session = Depends(get_db)):
    """Choisit une proposition de cover parmi l'historique. Ne supprime rien."""
    asset = db.query(EpisodeAsset).filter(
        EpisodeAsset.id == request.asset_id, EpisodeAsset.episode_id == episode_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Cover not found")
    if asset.status != "completed":
        raise HTTPException(status_code=400, detail="Cannot select a failed cover")

    db.query(EpisodeAsset).filter(
        EpisodeAsset.episode_id == episode_id, EpisodeAsset.asset_type == "cover"
    ).update({"is_selected": False})
    asset.is_selected = True
    db.commit()

    return {"message": "Cover selected", "asset_id": asset.id}


@router.post("/{episode_id}/upload-cover")
async def upload_episode_cover(episode_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Ajoute un cover retouché/dessiné par l'utilisateur comme proposition
    supplémentaire — sélectionnable comme les autres, jamais écrasé."""
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File type not allowed")

    last_batch = db.query(EpisodeAsset).filter(
        EpisodeAsset.episode_id == episode_id, EpisodeAsset.asset_type == "cover"
    ).order_by(EpisodeAsset.generation_batch.desc()).first()
    next_batch = (last_batch.generation_batch + 1) if last_batch else 1

    filename = f"{episode_id}_upload_b{next_batch}{file_ext}"
    local_path = os.path.join(STORAGE_DIR, filename)
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db.query(EpisodeAsset).filter(
        EpisodeAsset.episode_id == episode_id, EpisodeAsset.asset_type == "cover"
    ).update({"is_selected": False})
    asset = EpisodeAsset(
        episode_id=episode_id, asset_type="cover", file_url=f"/static/assets/covers/{filename}",
        prompt_used=None, model_used="user_upload", version=1, generation_batch=next_batch,
        is_selected=True, status="completed",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {"message": "Cover uploaded", "asset": {"id": asset.id, "url": asset.file_url}}


@router.delete("/{episode_id}/covers/{asset_id}")
async def delete_episode_cover(episode_id: int, asset_id: int, db: Session = Depends(get_db)):
    """Supprime définitivement une proposition de cover (fichier + ligne)."""
    asset = db.query(EpisodeAsset).filter(
        EpisodeAsset.id == asset_id, EpisodeAsset.episode_id == episode_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Cover not found")

    if asset.file_url:
        local_path = os.path.join("app", asset.file_url.lstrip("/"))
        if os.path.isfile(local_path):
            try:
                os.remove(local_path)
            except OSError as e:
                print(f"⚠️ Could not delete file on disk: {e}")

    db.delete(asset)
    db.commit()

    return {"message": "Cover deleted"}


@router.post("/{episode_id}/assemble-video")
async def assemble_video(episode_id: int, db: Session = Depends(get_db)):
    """Concatène les clips vidéo sélectionnés de l'épisode, dans l'ordre des
    plans (Shot Breakdown) — opération ffmpeg pure, aucun appel IA. Ajoute une
    intro de 2s avec le cover sélectionné, s'il en existe un."""
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    scenes = db.query(Scene).filter(Scene.episode_id == episode_id).all()
    report = build_assembly_report(episode, scenes)
    if not report["can_assemble"]:
        raise HTTPException(status_code=400, detail="No available video clips to assemble for this episode.")

    cover_path = None
    selected_cover = db.query(EpisodeAsset).filter(
        EpisodeAsset.episode_id == episode_id, EpisodeAsset.asset_type == "cover",
        EpisodeAsset.is_selected == True
    ).first()
    if selected_cover and selected_cover.file_url:
        candidate = os.path.join("app", selected_cover.file_url.lstrip("/"))
        if os.path.isfile(candidate):
            cover_path = candidate

    try:
        assembled_url = assemble_episode_video(scenes, episode_id, cover_path=cover_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video assembly failed: {e}")

    episode.assembled_video_url = assembled_url
    db.commit()

    return {"assembled_video_url": assembled_url, "report": report, "included_cover_intro": bool(cover_path)}