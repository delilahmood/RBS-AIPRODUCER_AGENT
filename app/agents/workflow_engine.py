from app.database import SessionLocal
from app.models.project import Project
from app.models.character import Character
from app.models.episode import Episode
from app.models.skill_execution import SkillExecution
from app.models.character_asset import CharacterAsset
from app.models.location import Location
from app.models.location_assets import LocationAsset
from app.models.scene import Scene
from app.models.scene_asset import SceneAsset
from app.agents.showrunner import ShowrunnerAgent
from app.agents.casting import CastingAgent
from app.agents.scriptwriter import ScriptwriterAgent
from app.agents.character_visualizer import CharacterVisualizerAgent
from app.agents.location_scout import LocationScoutAgent
from app.agents.location_visualizer import LocationDesignAgent
from app.agents.shot_breakdown import ShotBreakdownAgent
from app.agents.storyboard_art import StoryboardArtAgent
from datetime import datetime
import json
import os
import traceback


def _truncate(text, length=400):
    if not text:
        return text
    return text if len(text) <= length else text[:length] + "…"


class WorkflowEngine:
    def __init__(self):
        self.showrunner = ShowrunnerAgent()
        self.casting = CastingAgent()
        self.scriptwriter = ScriptwriterAgent()
        self.character_visualizer = CharacterVisualizerAgent()
        self.location_scout = LocationScoutAgent()
        self.location_design = LocationDesignAgent()
        self.shot_breakdown = ShotBreakdownAgent()
        self.storyboard_art = StoryboardArtAgent()
        self.logs = []

    # ------------------------------------------------------------------
    # Gestion d'une exécution de skill (une carte de la Timeline)
    # ------------------------------------------------------------------
    def _start_skill(self, db, project_id, skill_name):
        """Crée la ligne SkillExecution pour ce skill et la rend visible
        immédiatement en base (status='running')."""
        execution = SkillExecution(
            project_id=project_id,
            skill_name=skill_name,
            status="running",
            started_at=datetime.utcnow(),
            logs=json.dumps([]),
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    def _append_entry(self, db, execution, entry_type, message, extra=None):
        """Ajoute une entrée à la carte en cours et commit tout de suite,
        pour qu'un GET /generation-status concurrent la voie en direct."""
        entries = json.loads(execution.logs) if execution.logs else []
        entry = {
            "type": entry_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if extra:
            entry.update(extra)
        entries.append(entry)
        execution.logs = json.dumps(entries)
        db.add(execution)
        db.commit()

        # Garder aussi une trace dans self.logs (compat avec l'ancien retour)
        self._log(entry_type, message)

    def _finish_skill(self, db, execution, status, result_data=None):
        execution.status = status
        execution.finished_at = datetime.utcnow()
        if result_data is not None:
            execution.result_data = json.dumps(result_data, default=str)
        db.add(execution)
        db.commit()

    # ------------------------------------------------------------------
    # Pipeline principal
    # ------------------------------------------------------------------
    def run_pipeline(self, project_id: int, auto_approve: bool = False, workflow_steps: list = None):
        db = SessionLocal()
        self.logs = []

        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                self._log("error", "Project not found")
                return

            self._log("system", f"Starting pipeline for: {project.title}")
            duration = project.duration_seconds or 60

            # ============================================================
            # ÉTAPE 1 : SYNOPSIS (Showrunner)
            # ============================================================
            if not workflow_steps or "synopsis" in workflow_steps:
                execution = self._start_skill(db, project_id, "showrunner")
                self._append_entry(db, execution, "agent", "Showrunner Agent activated")

                idea = project.synopsis if project.synopsis else (project.idea or "Default idea")

                self._append_entry(
                    db, execution, "status",
                    "Preparing prompt for synopsis generation…"
                )

                synopsis_data = self.showrunner.generate_synopsis(
                    idea, duration, project.project_format,
                    genres=project.genres, narrative_style=project.narrative_style
                )

                router = self.showrunner.router
                self._append_entry(
                    db, execution, "prompt",
                    "Prompt sent to the model",
                    extra={
                        "system_prompt": _truncate(router.last_system_prompt, 800),
                        "user_prompt": router.last_user_prompt,
                        "model": router.last_model,
                    }
                )

                if synopsis_data:
                    project.synopsis = synopsis_data.get("synopsis", project.synopsis)
                    project.hook = synopsis_data.get("hook")
                    project.production_note = {"note": synopsis_data.get("production_note")}
                    db.commit()

                    self._append_entry(
                        db, execution, "success",
                        f"Synopsis generated in {router.last_duration_sec}s",
                        extra={
                            "duration_sec": router.last_duration_sec,
                            "tokens": router.last_tokens,
                        }
                    )
                    self._append_entry(db, execution, "info", f"Hook: {project.hook}")

                    self._finish_skill(db, execution, "completed", result_data={
                        "synopsis": project.synopsis,
                        "hook": project.hook,
                        "production_note": project.production_note,
                        "duration_sec": router.last_duration_sec,
                        "tokens": router.last_tokens,
                    })
                else:
                    self._append_entry(db, execution, "error", "Failed to generate synopsis")
                    self._finish_skill(db, execution, "failed")
                    return self.logs

            if not auto_approve:
                self._log("system", "Guided mode: Pausing for user validation")
                return self.logs

            # ============================================================
            # ÉTAPE 2 : PERSONNAGES (Casting)
            # ============================================================
            if not workflow_steps or "casting" in workflow_steps:
                if not project.synopsis or not project.synopsis.strip():
                    execution = self._start_skill(db, project_id, "casting")
                    self._append_entry(db, execution, "error",
                        "Cannot cast characters: the project synopsis is empty. "
                        "Generate or restore a synopsis first (see Showrunner card).")
                    self._finish_skill(db, execution, "failed")
                    return self.logs

                execution = self._start_skill(db, project_id, "casting")
                self._append_entry(db, execution, "agent", "Casting Agent activated")
                self._append_entry(db, execution, "status", "Preparing prompt for character casting…")

                characters_data = self.casting.generate_characters(project.synopsis, duration)
                router = self.casting.router

                self._append_entry(
                    db, execution, "prompt",
                    "Prompt sent to the model",
                    extra={
                        "system_prompt": _truncate(router.last_system_prompt, 800),
                        "user_prompt": _truncate(router.last_user_prompt, 800),
                        "model": router.last_model,
                    }
                )

                if characters_data:
                    chars = characters_data.get("characters", [])
                    created = []
                    for char_dict in chars:
                        new_char = Character(
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
                            has_secret=True if char_dict.get("secret") else False,
                            arc_potential=char_dict.get("arc_potential", ""),
                        )
                        db.add(new_char)
                        created.append(char_dict)
                        self._append_entry(db, execution, "info", f"Created character: {char_dict.get('name')} ({char_dict.get('role')})")
                    db.commit()

                    self._append_entry(
                        db, execution, "success",
                        f"{len(chars)} characters created in {router.last_duration_sec}s",
                        extra={"duration_sec": router.last_duration_sec, "tokens": router.last_tokens}
                    )

                    self._finish_skill(db, execution, "completed", result_data={
                        "characters": created,
                        "duration_sec": router.last_duration_sec,
                        "tokens": router.last_tokens,
                    })
                else:
                    self._append_entry(db, execution, "error", "Failed to generate characters")
                    self._finish_skill(db, execution, "failed")
                    return self.logs

            if not auto_approve:
                self._log("system", "Guided mode: Pausing for user validation")
                return self.logs

            # ============================================================
            # ÉTAPE 3 : SCRIPT (Scriptwriter) — tous les épisodes de la saison
            # ============================================================
            if not workflow_steps or "script" in workflow_steps:
                if not project.synopsis or not project.synopsis.strip():
                    execution = self._start_skill(db, project_id, "scriptwriter")
                    self._append_entry(db, execution, "error",
                        "Cannot write the script: the project synopsis is empty. "
                        "Generate or restore a synopsis first (see Showrunner card).")
                    self._finish_skill(db, execution, "failed")
                    return self.logs

                execution = self._start_skill(db, project_id, "scriptwriter")
                self._append_entry(db, execution, "agent", "Scriptwriter Agent activated")

                episode_count = project.episodes_per_season or 1
                is_serie = (project.project_format == "serie")
                self._append_entry(
                    db, execution, "status",
                    f"Preparing prompt for {episode_count} episode(s)…"
                )

                chars_list = [c.name + " (" + c.role + ")" for c in project.characters]
                script_data = self.scriptwriter.generate_episodes(
                    project.synopsis, project.hook or "", chars_list,
                    duration, episode_count, is_serie
                )
                router = self.scriptwriter.router

                self._append_entry(
                    db, execution, "prompt",
                    "Prompt sent to the model",
                    extra={
                        "system_prompt": _truncate(router.last_system_prompt, 800),
                        "user_prompt": _truncate(router.last_user_prompt, 800),
                        "model": router.last_model,
                    }
                )

                episodes = script_data.get("episodes") if script_data else None
                if episodes:
                    created = []
                    for ep_dict in episodes:
                        ep_num = ep_dict.get("episode_number") or (len(created) + 1)
                        new_ep = Episode(
                            project_id=project_id,
                            title=ep_dict.get("title", f"Episode {ep_num}"),
                            script_content=ep_dict.get("script_content", ""),
                            episode_number=ep_num,
                            season=1,
                            number=ep_num,
                            ends_with_cliffhanger=bool(ep_dict.get("ends_with_cliffhanger")),
                            cliffhanger_description=ep_dict.get("cliffhanger_description"),
                        )
                        db.add(new_ep)
                        created.append(ep_dict)
                        self._append_entry(db, execution, "info", f"Episode {ep_num}: {ep_dict.get('title')}")
                    db.commit()

                    self._append_entry(
                        db, execution, "success",
                        f"{len(episodes)} episode(s) generated in {router.last_duration_sec}s",
                        extra={"duration_sec": router.last_duration_sec, "tokens": router.last_tokens}
                    )

                    self._finish_skill(db, execution, "completed", result_data={
                        "episodes": created,
                        "duration_sec": router.last_duration_sec,
                        "tokens": router.last_tokens,
                    })
                else:
                    self._append_entry(db, execution, "error", "Failed to generate episodes")
                    self._finish_skill(db, execution, "failed")
                    return self.logs

            if not auto_approve:
                self._log("system", "Guided mode: Pausing for user validation")
                return self.logs

            # ============================================================
            # ÉTAPE 4 : IMAGES DE PERSONNAGES (Character Visualizer)
            # 2 propositions (style combiné) par personnage. L'historique des
            # lots précédents est préservé (jamais supprimé) ; la proposition
            # n°1 du nouveau lot est sélectionnée par défaut pour ne jamais
            # bloquer un "Generate All" automatique — l'utilisateur peut
            # ensuite choisir une autre proposition manuellement à tout moment.
            # Optionnelle : ne bloque jamais le reste du pipeline si elle échoue.
            # ============================================================
            if workflow_steps and "images" in workflow_steps:
                if not project.characters:
                    execution = self._start_skill(db, project_id, "character_visualizer")
                    self._append_entry(db, execution, "error",
                        "Cannot generate character images: no characters found. "
                        "Generate Casting first.")
                    self._finish_skill(db, execution, "failed")
                else:
                    execution = self._start_skill(db, project_id, "character_visualizer")
                    self._append_entry(db, execution, "agent", "Character Visualizer Agent activated")

                    visual_styles = project.visual_styles or []
                    style_label = " + ".join(visual_styles) if visual_styles else "default"
                    self._append_entry(
                        db, execution, "status",
                        f"Preparing image proposals for {len(project.characters)} character(s), combined style: {style_label}"
                    )

                    all_results = {}
                    total_ok, total_fail = 0, 0

                    for character in project.characters:
                        # Prochain numéro de lot pour CE personnage (préserve l'historique)
                        last_batch = db.query(CharacterAsset).filter(
                            CharacterAsset.character_id == character.id,
                            CharacterAsset.asset_type == "portrait"
                        ).order_by(CharacterAsset.generation_batch.desc()).first()
                        next_batch = (last_batch.generation_batch + 1) if last_batch else 1

                        char_dict = {
                            "id": character.id, "name": character.name, "role": character.role,
                            "age": character.age, "visual_trait": character.visual_trait,
                            "traits": character.traits,
                        }
                        proposals = self.character_visualizer.generate_proposals(
                            char_dict, visual_styles, project.character_style_prompt, batch_number=next_batch
                        )

                        char_assets = []
                        for p in proposals:
                            asset = CharacterAsset(
                                character_id=character.id,
                                asset_type="portrait",
                                file_url=p["url"] or "",
                                prompt_used=p["prompt_used"],
                                model_used=p["model_used"],
                                version=p["proposal_number"],
                                generation_batch=next_batch,
                                # Sélection auto de la 1ère proposition du nouveau lot,
                                # pour ne jamais bloquer un pipeline 100% automatique.
                                is_selected=(p["proposal_number"] == 1 and not p["error"]),
                                status="failed" if p["error"] else "completed",
                            )
                            db.add(asset)
                            char_assets.append(p)
                            if p["error"]:
                                total_fail += 1
                            else:
                                total_ok += 1

                        # Désélectionner les lots précédents : une seule image
                        # "choisie" à la fois pour ce personnage.
                        db.query(CharacterAsset).filter(
                            CharacterAsset.character_id == character.id,
                            CharacterAsset.asset_type == "portrait",
                            CharacterAsset.generation_batch != next_batch
                        ).update({"is_selected": False})
                        db.commit()

                        all_results[character.name] = char_assets
                        self._append_entry(
                            db, execution, "info",
                            f"{character.name}: {sum(1 for p in proposals if not p['error'])}/{len(proposals)} image(s) generated (batch {next_batch})"
                        )

                    status = "completed" if total_fail == 0 else ("completed" if total_ok > 0 else "failed")
                    self._append_entry(
                        db, execution, "success" if total_fail == 0 else "info",
                        f"{total_ok} image(s) generated, {total_fail} failed"
                    )
                    self._finish_skill(db, execution, status, result_data={"characters": all_results})

            # ============================================================
            # ÉTAPE 5 : LOCATION SCOUTING (texte) — extrait les lieux du script
            # ============================================================
            if workflow_steps and "location_scout" in workflow_steps:
                if not project.episodes:
                    execution = self._start_skill(db, project_id, "location_scout")
                    self._append_entry(db, execution, "error",
                        "Cannot scout locations: no script found. Generate Script first.")
                    self._finish_skill(db, execution, "failed")
                else:
                    execution = self._start_skill(db, project_id, "location_scout")
                    self._append_entry(db, execution, "agent", "Location Scout Agent activated")
                    self._append_entry(db, execution, "status", "Analyzing script for distinct locations…")

                    script_texts = [ep.script_content for ep in project.episodes if ep.script_content]
                    locations_data = self.location_scout.scout_locations(script_texts, project.synopsis or "")

                    router = self.location_scout.router
                    self._append_entry(
                        db, execution, "prompt", "Prompt sent to the model",
                        extra={
                            "system_prompt": _truncate(router.last_system_prompt, 800),
                            "user_prompt": _truncate(router.last_user_prompt, 800),
                            "model": router.last_model,
                        }
                    )

                    if locations_data:
                        locs = locations_data.get("locations", [])
                        created = []
                        for loc_dict in locs:
                            new_loc = Location(
                                project_id=project_id,
                                name=loc_dict.get("name", "Unknown"),
                                description=loc_dict.get("description", ""),
                                mood=loc_dict.get("mood", ""),
                                key_visual_details=loc_dict.get("key_visual_details", ""),
                            )
                            db.add(new_loc)
                            created.append(loc_dict)
                            self._append_entry(db, execution, "info", f"Location found: {loc_dict.get('name')}")
                        db.commit()

                        self._append_entry(
                            db, execution, "success",
                            f"{len(locs)} location(s) identified in {router.last_duration_sec}s",
                            extra={"duration_sec": router.last_duration_sec, "tokens": router.last_tokens}
                        )
                        self._finish_skill(db, execution, "completed", result_data={
                            "locations": created,
                            "duration_sec": router.last_duration_sec,
                            "tokens": router.last_tokens,
                        })
                    else:
                        self._append_entry(db, execution, "error", "Failed to scout locations")
                        self._finish_skill(db, execution, "failed")
                        return self.logs

            if not auto_approve:
                self._log("system", "Guided mode: Pausing for user validation")
                return self.logs

            # ============================================================
            # ÉTAPE 6 : LOCATION DESIGN (visuel) — 2 propositions par lieu
            # ============================================================
            if workflow_steps and "location_design" in workflow_steps:
                if not project.locations:
                    execution = self._start_skill(db, project_id, "location_design")
                    self._append_entry(db, execution, "error",
                        "Cannot generate location images: no locations found. "
                        "Run Location Scouting first.")
                    self._finish_skill(db, execution, "failed")
                else:
                    execution = self._start_skill(db, project_id, "location_design")
                    self._append_entry(db, execution, "agent", "Location Design Agent activated")

                    visual_styles = project.visual_styles or []
                    style_label = " + ".join(visual_styles) if visual_styles else "default"
                    self._append_entry(
                        db, execution, "status",
                        f"Preparing image proposals for {len(project.locations)} location(s), combined style: {style_label}"
                    )

                    all_results = {}
                    total_ok, total_fail = 0, 0
                    character_names = [c.name for c in project.characters]

                    for location in project.locations:
                        last_batch = db.query(LocationAsset).filter(
                            LocationAsset.location_id == location.id,
                            LocationAsset.asset_type == "reference"
                        ).order_by(LocationAsset.generation_batch.desc()).first()
                        next_batch = (last_batch.generation_batch + 1) if last_batch else 1

                        loc_dict = {
                            "id": location.id, "name": location.name, "description": location.description,
                            "mood": location.mood, "key_visual_details": location.key_visual_details,
                        }
                        proposals = self.location_design.generate_proposals(
                            loc_dict, visual_styles, project.world_style_prompt, batch_number=next_batch,
                            character_names=character_names
                        )

                        loc_assets = []
                        for p in proposals:
                            asset = LocationAsset(
                                location_id=location.id,
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
                            loc_assets.append(p)
                            if p["error"]:
                                total_fail += 1
                            else:
                                total_ok += 1

                        db.query(LocationAsset).filter(
                            LocationAsset.location_id == location.id,
                            LocationAsset.asset_type == "reference",
                            LocationAsset.generation_batch != next_batch
                        ).update({"is_selected": False})
                        db.commit()

                        all_results[location.name] = loc_assets
                        self._append_entry(
                            db, execution, "info",
                            f"{location.name}: {sum(1 for p in proposals if not p['error'])}/{len(proposals)} image(s) generated (batch {next_batch})"
                        )

                    status = "completed" if total_fail == 0 else ("completed" if total_ok > 0 else "failed")
                    self._append_entry(
                        db, execution, "success" if total_fail == 0 else "info",
                        f"{total_ok} image(s) generated, {total_fail} failed"
                    )
                    self._finish_skill(db, execution, status, result_data={"locations": all_results})

            if not auto_approve:
                self._log("system", "Guided mode: Pausing for user validation")
                return self.logs

            # ============================================================
            # ÉTAPE 7 : SHOT BREAKDOWN (texte) — découpe le script en plans
            # ============================================================
            if workflow_steps and "shot_breakdown" in workflow_steps:
                if not project.episodes:
                    execution = self._start_skill(db, project_id, "shot_breakdown")
                    self._append_entry(db, execution, "error",
                        "Cannot break down shots: no script found. Generate Script first.")
                    self._finish_skill(db, execution, "failed")
                else:
                    execution = self._start_skill(db, project_id, "shot_breakdown")
                    self._append_entry(db, execution, "agent", "Shot Breakdown Agent activated")

                    char_refs = [{"id": c.id, "name": c.name, "role": c.role} for c in project.characters]
                    loc_refs = [{"id": l.id, "name": l.name} for l in project.locations]
                    valid_char_ids = {c["id"] for c in char_refs}
                    valid_loc_ids = {l["id"] for l in loc_refs}
                    is_serie = (project.project_format == "serie")

                    # Nettoyer les anciens plans avant de redécouper (évite les doublons)
                    for ep in project.episodes:
                        db.query(Scene).filter(Scene.episode_id == ep.id).delete()
                    db.commit()

                    total_shots = 0
                    global_shot_number = 0  # continu sur toute la saison, ne repart jamais à 1
                    episodes_sorted = sorted(project.episodes, key=lambda e: e.episode_number or 0)
                    for idx, episode in enumerate(episodes_sorted):
                        is_last_episode = (idx == len(episodes_sorted) - 1)
                        self._append_entry(db, execution, "status", f"Breaking down episode: {episode.title}…")

                        breakdown = self.shot_breakdown.break_down_episode(
                            episode.script_content, episode.title, char_refs, loc_refs, is_last_episode, is_serie
                        )
                        router = self.shot_breakdown.router
                        self._append_entry(
                            db, execution, "prompt", "Prompt sent to the model",
                            extra={
                                "system_prompt": _truncate(router.last_system_prompt, 600),
                                "user_prompt": _truncate(router.last_user_prompt, 600),
                                "model": router.last_model,
                            }
                        )

                        if not breakdown:
                            self._append_entry(db, execution, "error", f"Failed to break down {episode.title}")
                            continue

                        shots = breakdown.get("shots", [])
                        for shot in shots:
                            char_ids = [cid for cid in (shot.get("character_ids") or []) if cid in valid_char_ids]
                            loc_id = shot.get("location_id")
                            if loc_id not in valid_loc_ids:
                                loc_id = None

                            global_shot_number += 1
                            db.add(Scene(
                                episode_id=episode.id,
                                location_id=loc_id,
                                character_ids=char_ids,
                                number=global_shot_number,
                                description=shot.get("description", ""),
                                camera_movement=shot.get("camera_movement", ""),
                                mood=shot.get("mood", ""),
                                dialogue=shot.get("dialogue"),
                                duration_seconds=min(shot.get("duration_seconds", 10.0) or 10.0, self.shot_breakdown.MAX_SHOT_DURATION),
                                is_cliffhanger=bool(shot.get("is_cliffhanger")),
                                cliffhanger_description=shot.get("cliffhanger_description"),
                                status="draft",
                            ))
                        db.commit()
                        total_shots += len(shots)
                        self._append_entry(db, execution, "info", f"{episode.title}: {len(shots)} shot(s) identified")

                    self._append_entry(db, execution, "success", f"{total_shots} shot(s) identified across {len(episodes_sorted)} episode(s)")
                    self._finish_skill(db, execution, "completed", result_data={"total_shots": total_shots})

            if not auto_approve:
                self._log("system", "Guided mode: Pausing for user validation")
                return self.logs

            # ============================================================
            # ÉTAPE 8 : STORYBOARD ART (visuel) — 1 image par plan, combine
            # les références personnages + décor déjà sélectionnées
            # ============================================================
            if workflow_steps and "storyboard_art" in workflow_steps:
                all_scenes = [s for ep in project.episodes for s in ep.scenes]
                if not all_scenes:
                    execution = self._start_skill(db, project_id, "storyboard_art")
                    self._append_entry(db, execution, "error",
                        "Cannot generate storyboards: no shots found. Run Shot Breakdown first.")
                    self._finish_skill(db, execution, "failed")
                else:
                    execution = self._start_skill(db, project_id, "storyboard_art")
                    self._append_entry(db, execution, "agent", "Storyboard Art Agent activated")
                    self._append_entry(db, execution, "status", f"Preparing {len(all_scenes)} storyboard frame(s)…")

                    visual_styles = project.visual_styles or []
                    total_ok, total_fail = 0, 0

                    for scene in all_scenes:
                        ref_paths = []
                        character_names = []
                        structured_characters = []
                        for cid in (scene.character_ids or []):
                            char = db.query(Character).filter(Character.id == cid).first()
                            if char:
                                character_names.append(char.name)
                            char_entry = {"name": char.name if char else "Character", "closeup_path": None, "fullbody_path": None}
                            # Closeup (portrait) ET fullbody (Model Sheet) — le
                            # fullbody porte l'info vêtements/silhouette absente du closeup.
                            for asset_type, key in (("portrait", "closeup_path"), ("reference_sheet", "fullbody_path")):
                                asset = db.query(CharacterAsset).filter(
                                    CharacterAsset.character_id == cid,
                                    CharacterAsset.asset_type == asset_type,
                                    CharacterAsset.is_selected == True
                                ).first()
                                if asset and asset.file_url:
                                    path = os.path.join("app", asset.file_url.lstrip("/"))
                                    ref_paths.append(path)
                                    char_entry[key] = path
                            structured_characters.append(char_entry)
                        structured_location = None
                        if scene.location_id:
                            location_obj = db.query(Location).filter(Location.id == scene.location_id).first()
                            loc_asset = db.query(LocationAsset).filter(
                                LocationAsset.location_id == scene.location_id,
                                LocationAsset.asset_type == "reference",
                                LocationAsset.is_selected == True
                            ).first()
                            if loc_asset and loc_asset.file_url:
                                path = os.path.join("app", loc_asset.file_url.lstrip("/"))
                                ref_paths.append(path)
                                structured_location = {"name": location_obj.name if location_obj else "Location", "path": path}
                        ref_paths = [p for p in ref_paths if os.path.isfile(p)]

                        last_batch = db.query(SceneAsset).filter(
                            SceneAsset.scene_id == scene.id, SceneAsset.asset_type == "storyboard"
                        ).order_by(SceneAsset.generation_batch.desc()).first()
                        next_batch = (last_batch.generation_batch + 1) if last_batch else 1

                        # Plans voisins (même épisode) pour la continuité narrative
                        prev_scene = db.query(Scene).filter(
                            Scene.episode_id == scene.episode_id, Scene.number == scene.number - 1
                        ).first()
                        next_scene_obj = db.query(Scene).filter(
                            Scene.episode_id == scene.episode_id, Scene.number == scene.number + 1
                        ).first()
                        previous_shot = {"description": prev_scene.description} if prev_scene else None
                        next_shot = {"description": next_scene_obj.description} if next_scene_obj else None

                        # Planche précédente (référence d'état), uniquement si générée
                        # en grille (voir storyboard_art.py pour la logique complète).
                        previous_storyboard_path = None
                        if prev_scene:
                            prev_sb_asset = db.query(SceneAsset).filter(
                                SceneAsset.scene_id == prev_scene.id, SceneAsset.asset_type == "storyboard",
                                SceneAsset.is_selected == True
                            ).first()
                            if prev_sb_asset and prev_sb_asset.file_url and prev_sb_asset.prompt_used and "BEATS:" in prev_sb_asset.prompt_used:
                                candidate = os.path.join("app", prev_sb_asset.file_url.lstrip("/"))
                                if os.path.isfile(candidate):
                                    previous_storyboard_path = candidate

                        shot_dict = {
                            "id": scene.id, "description": scene.description,
                            "camera_movement": scene.camera_movement, "mood": scene.mood,
                            "dialogue": scene.dialogue, "duration_seconds": scene.duration_seconds,
                            "is_cliffhanger": scene.is_cliffhanger,
                        }
                        # Défaut du pipeline groupé : qwen-image-2.0-pro, mode Auto,
                        # Prompt Director activé — le meilleur combo confirmé par
                        # les tests, explicitement fixé plutôt que de dépendre des
                        # valeurs par défaut de la fonction (qui restent pensées
                        # pour la génération individuelle, plus prudente par défaut).
                        result = self.storyboard_art.generate_storyboard_frame(
                            shot_dict, ref_paths, visual_styles, model="qwen-image-2.0-pro",
                            batch_number=next_batch, mode="auto", character_names=character_names,
                            previous_shot=previous_shot, next_shot=next_shot,
                            structured_characters=structured_characters, structured_location=structured_location,
                            use_prompt_director=True, previous_storyboard_path=previous_storyboard_path
                        )

                        db.add(SceneAsset(
                            scene_id=scene.id,
                            asset_type="storyboard",
                            file_url=result["url"] or "",
                            prompt_used=result["prompt_used"],
                            model_used=result["model_used"],
                            version=1,
                            generation_batch=next_batch,
                            is_selected=(not result["error"]),
                            status="failed" if result["error"] else "completed",
                        ))
                        if not result["error"]:
                            db.query(SceneAsset).filter(
                                SceneAsset.scene_id == scene.id, SceneAsset.asset_type == "storyboard",
                                SceneAsset.generation_batch != next_batch
                            ).update({"is_selected": False})
                            total_ok += 1
                        else:
                            total_fail += 1
                        db.commit()

                    self._append_entry(
                        db, execution, "success" if total_fail == 0 else "info",
                        f"{total_ok} storyboard frame(s) generated, {total_fail} failed"
                    )
                    self._finish_skill(db, execution, "completed" if total_ok > 0 else "failed",
                                        result_data={"total_ok": total_ok, "total_fail": total_fail})

            self._log("success", "Pipeline completed successfully!")
            project.status = "ready"
            db.commit()

        except Exception as e:
            self._log("error", f"Workflow error: {str(e)}")
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()

        return self.logs

    def _log(self, type: str, message: str):
        """Ajoute un log au run courant (compat avec la réponse HTTP synchrone)."""
        self.logs.append({
            "type": type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        print(f"[{type.upper()}] {message}")
