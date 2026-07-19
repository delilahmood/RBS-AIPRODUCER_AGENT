from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ProjectBase(BaseModel):
    title: str
    type: str
    project_format: Optional[str] = "one_shot"       # ✅ AJOUTÉ ("one_shot" ou "serie")
    idea: Optional[str] = None                      # ✅ AJOUTÉ (vient de l'interface)
    narrative_style: Optional[str] = None           # ✅ AJOUTÉ (vient de l'interface)
    genres: Optional[List[str]] = Field(default_factory=list, max_length=3)
    visual_styles: Optional[List[str]] = Field(default_factory=list)
    reference_image_world: Optional[str] = None     # ✅ AJOUTÉ (URL de l'image monde)
    reference_image_character: Optional[str] = None # ✅ AJOUTÉ (URL de l'image perso)
    extracted_style_prompt: Optional[str] = None    # ✅ AJOUTÉ (Prompt extrait) — conservé pour compat
    world_style_prompt: Optional[str] = None         # ✅ AJOUTÉ (style extrait de l'image World)
    character_style_prompt: Optional[str] = None     # ✅ AJOUTÉ (style extrait de l'image Character)
    seasons: Optional[int] = None
    episodes_per_season: Optional[int] = None
    duration_minutes: Optional[int] = None
    duration_seconds: Optional[int] = 60            # ✅ AJOUTÉ (C'est celui de ton interface gen-duration)
    aspect_ratio: Optional[str] = None               # ✅ AJOUTÉ ("16:9" ou "9:16")
    episodes_per_season: Optional[int] = None        # ✅ AJOUTÉ (nombre d'épisodes pour Short Drama)
    synopsis: Optional[str] = None
    status: Optional[str] = "draft"

class ProjectCreate(ProjectBase):
    pass # Hérite de tous les champs ci-dessus

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    idea: Optional[str] = None
    type: Optional[str] = None
    project_format: Optional[str] = None
    narrative_style: Optional[str] = None
    genres: Optional[List[str]] = None
    visual_styles: Optional[List[str]] = None
    reference_image_world: Optional[str] = None
    reference_image_character: Optional[str] = None
    extracted_style_prompt: Optional[str] = None
    world_style_prompt: Optional[str] = None
    character_style_prompt: Optional[str] = None
    seasons: Optional[int] = None
    episodes_per_season: Optional[int] = None
    duration_minutes: Optional[int] = None
    duration_seconds: Optional[int] = None
    aspect_ratio: Optional[str] = None
    synopsis: Optional[str] = None
    status: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: int
    owner_id: int
    aspect_ratio: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True