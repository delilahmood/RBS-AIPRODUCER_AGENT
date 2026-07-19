from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.project import Project
from app.models.character import Character

class ContextService:
    @staticmethod
    def get_system_prompt(
        context_type: str,
        project_id: Optional[int] = None,
        db: Optional[Session] = None
    ) -> str:
        """Get context-specific system prompt"""
        if context_type == "dashboard":
            return ContextService._get_dashboard_prompt()
        elif context_type == "project" and project_id:
            return ContextService._get_project_prompt(project_id, db)
        elif context_type == "characters":
            return ContextService._get_characters_prompt(project_id, db)
        elif context_type == "scripts":
            return ContextService._get_scripts_prompt()
        else:
            return ContextService._get_default_prompt()
    
    @staticmethod
    def _get_dashboard_prompt() -> str:
        return """Tu es l'assistant de RBS AIProducer, un studio cinématographique alimenté par l'IA.
        Aide les créateurs à démarrer leurs projets. Sois encourageant et professionnel."""
    
    @staticmethod
    def _get_project_prompt(project_id: int, db: Optional[Session] = None) -> str:
        if not db:
            db = SessionLocal()
        
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return ContextService._get_default_prompt()
            
            genres = ', '.join(project.genres) if project.genres else 'Non défini'
            styles = ', '.join(project.visual_styles) if project.visual_styles else 'Non défini'
            
            return f"""Tu es l'assistant du projet "{project.title}".
            Type: {project.type}
            Genres: {genres}
            Style visuel: {styles}
            Synopsis: {project.synopsis or 'Non défini'}
            
            Reste fidèle à l'univers créé."""
        finally:
            if not db:
                db.close()
    
    @staticmethod
    def _get_characters_prompt(project_id: Optional[int], db: Optional[Session] = None) -> str:
        return """Tu es un expert en création de personnages pour séries et films.
        Crée des fiches personnages détaillées avec motivations, forces/faiblesses, et arcs narratifs."""
    
    @staticmethod
    def _get_scripts_prompt() -> str:
        return """Tu es un scénariste professionnel. Crée des scripts cinématographiques détaillés avec dialogues et indications de caméra."""
    
    @staticmethod
    def _get_default_prompt() -> str:
        return "Tu es un assistant IA créatif. Aide l'utilisateur dans ses projets."
    
    @staticmethod
    async def load_project_context(project_id: int) -> Dict[str, Any]:
        """Load full project context"""
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {}
            
            characters = db.query(Character).filter(Character.project_id == project_id).all()
            
            return {
                "project": project,
                "characters": characters,
                "genres": project.genres or [],
                "visual_styles": project.visual_styles or []
            }
        finally:
            db.close()