from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
import os
import re

from app.database import get_db
from app.models.project import Project
from app.models.character import Character
from app.models.character_asset import CharacterAsset
from app.models.episode import Episode
from app.models.location import Location
from app.models.location_assets import LocationAsset
from app.models.scene import Scene
from app.models.scene_asset import SceneAsset
from app.services.export_service import build_markdown, build_pdf

router = APIRouter(prefix="/api/projects", tags=["export"])

VALID_SECTIONS = {"all", "synopsis", "casting", "script", "images", "locations", "storyboard"}
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


def _safe_filename(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", (title or "project").strip())
    return slug[:60] or "project"


def _get_project_data(project_id: int, db: Session):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    characters = db.query(Character).filter(Character.project_id == project_id).all()
    episodes = db.query(Episode).filter(Episode.project_id == project_id).order_by(Episode.episode_number.asc()).all()
    locations = db.query(Location).filter(Location.project_id == project_id).all()

    # Portrait sélectionné de chaque personnage (celui validé par l'utilisateur, pas les propositions)
    for c in characters:
        selected = db.query(CharacterAsset).filter(
            CharacterAsset.character_id == c.id, CharacterAsset.asset_type == "portrait",
            CharacterAsset.is_selected == True
        ).first()
        c.selected_portrait_url = selected.file_url if selected else None

    for l in locations:
        selected = db.query(LocationAsset).filter(
            LocationAsset.location_id == l.id, LocationAsset.asset_type == "reference",
            LocationAsset.is_selected == True
        ).first()
        l.selected_image_url = selected.file_url if selected else None

    episode_ids = [e.id for e in episodes]
    scenes = []
    if episode_ids:
        scenes = db.query(Scene).filter(Scene.episode_id.in_(episode_ids)).order_by(Scene.episode_id.asc(), Scene.number.asc()).all()
        for s in scenes:
            selected = db.query(SceneAsset).filter(
                SceneAsset.scene_id == s.id, SceneAsset.asset_type == "storyboard",
                SceneAsset.is_selected == True
            ).first()
            s.selected_storyboard_url = selected.file_url if selected else None
            s.episode_title = next((e.title for e in episodes if e.id == s.episode_id), "")
            s.character_names = [c.name for c in characters if c.id in (s.character_ids or [])]
            s.location_name = next((l.name for l in locations if l.id == s.location_id), None)

    return project, characters, episodes, locations, scenes


@router.get("/{project_id}/export/markdown")
def export_markdown(
    project_id: int,
    section: str = Query("all", description="all | synopsis | casting | script | images | locations | storyboard"),
    db: Session = Depends(get_db)
):
    if section not in VALID_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}")

    project, characters, episodes, locations, scenes = _get_project_data(project_id, db)
    content = build_markdown(project, characters, episodes, section=section, locations=locations, scenes=scenes)
    filename = f"{_safe_filename(project.title)}_{section}.md"

    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{project_id}/export/pdf")
def export_pdf(
    project_id: int,
    section: str = Query("all", description="all | synopsis | casting | script | images | locations | storyboard"),
    db: Session = Depends(get_db)
):
    if section not in VALID_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}")

    project, characters, episodes, locations, scenes = _get_project_data(project_id, db)
    pdf_bytes = build_pdf(project, characters, episodes, section=section, static_dir=STATIC_DIR,
                           locations=locations, scenes=scenes)
    filename = f"{_safe_filename(project.title)}_{section}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
