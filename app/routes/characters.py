from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.character import Character, CharacterRelation
from app.schemas.character import CharacterCreate, CharacterUpdate, CharacterResponse, CharacterRelationCreate, CharacterRelationResponse

router = APIRouter(prefix="/api/characters", tags=["characters"])

@router.get("/project/{project_id}", response_model=List[CharacterResponse])
async def get_characters(project_id: int, db: Session = Depends(get_db)):
    characters = db.query(Character).filter(Character.project_id == project_id).all()
    return characters

@router.post("/", response_model=CharacterResponse)
async def create_character(character: CharacterCreate, db: Session = Depends(get_db)):
    db_character = Character(
        project_id=character.project_id,
        name=character.name,
        alias=character.alias,
        role=character.role,
        age=character.age,
        description=character.description,
        traits=character.traits,
        reference_images=character.reference_images,
        is_agent=character.is_agent
    )
    db.add(db_character)
    db.commit()
    db.refresh(db_character)
    return db_character

@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: int, db: Session = Depends(get_db)):
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character

# ✅ CORRECTION : Utilise CharacterRelationResponse (Pydantic) au lieu de CharacterRelation (SQLAlchemy)
@router.post("/{character_id}/relations", response_model=CharacterRelationResponse)
async def create_character_relation(
    character_id: int, 
    relation: CharacterRelationCreate, 
    db: Session = Depends(get_db)
):
    db_relation = CharacterRelation(
        character_id=character_id,
        related_character_id=relation.related_character_id,
        relation_type=relation.relation_type,
        description=relation.description
    )
    db.add(db_relation)
    db.commit()
    db.refresh(db_relation)
    return db_relation

@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(character_id: int, update: CharacterUpdate, db: Session = Depends(get_db)):
    """Édition manuelle d'une fiche personnage (carte Casting)."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    for field, value in update.dict(exclude_unset=True).items():
        setattr(character, field, value)

    # Si un secret est renseigné/retiré manuellement, on garde has_secret cohérent
    if "secret" in update.dict(exclude_unset=True):
        character.has_secret = bool(character.secret)

    db.commit()
    db.refresh(character)

    # Le Script dépend des personnages : on le signale "stale" sans le relancer
    from app.models.skill_execution import SkillExecution
    import json as _json
    execution = db.query(SkillExecution).filter(
        SkillExecution.project_id == character.project_id,
        SkillExecution.skill_name == "scriptwriter",
        SkillExecution.status == "completed"
    ).order_by(SkillExecution.id.desc()).first()
    if execution:
        try:
            result = _json.loads(execution.result_data) if execution.result_data else {}
        except (_json.JSONDecodeError, TypeError):
            result = {}
        result["stale"] = True
        execution.result_data = _json.dumps(result, default=str)
        db.add(execution)
        db.commit()

    return character


@router.delete("/{character_id}")
async def delete_character(character_id: int, db: Session = Depends(get_db)):
    db_character = db.query(Character).filter(Character.id == character_id).first()
    if not db_character:
        raise HTTPException(status_code=404, detail="Character not found")

    project_id = db_character.project_id
    db.delete(db_character)
    db.commit()

    # Le Script dépend des personnages : on le signale "stale" sans le relancer
    from app.models.skill_execution import SkillExecution
    import json as _json
    execution = db.query(SkillExecution).filter(
        SkillExecution.project_id == project_id,
        SkillExecution.skill_name == "scriptwriter",
        SkillExecution.status == "completed"
    ).order_by(SkillExecution.id.desc()).first()
    if execution:
        try:
            result = _json.loads(execution.result_data) if execution.result_data else {}
        except (_json.JSONDecodeError, TypeError):
            result = {}
        result["stale"] = True
        execution.result_data = _json.dumps(result, default=str)
        db.add(execution)
        db.commit()

    return {"message": "Character deleted successfully"}


# ======================================================================
# IMAGES DE PERSONNAGE : sélection, régénération individuelle, upload manuel
# ======================================================================

from fastapi import UploadFile, File, Form
from pydantic import BaseModel
from app.models.character_asset import CharacterAsset
from app.agents.character_visualizer import CharacterVisualizerAgent, STORAGE_DIR, _slugify
from app.models.project import Project
import os
import shutil


class SelectImageRequest(BaseModel):
    asset_id: int


@router.post("/{character_id}/select-image")
async def select_character_image(character_id: int, request: SelectImageRequest, db: Session = Depends(get_db)):
    """Choisit une proposition d'image comme image officielle du personnage.
    Ne supprime rien : les autres propositions (et anciens lots) restent en
    base, juste non sélectionnées — l'utilisateur peut changer d'avis à tout
    moment."""
    asset = db.query(CharacterAsset).filter(
        CharacterAsset.id == request.asset_id, CharacterAsset.character_id == character_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Image not found")
    if asset.status != "completed":
        raise HTTPException(status_code=400, detail="Cannot select a failed image")

    db.query(CharacterAsset).filter(
        CharacterAsset.character_id == character_id,
        CharacterAsset.asset_type == asset.asset_type  # déduit du type de l'asset choisi (portrait OU reference_sheet)
    ).update({"is_selected": False})
    asset.is_selected = True
    db.commit()

    return {"message": "Image selected", "asset_id": asset.id}


class GenerateCharacterImagesRequest(BaseModel):
    model: str = None  # 'wan2.2-t2i-plus' (défaut), 'wan2.6-t2i' ou 'wan2.7-image-pro'


@router.post("/{character_id}/generate-images")
async def generate_character_images(character_id: int, request: GenerateCharacterImagesRequest = None, db: Session = Depends(get_db)):
    """Régénère les images d'UN SEUL personnage, sans toucher aux autres —
    évite de gaspiller des crédits API sur des personnages déjà satisfaisants.
    Synchrone (juste 2 images) : pas besoin de passer par le mécanisme complet
    de la Timeline pour ça."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    project = db.query(Project).filter(Project.id == character.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    last_batch = db.query(CharacterAsset).filter(
        CharacterAsset.character_id == character_id,
        CharacterAsset.asset_type == "portrait"
    ).order_by(CharacterAsset.generation_batch.desc()).first()
    next_batch = (last_batch.generation_batch + 1) if last_batch else 1

    char_dict = {
        "id": character.id, "name": character.name, "role": character.role,
        "age": character.age, "visual_trait": character.visual_trait, "traits": character.traits,
    }
    agent = CharacterVisualizerAgent()
    model = request.model if request and request.model else None
    proposals = agent.generate_proposals(
        char_dict, project.visual_styles or [], project.character_style_prompt, batch_number=next_batch,
        model=model
    )

    created = []
    for p in proposals:
        asset = CharacterAsset(
            character_id=character_id,
            asset_type="portrait",
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

    db.query(CharacterAsset).filter(
        CharacterAsset.character_id == character_id,
        CharacterAsset.asset_type == "portrait",
        CharacterAsset.generation_batch != next_batch
    ).update({"is_selected": False})
    db.commit()

    failed = sum(1 for p in proposals if p["error"])
    return {
        "message": f"{len(proposals) - failed}/{len(proposals)} image(s) generated",
        "batch": next_batch,
        "assets": [{"id": a.id, "url": a.file_url, "version": a.version, "status": a.status} for a in created],
    }


@router.post("/{character_id}/upload-image")
async def upload_character_image(
    character_id: int,
    file: UploadFile = File(...),
    asset_type: str = Form("portrait"),
    db: Session = Depends(get_db)
):
    """Ajoute une image retouchée par l'utilisateur (Photoshop, etc.) comme
    proposition supplémentaire pour ce personnage — sélectionnable exactement
    comme les propositions générées par IA. `asset_type` = 'portrait' ou
    'reference_sheet' (Model Sheet)."""
    if asset_type not in ("portrait", "reference_sheet"):
        raise HTTPException(status_code=400, detail="Invalid asset_type")

    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File type not allowed")

    last_batch = db.query(CharacterAsset).filter(
        CharacterAsset.character_id == character_id,
        CharacterAsset.asset_type == asset_type
    ).order_by(CharacterAsset.generation_batch.desc()).first()
    batch = last_batch.generation_batch if last_batch else 1

    # Numéro de proposition suivant, au sein de ce lot
    existing_in_batch = db.query(CharacterAsset).filter(
        CharacterAsset.character_id == character_id,
        CharacterAsset.asset_type == asset_type,
        CharacterAsset.generation_batch == batch
    ).count()
    proposal_number = existing_in_batch + 1

    slug = _slugify(character.name)
    type_tag = "sheet" if asset_type == "reference_sheet" else "portrait"
    filename = f"{character_id}_{slug}_{type_tag}_b{batch}p{proposal_number}_upload{file_ext}"
    local_path = os.path.join(STORAGE_DIR, filename)
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    asset = CharacterAsset(
        character_id=character_id,
        asset_type=asset_type,
        file_url=f"/static/assets/characters/{filename}",
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


# ======================================================================
# MODEL SHEET (planche de référence turnaround)
# ======================================================================

from app.agents.character_sheet import CharacterSheetAgent, AVAILABLE_SHEET_MODELS, DEFAULT_SHEET_MODEL


class GenerateSheetRequest(BaseModel):
    model: str = None  # un des AVAILABLE_SHEET_MODELS, sinon défaut


@router.post("/{character_id}/generate-sheet")
async def generate_character_sheet(character_id: int, request: GenerateSheetRequest, db: Session = Depends(get_db)):
    """Construit le Model Sheet à partir du portrait actuellement sélectionné
    pour ce personnage. Nécessite qu'un portrait soit déjà choisi."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    project = db.query(Project).filter(Project.id == character.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    selected_portrait = db.query(CharacterAsset).filter(
        CharacterAsset.character_id == character_id,
        CharacterAsset.asset_type == "portrait",
        CharacterAsset.is_selected == True,
        CharacterAsset.status == "completed"
    ).first()
    if not selected_portrait:
        raise HTTPException(status_code=400, detail="Select a portrait first before building the Model Sheet")

    # file_url est une URL relative (/static/assets/characters/...) : la
    # convertir en chemin disque réel (les fichiers vivent sous app/static/...).
    portrait_path = os.path.join("app", selected_portrait.file_url.lstrip("/"))
    if not os.path.isfile(portrait_path):
        raise HTTPException(status_code=500, detail=f"Portrait file not found on disk: {portrait_path}")

    last_batch = db.query(CharacterAsset).filter(
        CharacterAsset.character_id == character_id,
        CharacterAsset.asset_type == "reference_sheet"
    ).order_by(CharacterAsset.generation_batch.desc()).first()
    next_batch = (last_batch.generation_batch + 1) if last_batch else 1

    char_dict = {
        "id": character.id, "name": character.name, "role": character.role,
        "age": character.age, "visual_trait": character.visual_trait, "traits": character.traits,
    }
    agent = CharacterSheetAgent()
    result = agent.generate_sheet(
        char_dict, portrait_path, project.visual_styles or [], project.character_style_prompt,
        model=request.model, batch_number=next_batch
    )

    asset = CharacterAsset(
        character_id=character_id,
        asset_type="reference_sheet",
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
        db.query(CharacterAsset).filter(
            CharacterAsset.character_id == character_id,
            CharacterAsset.asset_type == "reference_sheet",
            CharacterAsset.generation_batch != next_batch
        ).update({"is_selected": False})
    db.commit()
    db.refresh(asset)

    if result["error"]:
        raise HTTPException(status_code=502, detail="Model Sheet generation failed. Try a different model.")

    return {
        "message": "Model Sheet generated",
        "batch": next_batch,
        "asset": {"id": asset.id, "url": asset.file_url, "model_used": asset.model_used},
    }