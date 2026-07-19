from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from jose import jwt, JWTError
from datetime import datetime

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.config import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/api/projects", tags=["projects"])

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Extract user from JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError as e:
        print(f"❌ JWT Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/", response_model=List[ProjectResponse])
async def get_projects(
    skip: int = 0,
    limit: int = 100,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupérer tous les projets de l'utilisateur"""
    print(f"\n{'='*60}")
    print(f"✅ FETCHING PROJECTS for user: {user.email}")
    projects = db.query(Project).filter(Project.owner_id == user.id).offset(skip).limit(limit).all()
    print(f"📦 Found {len(projects)} projects")
    for proj in projects:
        print(f"   - [{proj.id}] {proj.title} | Status: {proj.status} | Duration: {proj.duration_seconds}s")
    print(f"{'='*60}\n")
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupérer un projet spécifique"""
    print(f"\n{'='*60}")
    print(f"📥 GET PROJECT {project_id}")
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == user.id
    ).first()
    
    if not project:
        print(f"❌ Project {project_id} not found")
        raise HTTPException(status_code=404, detail="Project not found")
    
    print(f"✅ Project found: {project.title}")
    print(f"   Idea: {project.idea[:50] if project.idea else 'None'}...")
    print(f"   Duration: {project.duration_seconds}s")
    print(f"   Narrative Style: {project.narrative_style}")
    print(f"   Genres: {project.genres}")
    print(f"   Visual Styles: {project.visual_styles}")
    print(f"   Ref Image World: {project.reference_image_world}")
    print(f"   Ref Image Char: {project.reference_image_character}")
    print(f"   Extracted Style: {project.extracted_style_prompt[:50] if project.extracted_style_prompt else 'None'}...")
    print(f"{'='*60}\n")
    
    return project


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Créer un nouveau projet"""
    print(f"\n{'='*60}")
    print(f" CREATE PROJECT")
    print(f"   Title: {project.title}")
    print(f"   Type: {project.type}")
    print(f"   Data received: {project.dict()}")
    
    # Défaut intelligent : 16:9 pour Short Movie/Film, 9:16 pour Short Drama/Série,
    # sauf si l'utilisateur a explicitement choisi un format.
    aspect_ratio = project.aspect_ratio
    if not aspect_ratio:
        aspect_ratio = "9:16" if project.type in ("short_drama", "series") else "16:9"

    # Garde-fou (au cas où le frontend serait contourné) : un Short Drama/Série
    # a entre 2 et 5 épisodes (borne volontairement basse pour limiter le
    # risque pendant les tests du hackathon) ; un Short Movie/Film n'a pas de
    # notion d'épisode, on force 1.
    if project.type in ("short_drama", "series"):
        episodes_per_season = max(2, min(5, project.episodes_per_season or 2))
    else:
        episodes_per_season = 1

    db_project = Project(
        owner_id=user.id,
        title=project.title,
        idea=project.idea if hasattr(project, 'idea') else None,
        type=project.type,
        project_format=project.project_format or "one_shot",
        narrative_style=project.narrative_style if hasattr(project, 'narrative_style') else None,
        genres=project.genres,
        visual_styles=project.visual_styles,
        reference_image_world=project.reference_image_world if hasattr(project, 'reference_image_world') else None,
        reference_image_character=project.reference_image_character if hasattr(project, 'reference_image_character') else None,
        extracted_style_prompt=project.extracted_style_prompt if hasattr(project, 'extracted_style_prompt') else None,
        aspect_ratio=aspect_ratio,
        generation_progress={"status": "initialized"},
        seasons=project.seasons,
        episodes_per_season=episodes_per_season,
        duration_minutes=project.duration_minutes,
        duration_seconds=project.duration_seconds if hasattr(project, 'duration_seconds') else 60,
        synopsis=project.synopsis,
        status=project.status if hasattr(project, 'status') else "draft"
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    print(f"✅ Project created: {db_project.title} (ID: {db_project.id})")
    print(f"{'='*60}\n")
    return db_project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectCreate,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mettre à jour un projet existant"""
    print(f"\n{'='*60}")
    print(f"🔄 UPDATE PROJECT {project_id}")
    print(f"   Data received: {project_update.dict()}")
    
    # Vérifier que le projet existe et appartient à l'utilisateur
    db_project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == user.id
    ).first()
    
    if not db_project:
        print(f"❌ Project {project_id} not found")
        raise HTTPException(status_code=404, detail="Project not found")
    
    print(f"   Current values:")
    print(f"      - Title: {db_project.title}")
    print(f"      - Idea: {db_project.idea[:50] if db_project.idea else 'None'}...")
    print(f"      - Duration: {db_project.duration_seconds}s")
    
    # Mettre à jour TOUS les champs, pas seulement ceux qui sont set
    update_data = project_update.dict(exclude_unset=False)  # Changed to False

    # ⚠️ GARDE-FOU CRITIQUE : le formulaire de réglages (getFormData() côté
    # frontend) n'envoie JAMAIS le champ "synopsis" — avec exclude_unset=False,
    # Pydantic le remplit alors avec sa valeur par défaut (None), qui écraserait
    # silencieusement le synopsis à chaque sauvegarde silencieuse (avant chaque
    # Generate/Regenerate) si on ne l'exclut pas explicitement ici.
    PROTECTED_FIELDS = {"synopsis"}

    # Même garde-fou que pour la création.
    if update_data.get("type") in ("short_drama", "series"):
        update_data["episodes_per_season"] = max(2, min(5, update_data.get("episodes_per_season") or 2))
    else:
        update_data["episodes_per_season"] = 1

    print(f"   Updating with fields: {list(update_data.keys())}")

    for field, value in update_data.items():
        if field in PROTECTED_FIELDS:
            continue
        if hasattr(db_project, field):
            old_value = getattr(db_project, field)
            setattr(db_project, field, value)
            if old_value != value:
                print(f"   ✓ {field}: {old_value} → {value}")
    
    db_project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_project)
    
    print(f"✅ Project updated: {db_project.title}")
    print(f"   New values:")
    print(f"      - Idea: {db_project.idea[:50] if db_project.idea else 'None'}...")
    print(f"      - Duration: {db_project.duration_seconds}s")
    print(f"      - Ref World: {db_project.reference_image_world}")
    print(f"      - Ref Char: {db_project.reference_image_character}")
    print(f"{'='*60}\n")
    
    return db_project


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime définitivement un projet et tout ce qui lui est lié
    (personnages, épisodes, exécutions d'agents, assets) grâce aux relations
    cascade déjà déclarées sur le modèle Project."""
    db_project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == user.id
    ).first()

    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    title = db_project.title
    db.delete(db_project)
    db.commit()

    return {"message": f'Project "{title}" deleted successfully'}