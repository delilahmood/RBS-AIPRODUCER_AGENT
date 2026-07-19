from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import os
import re
import shutil
import threading

from app.database import get_db, SessionLocal
from app.models.scene import Scene
from app.models.scene_asset import SceneAsset
from app.models.episode import Episode
from app.models.project import Project
from app.models.character_asset import CharacterAsset
from app.models.location_assets import LocationAsset
from app.models.character import Character
from app.models.location import Location
from app.agents.storyboard_art import StoryboardArtAgent, STORAGE_DIR, AVAILABLE_STORYBOARD_MODELS
from app.agents.scene_generator import (
    SceneGeneratorAgent, AVAILABLE_VIDEO_MODELS, DEFAULT_VIDEO_MODEL,
    AVAILABLE_RESOLUTIONS, DEFAULT_RESOLUTION,
)

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


class SceneUpdate(BaseModel):
    description: Optional[str] = None
    camera_movement: Optional[str] = None
    mood: Optional[str] = None
    dialogue: Optional[str] = None
    duration_seconds: Optional[float] = None
    character_ids: Optional[List[int]] = None
    location_id: Optional[int] = None


@router.get("/{scene_id}")
async def get_scene(scene_id: int, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.put("/{scene_id}")
async def update_scene(scene_id: int, update: SceneUpdate, db: Session = Depends(get_db)):
    """Édition manuelle d'un plan (description, caméra, personnages/décor concernés)."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    for field, value in update.dict(exclude_unset=True).items():
        setattr(scene, field, value)

    db.commit()
    db.refresh(scene)
    return scene


# ======================================================================
# STORYBOARD (image de repérage du plan) : sélection, régénération, upload
# ======================================================================

class SelectSceneImageRequest(BaseModel):
    asset_id: int


@router.post("/{scene_id}/select-image")
async def select_scene_image(scene_id: int, request: SelectSceneImageRequest, db: Session = Depends(get_db)):
    asset = db.query(SceneAsset).filter(
        SceneAsset.id == request.asset_id, SceneAsset.scene_id == scene_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Image not found")
    if asset.status != "completed":
        raise HTTPException(status_code=400, detail="Cannot select a failed image")

    db.query(SceneAsset).filter(
        SceneAsset.scene_id == scene_id, SceneAsset.asset_type == asset.asset_type
    ).update({"is_selected": False})
    asset.is_selected = True
    db.commit()

    return {"message": "Image selected", "asset_id": asset.id}


class GenerateStoryboardRequest(BaseModel):
    model: str = None
    mode: str = "one_frame"  # 'one_frame' | '2x2' | '3x3' | 'auto'
    use_prompt_director: bool = True  # False = ancien template texte seul (moins cher, plus rapide)


@router.post("/{scene_id}/generate-storyboard")
async def generate_scene_storyboard(scene_id: int, request: GenerateStoryboardRequest, db: Session = Depends(get_db)):
    """Régénère le storyboard d'UN SEUL plan, en combinant les images déjà
    sélectionnées des personnages/décor concernés — sans toucher aux autres."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id).first() if episode else None
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ref_paths = []
    character_names = []
    structured_characters = []  # [{"name", "closeup_path", "fullbody_path"}] pour l'analyse vision
    for cid in (scene.character_ids or []):
        char = db.query(Character).filter(Character.id == cid).first()
        if char:
            character_names.append(char.name)
        char_entry = {"name": char.name if char else "Character", "closeup_path": None, "fullbody_path": None}
        # Closeup (portrait) ET fullbody (Model Sheet) — le fullbody porte
        # l'info vêtements/silhouette que le closeup n'a pas.
        for asset_type, key in (("portrait", "closeup_path"), ("reference_sheet", "fullbody_path")):
            asset = db.query(CharacterAsset).filter(
                CharacterAsset.character_id == cid, CharacterAsset.asset_type == asset_type,
                CharacterAsset.is_selected == True
            ).first()
            if asset and asset.file_url:
                path = os.path.join("app", asset.file_url.lstrip("/"))
                if os.path.isfile(path):
                    ref_paths.append(path)
                    char_entry[key] = path
        structured_characters.append(char_entry)

    structured_location = None
    if scene.location_id:
        location_obj = db.query(Location).filter(Location.id == scene.location_id).first()
        loc_asset = db.query(LocationAsset).filter(
            LocationAsset.location_id == scene.location_id, LocationAsset.asset_type == "reference",
            LocationAsset.is_selected == True
        ).first()
        if loc_asset and loc_asset.file_url:
            path = os.path.join("app", loc_asset.file_url.lstrip("/"))
            if os.path.isfile(path):
                ref_paths.append(path)
                structured_location = {"name": location_obj.name if location_obj else "Location", "path": path}

    last_batch = db.query(SceneAsset).filter(
        SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "storyboard"
    ).order_by(SceneAsset.generation_batch.desc()).first()
    next_batch = (last_batch.generation_batch + 1) if last_batch else 1

    # Plans voisins (même épisode) pour la continuité narrative — permet par
    # exemple à un plan de transformation de savoir à quoi ressemblait le
    # personnage juste avant, plutôt que de partir d'un vide narratif.
    prev_scene = db.query(Scene).filter(
        Scene.episode_id == scene.episode_id, Scene.number == scene.number - 1
    ).first()
    next_scene = db.query(Scene).filter(
        Scene.episode_id == scene.episode_id, Scene.number == scene.number + 1
    ).first()
    previous_shot = {"description": prev_scene.description} if prev_scene else None
    next_shot = {"description": next_scene.description} if next_scene else None

    # Planche du plan précédent, réutilisée comme référence d'ÉTAT (niveau 3
    # de la hiérarchie APPEARANCE STATE) — UNIQUEMENT si elle a été générée en
    # grille (a un "dernier panneau" identifiable) ET si ce plan-ci n'est pas
    # en mode one_frame (pas de notion de continuité inter-planches dans ce
    # cas, cf. décision produit).
    previous_storyboard_path = None
    if prev_scene and request.mode != "one_frame":
        prev_sb_asset = db.query(SceneAsset).filter(
            SceneAsset.scene_id == prev_scene.id, SceneAsset.asset_type == "storyboard",
            SceneAsset.is_selected == True
        ).first()
        if prev_sb_asset and prev_sb_asset.file_url and prev_sb_asset.prompt_used and "BEATS:" in prev_sb_asset.prompt_used:
            candidate = os.path.join("app", prev_sb_asset.file_url.lstrip("/"))
            if os.path.isfile(candidate):
                previous_storyboard_path = candidate

    shot_dict = {
        "id": scene.id, "description": scene.description, "camera_movement": scene.camera_movement,
        "mood": scene.mood, "dialogue": scene.dialogue, "duration_seconds": scene.duration_seconds,
        "is_cliffhanger": scene.is_cliffhanger,
    }
    agent = StoryboardArtAgent()
    result = agent.generate_storyboard_frame(
        shot_dict, ref_paths, project.visual_styles or [], model=request.model, batch_number=next_batch,
        mode=request.mode, character_names=character_names,
        previous_shot=previous_shot, next_shot=next_shot,
        structured_characters=structured_characters, structured_location=structured_location,
        use_prompt_director=request.use_prompt_director,
        previous_storyboard_path=previous_storyboard_path
    )

    asset = SceneAsset(
        scene_id=scene_id,
        asset_type="storyboard",
        file_url=result["url"] or "",
        prompt_used=result["prompt_used"],
        model_used=result["model_used"],
        version=1,
        generation_batch=next_batch,
        is_selected=(not result["error"]),
        status="failed" if result["error"] else "completed",
    )
    db.add(asset)
    if not result["error"]:
        db.query(SceneAsset).filter(
            SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "storyboard",
            SceneAsset.generation_batch != next_batch
        ).update({"is_selected": False})
    db.commit()
    db.refresh(asset)

    if result["error"]:
        raise HTTPException(status_code=502, detail="Storyboard generation failed. Try a different model.")

    return {"message": "Storyboard generated", "batch": next_batch, "asset": {"id": asset.id, "url": asset.file_url}}


@router.post("/{scene_id}/upload-image")
async def upload_scene_image(scene_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Ajoute une image de storyboard retouchée par l'utilisateur."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File type not allowed")

    last_batch = db.query(SceneAsset).filter(
        SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "storyboard"
    ).order_by(SceneAsset.generation_batch.desc()).first()
    batch = last_batch.generation_batch if last_batch else 1

    filename = f"scene{scene_id}_b{batch}_upload{file_ext}"
    local_path = os.path.join(STORAGE_DIR, filename)
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    asset = SceneAsset(
        scene_id=scene_id,
        asset_type="storyboard",
        file_url=f"/static/assets/storyboards/{filename}",
        prompt_used=None,
        model_used="user_upload",
        version=1,
        generation_batch=batch,
        is_selected=False,
        status="completed",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {"message": "Image uploaded", "asset": {"id": asset.id, "url": asset.file_url}}


# ======================================================================
# GÉNÉRATION VIDÉO (R2V) : la génération prend plusieurs minutes, on ne
# bloque jamais la requête HTTP — création immédiate d'une ligne "pending",
# mise à jour en tâche de fond une fois terminée.
# ======================================================================

class GenerateVideoRequest(BaseModel):
    model: str = None
    resolution: str = None  # '720P' (défaut) ou '1080P'
    custom_prompt: str = None  # si fourni, remplace le prompt auto-construit


def _parse_storyboard_beats(prompt_used: str) -> list:
    """Extrait les descriptions des panneaux depuis le prompt stocké d'un
    storyboard généré en mode grille (repère le bloc "BEATS: ... COMPOSITION:").
    Retourne une liste vide si le storyboard a été généré en mode single —
    repli automatique et sans erreur vers le mode vidéo continu classique."""
    if not prompt_used or "BEATS:" not in prompt_used:
        return []
    match = re.search(r"BEATS:\s*(.*?)\s*COMPOSITION:", prompt_used, re.DOTALL)
    if not match:
        return []
    raw_panels = re.split(r";\s*Panel \d+\s*—\s*", match.group(1))
    return [re.sub(r"^Panel \d+\s*—\s*", "", p).strip() for p in raw_panels if p.strip()]


def _run_video_generation_in_background(scene_id: int, model: str, resolution: str, asset_id: int, custom_prompt: str = None):
    db = SessionLocal()
    try:
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
        project = db.query(Project).filter(Project.id == episode.project_id).first()

        # Storyboard sélectionné (ancrage visuel principal du plan) — chemin
        # disque local, le SDK dashscope s'occupe lui-même de l'upload.
        sb_asset = db.query(SceneAsset).filter(
            SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "storyboard",
            SceneAsset.is_selected == True
        ).first()
        storyboard_path = os.path.join("app", sb_asset.file_url.lstrip("/")) if sb_asset and sb_asset.file_url else None
        # Réutilise les 9 panneaux du storyboard si généré en mode grille —
        # même choix créatif déjà fait à cette étape (voir conversation) —
        # liste vide si mode single, aucun effet dans ce cas.
        storyboard_beats = _parse_storyboard_beats(sb_asset.prompt_used) if sb_asset else []

        # Personnages : nom + chemin local du portrait sélectionné, nécessaires
        # pour les balises @imageN (Wan) / le rappel d'identité (HappyHorse).
        character_refs = []
        for cid in (scene.character_ids or []):
            char = db.query(Character).filter(Character.id == cid).first()
            ca = db.query(CharacterAsset).filter(
                CharacterAsset.character_id == cid, CharacterAsset.asset_type == "portrait",
                CharacterAsset.is_selected == True
            ).first()
            if char and ca and ca.file_url:
                character_refs.append({"name": char.name, "path": os.path.join("app", ca.file_url.lstrip("/"))})

        location_ref = None
        if scene.location_id:
            loc = db.query(Location).filter(Location.id == scene.location_id).first()
            la = db.query(LocationAsset).filter(
                LocationAsset.location_id == scene.location_id, LocationAsset.asset_type == "reference",
                LocationAsset.is_selected == True
            ).first()
            if loc and la and la.file_url:
                location_ref = {"name": loc.name, "path": os.path.join("app", la.file_url.lstrip("/"))}

        shot_dict = {
            "id": scene.id, "description": scene.description, "camera_movement": scene.camera_movement,
            "mood": scene.mood, "dialogue": scene.dialogue, "duration_seconds": scene.duration_seconds,
        }
        agent = SceneGeneratorAgent()
        result = agent.generate_scene_video(
            shot_dict, storyboard_path, character_refs, location_ref,
            " + ".join(project.visual_styles or []),
            aspect_ratio=project.aspect_ratio or "16:9", model=model, resolution=resolution,
            has_dialogue=bool(scene.dialogue), custom_prompt=custom_prompt,
            storyboard_beats=storyboard_beats
        )

        asset = db.query(SceneAsset).filter(SceneAsset.id == asset_id).first()
        if result["error"]:
            asset.status = "failed"
            asset.prompt_used = result.get("prompt_used")
            print(f"❌ [Scenes] Génération vidéo échouée (scene {scene_id}): {result.get('error_message')}")
        else:
            asset.status = "completed"
            asset.file_url = result["url"]
            asset.prompt_used = result["prompt_used"]
            asset.model_used = result["model_used"]
            asset.duration_seconds = scene.duration_seconds
            asset.is_selected = True
            db.query(SceneAsset).filter(
                SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "video",
                SceneAsset.id != asset_id
            ).update({"is_selected": False})
        db.commit()
    except Exception as e:
        print(f"❌ [Scenes] Erreur inattendue génération vidéo (scene {scene_id}): {e}")
        try:
            asset = db.query(SceneAsset).filter(SceneAsset.id == asset_id).first()
            if asset:
                asset.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/{scene_id}/generate-video")
async def generate_scene_video_endpoint(scene_id: int, request: GenerateVideoRequest, db: Session = Depends(get_db)):
    """Lance la génération vidéo (R2V) d'UN SEUL plan, en tâche de fond —
    combine le storyboard + personnages + décor déjà sélectionnés."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Garde-fou crédits : on ne lance JAMAIS un appel payant si une référence
    # attendue (storyboard, portrait de personnage, décor) n'est pas
    # sélectionnée — mieux vaut refuser proprement que gaspiller un appel sur
    # une génération qu'on sait déjà incomplète.
    sb_asset = db.query(SceneAsset).filter(
        SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "storyboard", SceneAsset.is_selected == True
    ).first()
    if not sb_asset:
        raise HTTPException(status_code=400, detail="No storyboard selected for this shot yet.")

    missing = []
    for cid in (scene.character_ids or []):
        char = db.query(Character).filter(Character.id == cid).first()
        ca = db.query(CharacterAsset).filter(
            CharacterAsset.character_id == cid, CharacterAsset.asset_type == "portrait", CharacterAsset.is_selected == True
        ).first()
        if char and not ca:
            missing.append(char.name)
    if scene.location_id:
        loc = db.query(Location).filter(Location.id == scene.location_id).first()
        la = db.query(LocationAsset).filter(
            LocationAsset.location_id == scene.location_id, LocationAsset.asset_type == "reference", LocationAsset.is_selected == True
        ).first()
        if loc and not la:
            missing.append(loc.name)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing selected reference image for: {', '.join(missing)}")

    last_batch = db.query(SceneAsset).filter(
        SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "video"
    ).order_by(SceneAsset.generation_batch.desc()).first()
    next_batch = (last_batch.generation_batch + 1) if last_batch else 1

    model = request.model if request.model in AVAILABLE_VIDEO_MODELS else DEFAULT_VIDEO_MODEL
    resolution = request.resolution if request.resolution in AVAILABLE_RESOLUTIONS else DEFAULT_RESOLUTION

    asset = SceneAsset(
        scene_id=scene_id, asset_type="video", file_url="", model_used=model,
        version=1, generation_batch=next_batch, is_selected=False, status="pending",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    thread = threading.Thread(
        target=_run_video_generation_in_background,
        args=(scene_id, model, resolution, asset.id, request.custom_prompt), daemon=True
    )
    thread.start()

    return {"message": "Video generation started — this may take a few minutes", "asset_id": asset.id, "batch": next_batch}


class SelectVideoRequest(BaseModel):
    asset_id: int


@router.post("/{scene_id}/select-video")
async def select_scene_video(scene_id: int, request: SelectVideoRequest, db: Session = Depends(get_db)):
    """Choisit une vidéo parmi les lots précédents comme vidéo officielle du
    plan. Ne supprime rien : les autres lots restent en base."""
    asset = db.query(SceneAsset).filter(
        SceneAsset.id == request.asset_id, SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "video"
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found")
    if asset.status != "completed":
        raise HTTPException(status_code=400, detail="Cannot select a failed or pending video")

    db.query(SceneAsset).filter(
        SceneAsset.scene_id == scene_id, SceneAsset.asset_type == "video"
    ).update({"is_selected": False})
    asset.is_selected = True
    db.commit()

    return {"message": "Video selected", "asset_id": asset.id}
