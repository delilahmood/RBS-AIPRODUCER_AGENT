from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class CharacterBase(BaseModel):
    name: str
    alias: Optional[str] = None
    role: str  # protagonist, antagonist, supporting
    age: Optional[int] = None
    description: Optional[str] = None
    traits: Optional[List[str]] = None
    reference_images: Optional[List[str]] = None
    is_agent: bool = False

class CharacterCreate(CharacterBase):
    project_id: int

class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    alias: Optional[str] = None
    role: Optional[str] = None
    age: Optional[int] = None
    description: Optional[str] = None
    traits: Optional[List[str]] = None
    reference_images: Optional[List[str]] = None
    is_agent: Optional[bool] = None
    objective: Optional[str] = None
    visual_trait: Optional[str] = None
    secret: Optional[str] = None
    arc_potential: Optional[str] = None

class CharacterRelationCreate(BaseModel):
    related_character_id: int
    relation_type: str  # romantic_allies, mortal_enemies, mentor, etc.
    description: Optional[str] = None

# ✅ NOUVEAU : Schema pour la réponse CharacterRelation
class CharacterRelationResponse(BaseModel):
    id: int
    character_id: int
    related_character_id: int
    relation_type: str
    description: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class CharacterResponse(CharacterBase):
    id: int
    project_id: int
    agent_public_url: Optional[str] = None
    objective: Optional[str] = None
    visual_trait: Optional[str] = None
    secret: Optional[str] = None
    has_secret: Optional[bool] = None
    arc_potential: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True