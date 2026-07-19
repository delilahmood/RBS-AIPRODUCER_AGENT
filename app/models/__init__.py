from app.models.user import User
from app.models.project import Project
from app.models.character import Character, CharacterRelation
from app.models.episode import Episode
from app.models.scene import Scene
from app.models.memory import ProjectMemory, ChatSession

#NOUVEAUX MODÈLES À AJOUTER ICI
from app.models.project_asset import ProjectAsset
from app.models.character_asset import CharacterAsset
from app.models.scene_asset import SceneAsset
from app.models.skill_execution import SkillExecution
from app.models.location import Location
from app.models.location_assets import LocationAsset

__all__ = [
    "User", "Project", "Character", "CharacterRelation", 
    "Episode", "Scene", "ProjectMemory", "ChatSession",
    "CharacterAsset", "ProjectAsset", "SceneAsset", "SkillExecution",
    "Location", "LocationAsset"
]
