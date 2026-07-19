from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.project import Project
from app.models.skill_execution import SkillExecution
from app.models.character import Character
from app.models.episode import Episode
from app.models.character_asset import CharacterAsset
from app.models.location import Location
from app.models.location_assets import LocationAsset
from app.models.scene import Scene
from app.models.scene_asset import SceneAsset
from app.agents.workflow_engine import WorkflowEngine
from pydantic import BaseModel, field_validator
from typing import List, Optional
import threading
import json


router = APIRouter(prefix="/api/projects", tags=["generation"])

class GenerateRequest(BaseModel):
    workflow_steps: Optional[List[str]] = ["synopsis", "script", "casting"]
    auto_approve: bool = True


def _run_pipeline_in_background(project_id: int, auto_approve: bool, workflow_steps: list):
    """Exécuté dans un thread séparé : ne bloque pas la requête HTTP.
    Chaque étape se persiste elle-même en base au fur et à mesure
    (voir WorkflowEngine._append_entry / _finish_skill)."""
    db = SessionLocal()
    try:
        # ⚠️ Important : si l'utilisateur relance "Generate" sur un projet qui
        # a déjà des personnages/épisodes (générés lors d'un essai précédent),
        # il faut les nettoyer avant de relancer le pipeline. Sinon les
        # anciens personnages s'accumulent en base et polluent le Scriptwriter
        # (qui lit TOUS les personnages du projet), produisant un script
        # incohérent mélangeant plusieurs histoires.
        if "casting" in (workflow_steps or []):
            db.query(Character).filter(Character.project_id == project_id).delete()
        if "script" in (workflow_steps or []):
            db.query(Episode).filter(Episode.project_id == project_id).delete()
        if "location_scout" in (workflow_steps or []):
            db.query(Location).filter(Location.project_id == project_id).delete()
        # NB: "images"/"location_design" n'effacent plus rien ici — l'historique
        # par lot (generation_batch) est géré directement dans workflow_engine.py,
        # qui préserve les anciennes propositions plutôt que de les supprimer.
        db.commit()

        engine = WorkflowEngine()
        engine.run_pipeline(
            project_id=project_id,
            auto_approve=auto_approve,
            workflow_steps=workflow_steps
        )
        # Statut final : 'ready' si aucune étape 'failed', sinon 'partial'
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.status == "generating":
            failed = db.query(SkillExecution).filter(
                SkillExecution.project_id == project_id,
                SkillExecution.status == "failed"
            ).first()
            project.status = "partial" if failed else "ready"
            db.commit()
    finally:
        db.close()


@router.post("/{project_id}/generate")
def generate_project(project_id: int, request: GenerateRequest, db: Session = Depends(get_db)):
    """Démarre le WorkflowEngine en arrière-plan et retourne immédiatement.
    Le frontend doit ensuite interroger GET /{project_id}/generation-status
    pour suivre la progression en direct (polling)."""

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "generating"
    db.commit()

    thread = threading.Thread(
        target=_run_pipeline_in_background,
        args=(project_id, request.auto_approve, request.workflow_steps),
        daemon=True
    )
    thread.start()

    return {
        "status": "started",
        "project_id": project_id,
        "message": "Generation started. Poll /generation-status for progress."
    }

@router.get("/{project_id}/generation-status")
async def get_generation_status(project_id: int, db: Session = Depends(get_db)):
    """État de la génération, à interroger en polling par le frontend pour
    construire/rafraîchir la Production Timeline (et la restaurer après un
    rechargement de page, puisque tout est déjà en base)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # On garde la dernière exécution de chaque skill (au cas où il y en aurait
    # plusieurs suite à une régénération)
    executions = db.query(SkillExecution).filter(
        SkillExecution.project_id == project_id
    ).order_by(SkillExecution.id.asc()).all()

    generations = {}
    for exec in executions:
        try:
            parsed_logs = json.loads(exec.logs) if exec.logs else []
        except (json.JSONDecodeError, TypeError):
            parsed_logs = []
        try:
            parsed_result = json.loads(exec.result_data) if exec.result_data else None
        except (json.JSONDecodeError, TypeError):
            parsed_result = None

        generations[exec.skill_name] = {
            "status": exec.status,
            "logs": parsed_logs,
            "result": parsed_result,
            "started_at": exec.started_at.isoformat() if exec.started_at else None,
            "finished_at": exec.finished_at.isoformat() if exec.finished_at else None
        }

    characters = db.query(Character).filter(Character.project_id == project_id).all()
    episodes = db.query(Episode).filter(Episode.project_id == project_id).order_by(Episode.episode_number.asc()).all()
    locations = db.query(Location).filter(Location.project_id == project_id).all()

    char_ids = [c.id for c in characters]
    assets_by_char = {}
    if char_ids:
        assets = db.query(CharacterAsset).filter(
            CharacterAsset.character_id.in_(char_ids)
        ).order_by(CharacterAsset.id.asc()).all()
        for a in assets:
            assets_by_char.setdefault(a.character_id, []).append({
                "id": a.id,
                "url": a.file_url,
                "asset_type": a.asset_type,
                "version": a.version,
                "generation_batch": a.generation_batch,
                "is_selected": a.is_selected,
                "status": a.status,
                "prompt_used": a.prompt_used,
                "model_used": a.model_used,
            })

    loc_ids = [l.id for l in locations]
    assets_by_location = {}
    if loc_ids:
        loc_assets = db.query(LocationAsset).filter(
            LocationAsset.location_id.in_(loc_ids)
        ).order_by(LocationAsset.id.asc()).all()
        for a in loc_assets:
            assets_by_location.setdefault(a.location_id, []).append({
                "id": a.id,
                "url": a.file_url,
                "asset_type": a.asset_type,
                "version": a.version,
                "generation_batch": a.generation_batch,
                "is_selected": a.is_selected,
                "status": a.status,
                "prompt_used": a.prompt_used,
                "model_used": a.model_used,
            })

    episode_ids = [e.id for e in episodes]
    assets_by_episode = {}
    if episode_ids:
        from app.models.episode_asset import EpisodeAsset
        ep_assets = db.query(EpisodeAsset).filter(
            EpisodeAsset.episode_id.in_(episode_ids)
        ).order_by(EpisodeAsset.id.asc()).all()
        for a in ep_assets:
            assets_by_episode.setdefault(a.episode_id, []).append({
                "id": a.id,
                "url": a.file_url,
                "asset_type": a.asset_type,
                "version": a.version,
                "generation_batch": a.generation_batch,
                "is_selected": a.is_selected,
                "status": a.status,
                "prompt_used": a.prompt_used,
                "model_used": a.model_used,
            })

    episode_ids = [e.id for e in episodes]
    scenes = []
    assets_by_scene = {}
    if episode_ids:
        scenes = db.query(Scene).filter(Scene.episode_id.in_(episode_ids)).order_by(Scene.episode_id.asc(), Scene.number.asc()).all()
        scene_ids = [s.id for s in scenes]
        if scene_ids:
            scene_assets = db.query(SceneAsset).filter(SceneAsset.scene_id.in_(scene_ids)).order_by(SceneAsset.id.asc()).all()
            for a in scene_assets:
                assets_by_scene.setdefault(a.scene_id, []).append({
                    "id": a.id,
                    "url": a.file_url,
                    "asset_type": a.asset_type,
                    "version": a.version,
                    "generation_batch": a.generation_batch,
                    "is_selected": a.is_selected,
                    "status": a.status,
                    "prompt_used": a.prompt_used,
                    "model_used": a.model_used,
                })

    return {
        "project_status": project.status,
        "project": {
            "id": project.id,
            "title": project.title,
            "synopsis": project.synopsis,
            "hook": project.hook,
            "production_note": project.production_note,
        },
        "generations": generations,
        "characters": [
            {
                "id": c.id,
                "name": c.name,
                "alias": c.alias,
                "role": c.role,
                "age": c.age,
                "description": c.description,
                "traits": c.traits,
                "objective": c.objective,
                "visual_trait": c.visual_trait,
                "secret": c.secret,
                "has_secret": c.has_secret,
                "arc_potential": c.arc_potential,
                "assets": assets_by_char.get(c.id, []),
            }
            for c in characters
        ],
        "locations": [
            {
                "id": l.id,
                "name": l.name,
                "description": l.description,
                "mood": l.mood,
                "key_visual_details": l.key_visual_details,
                "assets": assets_by_location.get(l.id, []),
            }
            for l in locations
        ],
        "episodes": [
            {
                "id": e.id,
                "title": e.title,
                "script_content": e.script_content,
                "episode_number": e.episode_number,
                "ends_with_cliffhanger": e.ends_with_cliffhanger,
                "cliffhanger_description": e.cliffhanger_description,
                "assembled_video_url": e.assembled_video_url,
                "assets": assets_by_episode.get(e.id, []),
            }
            for e in episodes
        ],
        "scenes": [
            {
                "id": s.id,
                "episode_id": s.episode_id,
                "number": s.number,
                "description": s.description,
                "camera_movement": s.camera_movement,
                "mood": s.mood,
                "dialogue": s.dialogue,
                "character_ids": s.character_ids,
                "location_id": s.location_id,
                "duration_seconds": s.duration_seconds,
                "is_cliffhanger": s.is_cliffhanger,
                "cliffhanger_description": s.cliffhanger_description,
                "assets": assets_by_scene.get(s.id, []),
            }
            for s in scenes
        ]
    }


# ======================================================================
# ÉDITION MANUELLE DU CONTENU GÉNÉRÉ (Edit / Save)
# ======================================================================

class SynopsisEditRequest(BaseModel):
    synopsis: str
    hook: Optional[str] = None

    @field_validator("synopsis")
    @classmethod
    def synopsis_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("Synopsis cannot be empty.")
        return v


def _mark_stale(db: Session, project_id: int, skill_names: List[str]):
    """Marque les cartes déjà terminées comme potentiellement obsolètes suite
    à l'édition manuelle d'une étape dont elles dépendent. Ne relance RIEN
    automatiquement : c'est à l'utilisateur de décider de régénérer."""
    for skill_name in skill_names:
        execution = db.query(SkillExecution).filter(
            SkillExecution.project_id == project_id,
            SkillExecution.skill_name == skill_name,
            SkillExecution.status == "completed"
        ).order_by(SkillExecution.id.desc()).first()
        if execution:
            try:
                result = json.loads(execution.result_data) if execution.result_data else {}
            except (json.JSONDecodeError, TypeError):
                result = {}
            result["stale"] = True
            execution.result_data = json.dumps(result, default=str)
            db.add(execution)
    db.commit()


@router.put("/{project_id}/synopsis")
def edit_synopsis(project_id: int, request: SynopsisEditRequest, db: Session = Depends(get_db)):
    """Édition manuelle du synopsis/hook (carte Showrunner)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.synopsis = request.synopsis
    if request.hook is not None:
        project.hook = request.hook
    db.commit()

    # Le Casting et le Script dépendent du synopsis : on les signale "stale"
    # sans jamais les relancer automatiquement.
    _mark_stale(db, project_id, ["casting", "scriptwriter"])

    return {"message": "Synopsis updated", "synopsis": project.synopsis, "hook": project.hook}


class EpisodeEditRequest(BaseModel):
    title: Optional[str] = None
    script_content: str

    @field_validator("script_content")
    @classmethod
    def script_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("Script content cannot be empty.")
        return v


@router.put("/{project_id}/episodes/{episode_id}")
def edit_episode(project_id: int, episode_id: int, request: EpisodeEditRequest, db: Session = Depends(get_db)):
    """Édition manuelle du script (carte Scriptwriter)."""
    episode = db.query(Episode).filter(
        Episode.id == episode_id, Episode.project_id == project_id
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    episode.script_content = request.script_content
    if request.title is not None:
        episode.title = request.title
    db.commit()

    return {"message": "Episode updated", "title": episode.title, "script_content": episode.script_content}


# ======================================================================
# RÉGÉNÉRATION PARTIELLE (Regenerate)
# ======================================================================

PIPELINE_ORDER = ["synopsis", "casting", "script", "images", "location_scout", "location_design", "shot_breakdown", "storyboard_art"]
SKILL_TO_STEP = {
    "showrunner": "synopsis", "casting": "casting", "scriptwriter": "script",
    "character_visualizer": "images", "location_scout": "location_scout", "location_design": "location_design",
    "shot_breakdown": "shot_breakdown", "storyboard_art": "storyboard_art",
}


class RegenerateRequest(BaseModel):
    skill_name: str  # 'showrunner' | 'casting' | 'scriptwriter'
    cascade: bool = False  # si True, régénère aussi les étapes suivantes


def _run_regeneration_in_background(project_id: int, workflow_steps: list):
    db = SessionLocal()
    try:
        # Nettoyer les données existantes des étapes qui vont être régénérées,
        # pour éviter les doublons (ex: personnages en double). "images"/
        # "location_design" ne suppriment rien : les lots précédents sont
        # préservés (voir workflow_engine.py).
        if "casting" in workflow_steps:
            db.query(Character).filter(Character.project_id == project_id).delete()
        if "script" in workflow_steps:
            db.query(Episode).filter(Episode.project_id == project_id).delete()
        if "location_scout" in workflow_steps:
            db.query(Location).filter(Location.project_id == project_id).delete()
        db.commit()

        engine = WorkflowEngine()
        engine.run_pipeline(project_id=project_id, auto_approve=True, workflow_steps=workflow_steps)

        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.status == "generating":
            failed = db.query(SkillExecution).filter(
                SkillExecution.project_id == project_id,
                SkillExecution.status == "failed"
            ).first()
            project.status = "partial" if failed else "ready"
            db.commit()
    finally:
        db.close()


@router.post("/{project_id}/regenerate")
def regenerate_step(project_id: int, request: RegenerateRequest, db: Session = Depends(get_db)):
    """Relance UNE étape du pipeline (et éventuellement les suivantes si
    cascade=True), sans jamais le faire automatiquement : c'est toujours un
    clic explicite de l'utilisateur sur le bouton 'Regenerate' d'une carte."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    step = SKILL_TO_STEP.get(request.skill_name)
    if not step:
        raise HTTPException(status_code=400, detail=f"Unknown skill_name: {request.skill_name}")

    if request.cascade:
        start_idx = PIPELINE_ORDER.index(step)
        workflow_steps = PIPELINE_ORDER[start_idx:]
    else:
        workflow_steps = [step]

    project.status = "generating"
    db.commit()

    thread = threading.Thread(
        target=_run_regeneration_in_background,
        args=(project_id, workflow_steps),
        daemon=True
    )
    thread.start()

    return {"status": "started", "project_id": project_id, "workflow_steps": workflow_steps}


# ======================================================================
# HISTORIQUE DES VERSIONS & RESTAURATION
# ======================================================================
# Chaque (re)génération crée une NOUVELLE ligne SkillExecution plutôt que de
# réécrire l'ancienne (voir WorkflowEngine._start_skill). Rien n'est donc
# perdu : on peut lister toutes les versions passées et en restaurer une,
# sans avoir eu besoin de prévoir un vrai système de versioning au départ.

def _summarize_version(skill_name: str, result: dict) -> str:
    if not result:
        return "(no data)"
    if skill_name == "showrunner":
        return result.get("hook") or "(no hook)"
    if skill_name == "casting":
        chars = result.get("characters", [])
        names = ", ".join(c.get("name", "?") for c in chars)
        return f"{len(chars)} character(s) — {names}" if chars else "(no characters)"
    if skill_name == "scriptwriter":
        eps = result.get("episodes", [])
        titles = ", ".join(e.get("title", "?") for e in eps)
        return f"{len(eps)} episode(s) — {titles}" if eps else "(no episodes)"
    return "(no data)"


@router.get("/{project_id}/history/{skill_name}")
def get_version_history(project_id: int, skill_name: str, db: Session = Depends(get_db)):
    """Liste toutes les versions passées (générations + régénérations) d'une
    étape, en lecture seule, pour permettre à l'utilisateur de comparer et
    éventuellement restaurer une ancienne version."""
    executions = db.query(SkillExecution).filter(
        SkillExecution.project_id == project_id,
        SkillExecution.skill_name == skill_name,
        SkillExecution.status == "completed"
    ).order_by(SkillExecution.id.asc()).all()

    versions = []
    for idx, execution in enumerate(executions, start=1):
        try:
            result = json.loads(execution.result_data) if execution.result_data else {}
        except (json.JSONDecodeError, TypeError):
            result = {}
        versions.append({
            "execution_id": execution.id,
            "version_number": idx,
            "created_at": execution.finished_at.isoformat() if execution.finished_at else None,
            "summary": _summarize_version(skill_name, result),
            "result": result,
        })

    versions.reverse()  # la plus récente en premier
    return {"skill_name": skill_name, "versions": versions}


class RestoreRequest(BaseModel):
    skill_name: str
    execution_id: int


@router.post("/{project_id}/restore")
def restore_version(project_id: int, request: RestoreRequest, db: Session = Depends(get_db)):
    """Restaure une ancienne version d'une étape (remplace le contenu actuel).
    Ne fusionne rien automatiquement : c'est un remplacement complet et
    explicite, déclenché uniquement par un clic utilisateur."""
    execution = db.query(SkillExecution).filter(
        SkillExecution.id == request.execution_id,
        SkillExecution.project_id == project_id,
        SkillExecution.skill_name == request.skill_name
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Version not found")

    try:
        result = json.loads(execution.result_data) if execution.result_data else {}
    except (json.JSONDecodeError, TypeError):
        result = {}

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.skill_name == "showrunner":
        project.synopsis = result.get("synopsis", project.synopsis)
        project.hook = result.get("hook", project.hook)
        db.commit()
        _mark_stale(db, project_id, ["casting", "scriptwriter"])

    elif request.skill_name == "casting":
        db.query(Character).filter(Character.project_id == project_id).delete()
        for char_dict in result.get("characters", []):
            db.add(Character(
                project_id=project_id,
                name=char_dict.get("name", "Unknown"),
                alias=char_dict.get("alias") or None,
                role=char_dict.get("role", "Supporting"),
                age=char_dict.get("age") if isinstance(char_dict.get("age"), int) else None,
                description=char_dict.get("visual_trait", ""),
                traits=char_dict.get("traits") or [],
                objective=char_dict.get("objective", ""),
                visual_trait=char_dict.get("visual_trait", ""),
                secret=char_dict.get("secret", ""),
                has_secret=bool(char_dict.get("secret")),
                arc_potential=char_dict.get("arc_potential", ""),
            ))
        db.commit()
        _mark_stale(db, project_id, ["scriptwriter"])

    elif request.skill_name == "scriptwriter":
        db.query(Episode).filter(Episode.project_id == project_id).delete()
        for ep_dict in result.get("episodes", []):
            ep_num = ep_dict.get("episode_number", 1)
            db.add(Episode(
                project_id=project_id,
                title=ep_dict.get("title", f"Episode {ep_num}"),
                script_content=ep_dict.get("script_content", ""),
                episode_number=ep_num,
                season=1,
                number=ep_num,
                ends_with_cliffhanger=bool(ep_dict.get("ends_with_cliffhanger")),
                cliffhanger_description=ep_dict.get("cliffhanger_description"),
            ))
        db.commit()

    else:
        raise HTTPException(status_code=400, detail=f"Unknown skill_name: {request.skill_name}")

    return {"message": "Version restored", "skill_name": request.skill_name}