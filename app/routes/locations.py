from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os
import shutil

from app.database import get_db
from app.models.location import Location
from app.models.location_assets import LocationAsset
from app.models.project import Project
from app.models.character import Character
from app.agents.location_visualizer import LocationDesignAgent, STORAGE_DIR, _slugify

router = APIRouter(prefix="/api/locations", tags=["locations"])


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mood: Optional[str] = None
    key_visual_details: Optional[str] = None


@router.get("/{location_id}")
async def get_location(location_id: int, db: Session = Depends(get_db)):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.put("/{location_id}")
async def update_location(location_id: int, update: LocationUpdate, db: Session = Depends(get_db)):
    """Édition manuelle d'une fiche lieu."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    for field, value in update.dict(exclude_unset=True).items():
        setattr(location, field, value)

    db.commit()
    db.refresh(location)
    return location


@router.delete("/{location_id}")
async def delete_location(location_id: int, db: Session = Depends(get_db)):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    db.delete(location)
    db.commit()
    return {"message": "Location deleted successfully"}


# ======================================================================
# IMAGES DE LIEU : sélection, régénération individuelle, upload manuel
# ======================================================================

class SelectLocationImageRequest(BaseModel):
    asset_id: int


@router.post("/{location_id}/select-image")
async def select_location_image(location_id: int, request: SelectLocationImageRequest, db: Session = Depends(get_db)):
    """Choisit une proposition d'image comme référence officielle du lieu.
    Ne supprime rien : les autres propositions restent en base."""
    asset = db.query(LocationAsset).filter(
        LocationAsset.id == request.asset_id, LocationAsset.location_id == location_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Image not found")
    if asset.status != "completed":
        raise HTTPException(status_code=400, detail="Cannot select a failed image")

    db.query(LocationAsset).filter(
        LocationAsset.location_id == location_id,
        LocationAsset.asset_type == asset.asset_type
    ).update({"is_selected": False})
    asset.is_selected = True
    db.commit()

    return {"message": "Image selected", "asset_id": asset.id}


class GenerateLocationImagesRequest(BaseModel):
    model: str = None  # 'wan2.2-t2i-plus' (défaut), 'wan2.6-t2i' ou 'wan2.7-image-pro'


@router.post("/{location_id}/generate-images")
async def generate_location_images(location_id: int, request: GenerateLocationImagesRequest = None, db: Session = Depends(get_db)):
    """Régénère les images d'UN SEUL lieu, sans toucher aux autres."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    project = db.query(Project).filter(Project.id == location.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    last_batch = db.query(LocationAsset).filter(
        LocationAsset.location_id == location_id,
        LocationAsset.asset_type == "reference"
    ).order_by(LocationAsset.generation_batch.desc()).first()
    next_batch = (last_batch.generation_batch + 1) if last_batch else 1

    loc_dict = {
        "id": location.id, "name": location.name, "description": location.description,
        "mood": location.mood, "key_visual_details": location.key_visual_details,
    }
    character_names = [c.name for c in db.query(Character).filter(Character.project_id == location.project_id).all()]
    agent = LocationDesignAgent()
    model = request.model if request and request.model else None
    proposals = agent.generate_proposals(
        loc_dict, project.visual_styles or [], project.world_style_prompt, batch_number=next_batch,
        character_names=character_names, model=model
    )

    created = []
    for p in proposals:
        asset = LocationAsset(
            location_id=location_id,
            asset_type="reference",
            file_url=p["url"] or "",
            prompt_used=p["prompt_used"],
            model_used=p["model_used"],
            version=p["proposal_number"],
            generation_batch=next_batch,
            is_selected=(p["proposal_number"] == 1 and not p["error"]),
            status="failed" if p["error"] else "completed",
        )
        db.add(asset)
        created.append(asset)

    db.query(LocationAsset).filter(
        LocationAsset.location_id == location_id,
        LocationAsset.asset_type == "reference",
        LocationAsset.generation_batch != next_batch
    ).update({"is_selected": False})
    db.commit()

    failed = sum(1 for p in proposals if p["error"])
    return {
        "message": f"{len(proposals) - failed}/{len(proposals)} image(s) generated",
        "batch": next_batch,
        "assets": [{"id": a.id, "url": a.file_url, "version": a.version, "status": a.status} for a in created],
    }


@router.post("/{location_id}/upload-image")
async def upload_location_image(
    location_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Ajoute une image retouchée par l'utilisateur comme proposition
    supplémentaire pour ce lieu — sélectionnable comme les autres."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File type not allowed")

    last_batch = db.query(LocationAsset).filter(
        LocationAsset.location_id == location_id,
        LocationAsset.asset_type == "reference"
    ).order_by(LocationAsset.generation_batch.desc()).first()
    batch = last_batch.generation_batch if last_batch else 1

    existing_in_batch = db.query(LocationAsset).filter(
        LocationAsset.location_id == location_id,
        LocationAsset.asset_type == "reference",
        LocationAsset.generation_batch == batch
    ).count()
    proposal_number = existing_in_batch + 1

    slug = _slugify(location.name)
    filename = f"{location_id}_{slug}_b{batch}p{proposal_number}_upload{file_ext}"
    local_path = os.path.join(STORAGE_DIR, filename)
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    asset = LocationAsset(
        location_id=location_id,
        asset_type="reference",
        file_url=f"/static/assets/locations/{filename}",
        prompt_used=None,
        model_used="user_upload",
        version=proposal_number,
        generation_batch=batch,
        is_selected=False,
        status="completed",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {"message": "Image uploaded", "asset": {"id": asset.id, "url": asset.file_url, "version": asset.version}}
