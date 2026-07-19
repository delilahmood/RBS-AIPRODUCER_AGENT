// ===== GLOBAL VARIABLES =====
window.selectedProjectType = 'short_drama';
window.uploadedImages = {
    world: null,
    character: null
};

// ===== GENERATOR LOGIC =====
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Generator initialized');
    
    // Récupérer l'ID du projet depuis l'URL
    const pathParts = window.location.pathname.split('/');
    const projectId = pathParts[pathParts.length - 1];
    const isNewProject = projectId === 'new';
    console.log(`📍 Project ID: ${projectId}, Is New: ${isNewProject}`);

    // ⚠️ Bug corrigé : cette variable ne doit JAMAIS être figée dans une
    // closure de bouton — après la toute première création réussie, elle
    // doit repasser à false, sinon chaque clic ultérieur sur Save/Generate
    // continue de croire qu'il doit CRÉER un nouveau projet (POST) au lieu
    // de mettre à jour l'existant (PUT), dupliquant le projet à chaque clic.
    window._genIsNew = isNewProject;
    
    // Éléments du DOM
    const btnCreate = document.getElementById('btn-run-generation');
    const btnSave = document.getElementById('btn-save-params');
    
    // Gestion des Chips
    setupChips('.genre-chip', 'genres');
    setupChips('.visual-chip', 'visual_styles');
    setupChips('.narrative-chip', 'narrative_style', true);

    // Initialiser l'état dynamique du formulaire (afficher/masquer Episodes,
    // libellé de durée, etc.) selon le type par défaut — nécessaire même pour
    // un NOUVEAU projet, sinon la ligne "Episodes" reste cachée puisque
    // "Short Drama" n'est actif que visuellement (classe HTML statique) sans
    // que la logique JS associée n'ait jamais été déclenchée.
    selectProjectType(window.selectedProjectType);

    // Charger les données si projet existant
    if (!isNewProject && projectId) {
        loadProjectData(projectId);
        // Restaurer la Production Timeline depuis la base (persistance au reload)
        refreshTimelineFromServer(projectId);
    }
    
    // Event Listeners
    if (btnCreate) {
        btnCreate.addEventListener('click', () => handleGenerate(getCurrentProjectId(), window._genIsNew));
    }
    if (btnSave) {
        btnSave.addEventListener('click', () => handleSave(getCurrentProjectId(), window._genIsNew));
    }
});

// ===== GESTION DES CHIPS =====
function setupChips(selector, stateKey, isSingle = false) {
    const chips = document.querySelectorAll(selector);
    chips.forEach(chip => {
        chip.addEventListener('click', function() {
            if (isSingle) {
                document.querySelectorAll(selector).forEach(c => {
                    c.classList.remove('bg-purple-600', 'border-purple-500', 'text-white');
                    c.classList.add('bg-slate-800', 'border-slate-700', 'text-slate-300');
                });
                this.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-300');
                this.classList.add('bg-purple-600', 'border-purple-500', 'text-white');
            } else {
                if (this.classList.contains('bg-purple-600')) {
                    this.classList.remove('bg-purple-600', 'border-purple-500', 'text-white');
                    this.classList.add('bg-slate-800', 'border-slate-700', 'text-slate-300');
                } else {
                    if (stateKey === 'genres') {
                        const selected = document.querySelectorAll(`${selector}.bg-purple-600`);
                        if (selected.length >= 3) {
                            alert('Maximum 3 genres allowed');
                            return;
                        }
                    }
                    this.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-300');
                    this.classList.add('bg-purple-600', 'border-purple-500', 'text-white');
                }
            }
        });
    });
}

// ===== SÉLECTION DU TYPE DE PROJET (comportements dynamiques) =====
function selectProjectType(type) {
    window.selectedProjectType = type;

    // Mettre à jour l'état visuel des boutons
    document.querySelectorAll('.type-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.type === type);
    });

    const isEpisodic = (type === 'short_drama' || type === 'series');

    // Season/Episodes : uniquement pertinent pour un contenu épisodique
    const seasonRow = document.getElementById('gen-season-row');
    if (seasonRow) seasonRow.style.display = isEpisodic ? 'grid' : 'none';

    // Case "suite prévue" : idem
    const serieRow = document.getElementById('gen-serie-row');
    if (serieRow) serieRow.style.display = isEpisodic ? 'block' : 'none';

    // Libellé de durée : "par épisode" seulement si plusieurs épisodes possibles
    const durationLabel = document.getElementById('gen-duration-label');
    if (durationLabel) {
        durationLabel.textContent = isEpisodic ? 'Duration per Episode (seconds)' : 'Duration (seconds)';
    }

    // Format vidéo par défaut : 9:16 pour Short Drama/Series, 16:9 pour Short Movie —
    // mais on ne touche plus au select si l'utilisateur l'a déjà changé à la main.
    const aspectSelect = document.getElementById('gen-aspect-ratio');
    if (aspectSelect && !window.aspectRatioManuallySet) {
        aspectSelect.value = isEpisodic ? '9:16' : '16:9';
    }
}

// L'utilisateur a changé le format vidéo lui-même : on ne l'écrase plus automatiquement
document.addEventListener('DOMContentLoaded', () => {
    const aspectSelect = document.getElementById('gen-aspect-ratio');
    if (aspectSelect) {
        aspectSelect.addEventListener('change', () => { window.aspectRatioManuallySet = true; });
    }
});

// Cases "Generation Steps" : ajouter/retirer la carte Ready/Queued correspondante
// à la volée, et avertir avant de décocher une étape déjà générée (rien n'est
// jamais supprimé — juste exclu des prochaines exécutions de "Generate All").
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.workflow-step').forEach(cb => {
        cb.addEventListener('change', (e) => {
            const step = e.target.dataset.step;

            // Cas spécial : Scene Generator coûte de vrais crédits par vidéo
            // générée — un message informatif s'affiche à la coche, pas de
            // conséquence fonctionnelle sur "Generate All" (cette étape n'est
            // de toute façon jamais lancée en groupe, uniquement plan par plan).
            if (step === 'scene_generator' && e.target.checked) {
                const storyboardDone = lastGenerationData?.generations?.['storyboard_art']?.status === 'completed';
                const proceed = confirm(
                    `Heads up: Scene Generator creates real video clips, which cost real API credits per shot.\n\n` +
                    (storyboardDone
                        ? `Your storyboards are ready — you can safely generate videos shot by shot using the dedicated card below.`
                        : `We recommend leaving this OUT of "Generate All" until Storyboard Art is finished. Generate videos one shot at a time instead, once storyboards are ready, to avoid spending credits on shots that aren't ready yet.`) +
                    `\n\nKeep this box checked anyway?`
                );
                if (!proceed) {
                    e.target.checked = false;
                    return;
                }
            }

            const skillKey = STEP_TO_SKILL[step];
            const gen = lastGenerationData?.generations?.[skillKey];

            if (!e.target.checked && gen?.status === 'completed') {
                const agentLabel = AGENT_PIPELINE.find(a => a.key === skillKey)?.label || step;
                const confirmed = confirm(
                    `${agentLabel} has already generated content.\n\n` +
                    `Unchecking it won't delete anything — it will just be excluded from future "Generate All" runs. You can re-check it anytime.\n\n` +
                    `Continue?`
                );
                if (!confirmed) {
                    e.target.checked = true; // annuler le décochage
                    return;
                }
            }
            if (lastGenerationData) renderTimeline(lastGenerationData);
        });
    });
});

// ===== RÉCUPÉRER LES DONNÉES DU FORMULAIRE =====
function getFormData() {
    const getSelectedValues = (selector) => {
        return Array.from(document.querySelectorAll(`${selector}.bg-purple-600`))
            .map(el => el.dataset.value);
    };
    
    const data = {
        title: document.getElementById('gen-title').value,
        idea: document.getElementById('gen-idea').value,
        type: window.selectedProjectType || 'short_drama',  // ✅ Utiliser la variable globale
        project_format: document.getElementById('gen-project-format')?.checked ? 'serie' : 'one_shot',
        seasons: parseInt(document.getElementById('gen-season').value) || 1,
        episodes_per_season: parseInt(document.getElementById('gen-episodes')?.value) || 1,
        duration_seconds: parseInt(document.getElementById('gen-duration').value) || 60,
        aspect_ratio: document.getElementById('gen-aspect-ratio')?.value || '16:9',
        narrative_style: document.querySelector('.narrative-chip.bg-purple-600')?.dataset.value || null,
        genres: getSelectedValues('.genre-chip'),
        visual_styles: getSelectedValues('.visual-chip'),
        workflow_steps: Array.from(document.querySelectorAll('.workflow-step:checked')).map(cb => cb.dataset.step),
        reference_image_world: window.uploadedImages.world || null,
        reference_image_character: window.uploadedImages.character || null,
        extracted_style_prompt: null,
        world_style_prompt: document.getElementById('gen-world-style')?.value || null,
        character_style_prompt: document.getElementById('gen-character-style')?.value || null
    };
    
    console.log('📦 getFormData() called');
    console.log('   Type:', data.type);
    console.log('   Seasons:', data.seasons);
    console.log('   Duration:', data.duration_seconds);
    console.log('   Images:', window.uploadedImages);
    console.log('   Data:', JSON.stringify(data, null, 2));
    
    return data;
}

// ===== SAUVEGARDER LE PROJET =====
// Sauvegarde silencieuse des réglages actuels du formulaire (pas d'alert),
// réutilisée avant tout Generate/Regenerate pour être sûr que le backend
// travaille toujours avec les valeurs affichées à l'écran, même si
// l'utilisateur n'a pas cliqué explicitement sur "Save" avant.
async function saveProjectSettingsSilently(projectId) {
    const data = getFormData();
    const token = localStorage.getItem('access_token');
    const response = await fetch(`/api/projects/${projectId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ ...data, status: 'draft' })
    });
    if (!response.ok) throw new Error('Failed to save project settings');
    return await response.json();
}

async function handleSave(projectId, isNew) {
    console.log('\n💾 handleSave() called');
    const data = getFormData();
    
    if (!data.title) { 
        alert('Title is required'); 
        return; 
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const url = isNew ? '/api/projects/' : `/api/projects/${projectId}`;
        const method = isNew ? 'POST' : 'PUT';
        
        console.log(`   ${method} ${url}`);
        console.log('   Payload:', JSON.stringify(data, null, 2));
        
        const response = await fetch(url, {
            method: method,
            headers: { 
                'Content-Type': 'application/json', 
                'Authorization': `Bearer ${token}` 
            },
            body: JSON.stringify({ ...data, status: 'draft' })
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('   ✅ Save successful:', result);
            
            if (isNew) {
                window.history.pushState({}, '', `/generator/${result.id}`);
                window._genIsNew = false; // le prochain clic doit mettre à jour, plus jamais créer
                alert('Project created! You can now run generation.');
            } else {
                alert('Parameters saved!');
            }
        } else {
            const error = await response.json();
            console.error('   ❌ Save failed:', error);
            alert('Error saving project: ' + (error.detail || 'Unknown error'));
        }
    } catch (e) { 
        console.error('   ❌ Exception:', e);
        alert('Error: ' + e.message); 
    }
}

// ===== EXPORT (PDF / Markdown), par section ou global =====
function toggleExportMenu(event) {
    event.stopPropagation();
    const menu = document.getElementById('export-menu');
    if (!menu) return;
    const isOpen = menu.classList.contains('open');
    document.querySelectorAll('.export-menu.open').forEach(m => m.classList.remove('open'));
    if (!isOpen) menu.classList.add('open');
}
document.addEventListener('click', () => {
    document.querySelectorAll('.export-menu.open').forEach(m => m.classList.remove('open'));
});

async function downloadExport(section, format) {
    const projectId = getCurrentProjectId();
    const token = localStorage.getItem('access_token');
    const endpoint = format === 'pdf' ? 'pdf' : 'markdown';

    try {
        const response = await fetch(`/api/projects/${projectId}/export/${endpoint}?section=${section}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Export failed');

        const blob = await response.blob();
        const disposition = response.headers.get('Content-Disposition') || '';
        const match = disposition.match(/filename="?([^"]+)"?/);
        const filename = match ? match[1] : `export.${format === 'pdf' ? 'pdf' : 'md'}`;

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (e) {
        console.error('   ❌ Export error:', e);
        alert('Export failed.');
    }
}

// ===== LANCER LA GÉNÉRATION =====
async function handleGenerate(projectId, isNew) {
    console.log('\n🚀 handleGenerate() called');
    let currentId = projectId;
    
    if (isNew) {
        const data = getFormData();
        if (!data.title || !data.idea) { 
            alert('Title and Idea are required'); 
            return; 
        }
        
        console.log('   Creating new project...');
        const token = localStorage.getItem('access_token');
        const createRes = await fetch('/api/projects/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json', 
                'Authorization': `Bearer ${token}` 
            },
            body: JSON.stringify({ ...data, status: 'generating' })
        });
        
        if (!createRes.ok) { 
            alert('Failed to create project'); 
            return; 
        }
        
        const newProject = await createRes.json();
        currentId = newProject.id;
        window.history.pushState({}, '', `/generator/${currentId}`);
        window._genIsNew = false; // le prochain clic doit régénérer sur CE projet, plus jamais en créer un autre
        document.getElementById('header-project-title').textContent = newProject.title;
        console.log('   ✅ Project created:', newProject.id);
    } else {
        // Projet existant : s'assurer que le backend utilise bien les réglages
        // actuellement affichés (episodes, durée, genres...), même si
        // l'utilisateur n'a pas cliqué sur "Save" avant de cliquer "Generate".
        try {
            await saveProjectSettingsSilently(currentId);
        } catch (e) {
            console.error('   ❌ Failed to sync settings before generate:', e);
            alert('Failed to save current settings before generating.');
            return;
        }
    }
    
    // Lancer la génération (le backend répond immédiatement, la Timeline
    // se construit ensuite via polling de /generation-status)
    console.log('   Starting generation pipeline...');
    clearTimelineEmptyState();

    const workflowSteps = Array.from(document.querySelectorAll('.workflow-step:checked'))
        .map(cb => cb.dataset.step)
        .filter(step => ['synopsis', 'casting', 'script', 'images', 'location_scout', 'location_design', 'shot_breakdown', 'storyboard_art'].includes(step)); // agents implémentés

    // "Generate All" doit prévenir avant d'écraser du contenu déjà généré —
    // aucune régénération silencieuse et coûteuse en crédits API.
    if (!isNew && lastGenerationData) {
        const alreadyDone = AGENT_PIPELINE.filter(a => {
            const step = SKILL_TO_STEP[a.key];
            return workflowSteps.includes(step) && lastGenerationData.generations?.[a.key]?.status === 'completed';
        });
        if (alreadyDone.length > 0) {
            const proceed = await _showGenerateAllReportModal(alreadyDone);
            if (!proceed) return;
        }
    }

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/projects/${currentId}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                workflow_steps: workflowSteps.length ? workflowSteps : ['synopsis', 'casting', 'script'],
                auto_approve: true
            })
        });

        if (!response.ok) throw new Error('Failed to start generation');

        setHeaderStatus('Generating', 'status-running');
        startPollingGenerationStatus(currentId);

    } catch (e) {
        console.error('   ❌ Generation error:', e);
        setHeaderStatus('Error', 'status-failed');
    }
}

// ===== TIMELINE : ORDRE ET MÉTADONNÉES DES AGENTS =====
const AGENT_PIPELINE = [
    { key: 'showrunner', label: 'Showrunner Agent', icon: 'fa-feather-pointed' },
    { key: 'casting', label: 'Casting Agent', icon: 'fa-users' },
    { key: 'scriptwriter', label: 'Scriptwriter Agent', icon: 'fa-pen-nib' },
    { key: 'character_visualizer', label: 'Character Visualizer', icon: 'fa-image' },
    { key: 'location_scout', label: 'Location Scout Agent', icon: 'fa-map-location-dot' },
    { key: 'location_design', label: 'Location Design Agent', icon: 'fa-mountain-sun' },
    { key: 'shot_breakdown', label: 'Shot Breakdown Agent', icon: 'fa-clapperboard' },
    { key: 'storyboard_art', label: 'Storyboard Art Agent', icon: 'fa-film' },
];
const SKILL_TO_STEP = {
    showrunner: 'synopsis', casting: 'casting', scriptwriter: 'script',
    character_visualizer: 'images', location_scout: 'location_scout', location_design: 'location_design',
    shot_breakdown: 'shot_breakdown', storyboard_art: 'storyboard_art',
};
const STEP_TO_SKILL = {
    synopsis: 'showrunner', casting: 'casting', script: 'scriptwriter',
    images: 'character_visualizer', location_scout: 'location_scout', location_design: 'location_design',
    shot_breakdown: 'shot_breakdown', storyboard_art: 'storyboard_art',
};

function getCheckedSteps() {
    return Array.from(document.querySelectorAll('.workflow-step:checked')).map(cb => cb.dataset.step);
}

let pollingInterval = null;
let lastGenerationData = null;

// État d'affichage de chaque carte, conservé entre deux rendus (l'utilisateur
// garde la main sur ce qui est ouvert/fermé, on ne l'écrase jamais tout seul
// sauf lors du tout premier passage à "completed").
const cardUiState = {}; // { [skillKey]: { expanded: bool, logsOpen: bool, editing: bool, initialized: bool } }

function getCardState(key) {
    if (!cardUiState[key]) {
        cardUiState[key] = { expanded: true, logsOpen: false, editing: false, initialized: false };
    }
    return cardUiState[key];
}

function clearTimelineEmptyState() {
    const container = document.getElementById('timeline-container');
    const empty = container ? container.querySelector('.timeline-empty') : null;
    if (empty) empty.remove();
}

function setHeaderStatus(text, statusClass) {
    const badge = document.getElementById('header-project-status');
    if (!badge) return;
    badge.textContent = text;
    badge.className = `status-badge ${statusClass} ml-2`;
}

// ===== DÉMARRER LE POLLING =====
function startPollingGenerationStatus(projectId) {
    if (pollingInterval) clearInterval(pollingInterval);

    const poll = async () => {
        try {
            const data = await fetchGenerationStatus(projectId);
            if (!data) return;

            renderTimeline(data, true);

            const stillRunning = Object.values(data.generations || {}).some(g => g.status === 'running');
            if (!stillRunning && data.project_status !== 'generating') {
                clearInterval(pollingInterval);
                pollingInterval = null;
                setHeaderStatus(
                    data.project_status === 'ready' ? 'Ready' : 'Partial',
                    data.project_status === 'ready' ? 'status-completed' : 'status-failed'
                );
            }
        } catch (e) {
            console.error('   ❌ Polling error:', e);
        }
    };

    poll(); // premier appel immédiat
    pollingInterval = setInterval(poll, 1500);
}

// ===== RESTAURER LA TIMELINE AU CHARGEMENT DE LA PAGE =====
async function refreshTimelineFromServer(projectId) {
    const data = await fetchGenerationStatus(projectId);
    if (!data) return;

    // Recaler les cases à cocher sur la réalité de la base : une étape déjà
    // générée doit apparaître cochée, même si ce n'est pas l'état par défaut
    // du HTML — sinon on croit qu'un agent n'a jamais tourné alors que son
    // contenu existe bel et bien.
    _syncCheckboxesWithReality(data);

    renderTimeline(data);

    const stillRunning = Object.values(data.generations || {}).some(g => g.status === 'running')
        || data.project_status === 'generating';
    if (stillRunning) {
        setHeaderStatus('Generating', 'status-running');
        startPollingGenerationStatus(projectId);
    } else if (data.project_status && data.project_status !== 'draft') {
        const map = { ready: ['Ready', 'status-completed'], partial: ['Partial', 'status-failed'], completed: ['Completed', 'status-completed'] };
        const [text, cls] = map[data.project_status] || [data.project_status, 'status-pending'];
        setHeaderStatus(text, cls);
    }
}

async function fetchGenerationStatus(projectId) {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`/api/projects/${projectId}/generation-status`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!response.ok) return null;
    return await response.json();
}

// ===== CONSTRUIRE LA TIMELINE (CARTES AGENT) =====
// Insère une carte à sa position CORRECTE dans le pipeline (pas juste à la
// fin) — sans ça, l'ordre d'affichage dépend de l'ordre de création des
// cartes dans la session (ex: un storyboard généré individuellement avant
// que "Storyboard Art" ne soit jamais coché en groupe), pas de l'ordre
// logique du pipeline.
function _insertCardInOrder(container, card, order) {
    card.dataset.order = order;
    const siblings = Array.from(container.children);
    const nextSibling = siblings.find(el => {
        const elOrder = parseFloat(el.dataset.order);
        return !isNaN(elOrder) && elOrder > order;
    });
    if (nextSibling) {
        container.insertBefore(card, nextSibling);
    } else {
        container.appendChild(card);
    }
}

function renderTimeline(data, isPollRefresh) {
    const container = document.getElementById('timeline-container');
    if (!container) return;

    lastGenerationData = data;

    const generations = data.generations || {};
    const checkedSteps = getCheckedSteps();

    if (Object.keys(generations).length === 0 && checkedSteps.length === 0) return; // rien à afficher encore

    clearTimelineEmptyState();
    updateWorkflowCheckboxIndicators(generations);

    const relevantAgents = AGENT_PIPELINE.filter(a => generations[a.key] || checkedSteps.includes(SKILL_TO_STEP[a.key]));
    const doneCount = relevantAgents.filter(a => generations[a.key]?.status === 'completed').length;
    updateProgress(relevantAgents.length ? Math.round((doneCount / relevantAgents.length) * 100) : 0);

    let previousCompleted = true; // le premier agent de la chaîne n'a pas de prédécesseur
    let storyboardArtVisible = false; // Scene Generator ne s'affiche que si cette carte l'est aussi
    AGENT_PIPELINE.forEach((agent, index) => {
        const gen = generations[agent.key];
        const step = SKILL_TO_STEP[agent.key];
        const isChecked = checkedSteps.includes(step);

        if (gen) {
            // Déjà lancé au moins une fois (peu importe l'état actuel de la
            // case à cocher, cf. décision produit : décocher n'efface rien).
            renderAgentCard(container, agent, gen, data, index, isPollRefresh, !isChecked);
            previousCompleted = gen.status === 'completed';
            if (agent.key === 'storyboard_art') storyboardArtVisible = true;
        } else if (isChecked) {
            if (agent.key === 'storyboard_art' && previousCompleted && (data.scenes || []).length) {
                // Cas spécial : avec potentiellement des dizaines de plans, on ne
                // veut jamais forcer une génération groupée juste pour débloquer
                // le contrôle plan par plan — on l'offre directement.
                renderStoryboardReadyCard(container, agent, data, index);
                storyboardArtVisible = true;
            } else {
                // Coché mais jamais lancé : carte "Ready" ou "Queued" selon la position
                renderPendingCard(container, agent, previousCompleted ? 'ready' : 'queued', index);
                if (agent.key === 'storyboard_art') storyboardArtVisible = true;
            }
            previousCompleted = false;
        } else {
            // Ni généré ni coché : pas de carte (on retire si elle existait déjà)
            const existing = document.getElementById(`agent-card-${agent.key}`);
            if (existing) existing.remove();
        }
    });

    // Carte Scene Generator : visible dès qu'au moins un plan a un storyboard
    // sélectionné ET que la carte Storyboard Art est elle-même visible —
    // pas de sens à montrer les vidéos d'une étape que l'utilisateur a masquée.
    // Pas liée aux cases à cocher pour son propre déclenchement (coût par
    // vidéo trop élevé pour proposer un lancement groupé par défaut).
    const scenesWithStoryboard = (data.scenes || []).filter(
        s => (s.assets || []).some(a => a.asset_type === 'storyboard' && a.is_selected)
    );
    if (scenesWithStoryboard.length && storyboardArtVisible) {
        renderSceneGeneratorCard(container, data, scenesWithStoryboard, AGENT_PIPELINE.length);
    } else {
        const existing = document.getElementById('agent-card-scene_generator');
        if (existing) existing.remove();
    }

    // Carte Episode Assembly : toujours visible dès qu'il y a au moins un
    // épisode — indépendante du reste du pipeline, pas de notion de "prêt/pas
    // prêt" puisqu'elle gère elle-même les plans manquants via son rapport.
    if (data.episodes && data.episodes.length) {
        renderEpisodeAssemblyCard(container, data, AGENT_PIPELINE.length + 1);
    } else {
        const existing = document.getElementById('agent-card-episode_assembly');
        if (existing) existing.remove();
    }
}

// ===== CARTE EPISODE ASSEMBLY (cover + rapport + assemblage ffmpeg final) =====
function renderEpisodeAssemblyCard(container, data, index) {
    let card = document.getElementById('agent-card-episode_assembly');
    if (!card) {
        card = document.createElement('div');
        card.id = 'agent-card-episode_assembly';
        _insertCardInOrder(container, card, index);
    }
    card.className = `agent-card ${index % 2 === 0 ? 'zebra-even' : 'zebra-odd'}`;

    const state = getCardState('episode_assembly');
    const uiKey = 'episode_assembly';
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { selectedEpisodeId: data.episodes[0]?.id, selectedModel: 'qwen-image-2.0-pro', report: null, coverHistoryOpen: false };
    const ui = cardUiState[uiKey];
    if (!ui.selectedEpisodeId) ui.selectedEpisodeId = data.episodes[0]?.id;

    const episode = data.episodes.find(e => e.id === ui.selectedEpisodeId) || data.episodes[0];

    card.innerHTML = `
        <div class="agent-card-header" onclick="toggleCardExpand('episode_assembly')">
            <span class="agent-card-title"><i class="fas fa-clapperboard"></i> Episode Assembly</span>
            <div class="agent-card-header-right">
                <span class="status-badge status-pending">Cover + final cut</span>
                <i class="fas fa-chevron-down agent-card-chevron ${state.expanded ? 'expanded' : ''}"></i>
            </div>
        </div>
        <div class="agent-card-summary" style="${state.expanded ? 'display:none' : ''}">
            <span class="agent-card-summary-text">Generate a cover and assemble the final cut for an episode</span>
        </div>
        <div class="agent-card-body" style="${state.expanded ? '' : 'display:none'}">
            <p class="agent-card-summary-text">
                Purely mechanical assembly (ffmpeg, no AI) of the selected video clips, in shot order —
                plus an optional AI-generated cover with your project's title, episode number, and logo.
            </p>
            <div class="form-group" style="margin-top:0.75rem;">
                <label class="form-label">Episode</label>
                <select class="form-input" onchange="setEpisodeAssemblySelection(this.value)">
                    ${data.episodes.map(e => `<option value="${e.id}" ${e.id === ui.selectedEpisodeId ? 'selected' : ''}>${escapeHtml(e.title)}</option>`).join('')}
                </select>
            </div>

            <div class="agent-card-section-label" style="margin-top:1rem;">Cover</div>
            ${renderEpisodeCoverSection(episode, ui)}

            <div class="agent-card-section-label" style="margin-top:1.25rem;">Final Cut</div>
            <div class="character-card-buttons character-sheet-controls">
                <button class="agent-card-btn agent-card-btn-secondary" ${ui.loadingReport ? 'disabled' : ''} onclick="previewEpisodeAssemblyReport()">
                    <i class="fas fa-list-check ${ui.loadingReport ? 'fa-spin' : ''}"></i> ${ui.loadingReport ? 'Checking…' : 'Preview Report'}
                </button>
                <button class="agent-card-btn agent-card-btn-primary" ${(!ui.report || !ui.report.can_assemble || ui.assembling) ? 'disabled' : ''} onclick="assembleEpisodeVideo()"
                        title="${!ui.report ? 'Preview the report first' : (!ui.report.can_assemble ? 'No available clips for this episode' : '')}">
                    <i class="fas fa-film ${ui.assembling ? 'fa-spin' : ''}"></i> ${ui.assembling ? 'Assembling…' : 'Assemble Video'}
                </button>
            </div>
            ${ui.report ? renderEpisodeAssemblyReport(ui.report) : ''}
            ${episode.assembled_video_url ? `
                <div class="agent-card-section-label" style="margin-top:1rem;">Assembled Episode</div>
                <video controls class="scene-video-player" style="max-width:28rem;" src="${escapeHtml(episode.assembled_video_url)}"></video>
                <a class="agent-card-btn agent-card-btn-secondary" style="display:inline-flex; margin-top:0.5rem; text-decoration:none;" href="${escapeHtml(episode.assembled_video_url)}" download>
                    <i class="fas fa-download"></i> Download
                </a>
            ` : ''}
        </div>
    `;
}

function renderEpisodeCoverSection(episode, ui) {
    const covers = (episode.assets || []).filter(a => a.asset_type === 'cover');
    const batches = {};
    covers.forEach(a => (batches[a.generation_batch] = batches[a.generation_batch] || []).push(a));
    const batchNumbers = Object.keys(batches).map(Number).sort((a, b) => a - b);
    const selected = covers.find(a => a.is_selected);

    const preview = selected && selected.status === 'completed'
        ? `<img src="${escapeHtml(selected.url)}" class="episode-cover-preview" onclick="openImageLightbox('${escapeHtml(selected.url)}', event)" alt="cover">`
        : `<p class="agent-card-summary-text">No cover generated yet.</p>`;

    const historyHtml = ui.coverHistoryOpen ? `
        <div class="character-image-history">
            ${batchNumbers.slice(0, -1).reverse().map(bn => `
                <div class="character-image-history-batch">
                    <span class="agent-card-section-label">Batch ${bn} — ${escapeHtml(batches[bn][0].model_used || '')}</span>
                    ${batches[bn].filter(a => a.status === 'completed').map(a => `
                        <div class="scene-video-history-item">
                            <img src="${escapeHtml(a.url)}" class="scene-video-history-thumb" onclick="openImageLightbox('${escapeHtml(a.url)}', event)">
                            <button class="agent-card-btn ${a.is_selected ? 'agent-card-btn-primary' : 'agent-card-btn-secondary'}" onclick="selectEpisodeCover(${episode.id}, ${a.id})">
                                ${a.is_selected ? '✓ Selected' : 'Select'}
                            </button>
                            <button class="agent-card-btn agent-card-btn-secondary" onclick="deleteEpisodeCover(${episode.id}, ${a.id}, event)" title="Delete"><i class="fas fa-trash"></i></button>
                        </div>
                    `).join('')}
                </div>
            `).join('')}
        </div>
    ` : '';

    return `
        ${preview}
        <div class="character-card-buttons character-sheet-controls" style="margin-top:0.5rem;">
            <select class="form-input character-sheet-model-select" onchange="setEpisodeAssemblyModel(this.value)">
                ${COVER_MODELS.map(m => `<option value="${m}" ${m === ui.selectedModel ? 'selected' : ''}>${m}</option>`).join('')}
            </select>
            <button class="agent-card-btn agent-card-btn-secondary" ${ui.generatingCover ? 'disabled' : ''} onclick="generateEpisodeCover()">
                <i class="fas fa-image ${ui.generatingCover ? 'fa-spin' : ''}"></i> ${ui.generatingCover ? 'Generating…' : (covers.length ? 'Generate Another' : 'Generate Cover')}
            </button>
            <label class="agent-card-btn agent-card-btn-secondary character-upload-btn">
                <i class="fas fa-upload"></i> Upload
                <input type="file" accept="image/*" style="display:none" onchange="uploadEpisodeCover(${episode.id}, this.files[0])">
            </label>
        </div>
        ${batchNumbers.length > 1 ? `
            <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${episode.id}, 'coverHistoryOpen', event, 'episode_assembly')">
                <i class="fas fa-chevron-${ui.coverHistoryOpen ? 'down' : 'right'}"></i>
                <span>Previous covers (${batchNumbers.length - 1})</span>
            </div>
            ${historyHtml}
        ` : ''}
    `;
}

function renderEpisodeAssemblyReport(report) {
    return `
        <div class="agent-card-logs" style="margin-top:0.75rem;">
            <div class="agent-card-log"><span class="agent-card-log-time">Total shots</span><span>${report.total_shots}</span></div>
            <div class="agent-card-log"><span class="agent-card-log-time">Available</span><span>${report.available_count} / ${report.total_shots}</span></div>
            <div class="agent-card-log"><span class="agent-card-log-time">Total duration</span><span>${report.total_duration_seconds}s</span></div>
            ${report.missing_shots.length ? `
                <div class="agent-card-log"><span class="agent-card-log-time scene-video-error">Missing shots</span>
                <span>${report.missing_shots.map(s => `#${s.number}`).join(', ')}</span></div>
            ` : '<div class="agent-card-log"><span class="agent-card-log-time">Missing shots</span><span>None — all shots ready</span></div>'}
            ${!report.can_assemble ? '<p class="agent-card-summary-text scene-video-error" style="margin-top:0.5rem;"><i class="fas fa-triangle-exclamation"></i> No shot has an available video yet — generate at least one before assembling.</p>' : ''}
        </div>
    `;
}

function setEpisodeAssemblySelection(episodeId) {
    const ui = cardUiState['episode_assembly'];
    ui.selectedEpisodeId = parseInt(episodeId, 10);
    ui.report = null; // changer d'épisode invalide le rapport précédent
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

function setEpisodeAssemblyModel(model) {
    cardUiState['episode_assembly'].selectedModel = model;
}

async function generateEpisodeCover() {
    const ui = cardUiState['episode_assembly'];
    ui.generatingCover = true;
    if (lastGenerationData) renderTimeline(lastGenerationData);
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/episodes/${ui.selectedEpisodeId}/generate-cover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ model: ui.selectedModel })
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Cover generation failed');
        }
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Episode cover error:', e);
        alert(e.message || 'Failed to generate cover.');
    } finally {
        ui.generatingCover = false;
        if (lastGenerationData) renderTimeline(lastGenerationData);
    }
}

async function selectEpisodeCover(episodeId, assetId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/episodes/${episodeId}/select-cover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ asset_id: assetId })
        });
        if (!response.ok) throw new Error('Selection failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Cover selection error:', e);
        alert('Failed to select cover.');
    }
}

async function uploadEpisodeCover(episodeId, file) {
    if (!file) return;
    try {
        const token = localStorage.getItem('access_token');
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`/api/episodes/${episodeId}/upload-cover`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        if (!response.ok) throw new Error('Upload failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Cover upload error:', e);
        alert('Failed to upload cover.');
    }
}

async function deleteEpisodeCover(episodeId, assetId, event) {
    if (event) event.stopPropagation();
    if (!confirm('Delete this cover permanently? This cannot be undone.')) return;
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/episodes/${episodeId}/covers/${assetId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Delete failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Cover delete error:', e);
        alert('Failed to delete cover.');
    }
}

async function previewEpisodeAssemblyReport() {
    const ui = cardUiState['episode_assembly'];
    ui.loadingReport = true;
    if (lastGenerationData) renderTimeline(lastGenerationData);
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/episodes/${ui.selectedEpisodeId}/assembly-report`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Failed to load report');
        ui.report = await response.json();
    } catch (e) {
        console.error('   ❌ Assembly report error:', e);
        alert('Failed to load the assembly report.');
    } finally {
        ui.loadingReport = false;
        if (lastGenerationData) renderTimeline(lastGenerationData);
    }
}

async function assembleEpisodeVideo() {
    const ui = cardUiState['episode_assembly'];
    if (!ui.report || !ui.report.can_assemble) return;
    if (ui.report.missing_shots.length > 0) {
        const proceed = confirm(
            `${ui.report.missing_shots.length} shot(s) will be skipped (no available video): ` +
            `${ui.report.missing_shots.map(s => '#' + s.number).join(', ')}.\n\n` +
            `Assemble anyway with the ${ui.report.available_count} available shot(s)?`
        );
        if (!proceed) return;
    }
    ui.assembling = true;
    if (lastGenerationData) renderTimeline(lastGenerationData);
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/episodes/${ui.selectedEpisodeId}/assemble-video`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Assembly failed');
        }
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Episode assembly error:', e);
        alert(e.message || 'Failed to assemble episode video.');
    } finally {
        ui.assembling = false;
        if (lastGenerationData) renderTimeline(lastGenerationData);
    }
}


// ===== CARTE SPÉCIALE STORYBOARD ART : génération plan par plan dès le départ =====
function renderStoryboardReadyCard(container, agent, data, index) {
    let card = document.getElementById(`agent-card-${agent.key}`);
    if (!card) {
        card = document.createElement('div');
        card.id = `agent-card-${agent.key}`;
        _insertCardInOrder(container, card, index);
    }
    card.className = `agent-card ${index % 2 === 0 ? 'zebra-even' : 'zebra-odd'}`;

    const state = getCardState(agent.key);
    const scenes = data.scenes || [];
    const episodes = data.episodes || [];
    const byEpisode = {};
    scenes.forEach(s => (byEpisode[s.episode_id] = byEpisode[s.episode_id] || []).push(s));

    const totalImages = scenes.reduce((sum, s) => sum + (s.assets || []).filter(a => a.asset_type === 'storyboard' && a.status === 'completed').length, 0);

    card.innerHTML = `
        <div class="agent-card-header" onclick="toggleCardExpand('${agent.key}')">
            <span class="agent-card-title"><i class="fas ${agent.icon}"></i> ${agent.label}</span>
            <div class="agent-card-header-right">
                <span class="status-badge status-pending">Ready — generate one at a time</span>
                <i class="fas fa-chevron-down agent-card-chevron ${state.expanded ? 'expanded' : ''}"></i>
            </div>
        </div>
        <div class="agent-card-summary" style="${state.expanded ? 'display:none' : ''}">
            <span class="agent-card-summary-text">${totalImages} storyboard frame(s) across ${scenes.length} shot(s)</span>
        </div>
        <div class="agent-card-body" style="${state.expanded ? '' : 'display:none'}">
            <p class="agent-card-summary-text">
                Generate storyboard frames individually below — pick a model per shot to compare quality
                without spending credits on all ${scenes.length} shot(s) at once.
            </p>
            ${Object.entries(byEpisode).map(([epId, epScenes]) => {
                const ep = episodes.find(e => e.id == epId);
                return `
                    <div class="agent-card-section-label" style="margin-top:0.75rem;">${ep ? escapeHtml(ep.title) : 'Episode'}</div>
                    ${epScenes.map(s => renderSceneStoryboardGroup(s, data)).join('')}
                `;
            }).join('')}
        </div>
    `;
}


const VIDEO_MODELS = ['happyhorse-1.1-r2v', 'wan2.7-r2v-2026-06-12'];

// ===== CARTE SCENE GENERATOR (toujours visible, indépendante des cases à cocher) =====
function renderSceneGeneratorCard(container, data, scenes, index) {
    let card = document.getElementById('agent-card-scene_generator');
    if (!card) {
        card = document.createElement('div');
        card.id = 'agent-card-scene_generator';
        _insertCardInOrder(container, card, index);
    }
    card.className = `agent-card ${index % 2 === 0 ? 'zebra-even' : 'zebra-odd'}`;

    const state = getCardState('scene_generator');
    const episodes = data.episodes || [];
    const byEpisode = {};
    scenes.forEach(s => (byEpisode[s.episode_id] = byEpisode[s.episode_id] || []).push(s));

    const totalVideos = scenes.reduce((sum, s) => sum + (s.assets || []).filter(a => a.asset_type === 'video' && a.status === 'completed').length, 0);

    card.innerHTML = `
        <div class="agent-card-header" onclick="toggleCardExpand('scene_generator')">
            <span class="agent-card-title"><i class="fas fa-clapperboard"></i> Shot Director Agent</span>
            <div class="agent-card-header-right">
                <span class="status-badge status-pending">Generate one shot at a time</span>
                <i class="fas fa-chevron-down agent-card-chevron ${state.expanded ? 'expanded' : ''}"></i>
            </div>
        </div>
        <div class="agent-card-summary" style="${state.expanded ? 'display:none' : ''}">
            <span class="agent-card-summary-text">${totalVideos} video(s) generated across ${scenes.length} shot(s)</span>
        </div>
        <div class="agent-card-body" style="${state.expanded ? '' : 'display:none'}">
            <p class="agent-card-summary-text">
                Turns each shot's selected storyboard into a real video clip — combining the
                storyboard, characters, and location already chosen. Each video costs real
                credits and takes a few minutes, so nothing here ever runs automatically.
            </p>
            ${Object.entries(byEpisode).map(([epId, epScenes]) => {
                const ep = episodes.find(e => e.id == epId);
                return `
                    <div class="agent-card-section-label" style="margin-top:1.25rem;">${ep ? escapeHtml(ep.title) : 'Episode'}</div>
                    ${epScenes.map(s => renderSceneVideoRow(s, data)).join('')}
                `;
            }).join('')}
        </div>
    `;
}

// ===== LIGNE VIDÉO D'UN PLAN (layout aéré : infos+storyboard à gauche, génération/lecteur à droite) =====
function renderSceneVideoRow(scene, liveData) {
    const videoAssets = (scene.assets || []).filter(a => a.asset_type === 'video');
    const uiKey = `video-${scene.id}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { selectedModel: VIDEO_MODELS[0], historyOpen: false, promptsOpen: false, customPrompt: null };
    const ui = cardUiState[uiKey];

    const storyboard = (scene.assets || []).find(a => a.asset_type === 'storyboard' && a.is_selected);
    const loc = (liveData.locations || []).find(l => l.id === scene.location_id);
    const chars = (liveData.characters || []).filter(c => (scene.character_ids || []).includes(c.id));

    // Portraits/décor RÉELLEMENT sélectionnés — ce sont eux qui partiront en
    // référence à l'appel vidéo. Les afficher permet de vérifier visuellement
    // avant de dépenser des crédits, plutôt que de découvrir après coup qu'une
    // référence manquait ou ne correspondait pas à ce qu'on attendait.
    const charThumbs = chars.map(c => ({
        name: c.name,
        url: (c.assets || []).find(a => a.asset_type === 'portrait' && a.is_selected)?.url || null,
    }));
    const locThumb = loc ? { name: loc.name, url: (loc.assets || []).find(a => a.asset_type === 'reference' && a.is_selected)?.url || null } : null;

    const missingCharRefs = charThumbs.filter(c => !c.url);
    const missingLocRef = loc && !locThumb?.url;
    const hasMissingRefs = missingCharRefs.length > 0 || missingLocRef;

    const batches = {};
    videoAssets.forEach(a => (batches[a.generation_batch] = batches[a.generation_batch] || []).push(a));
    const batchNumbers = Object.keys(batches).map(Number).sort((a, b) => a - b);
    const latestBatchNum = batchNumbers[batchNumbers.length - 1];
    const latestBatchVideo = latestBatchNum ? batches[latestBatchNum][0] : null;
    // La vidéo "sélectionnée" peut venir d'un lot plus ancien si l'utilisateur
    // est revenu en arrière via l'historique — sinon on retombe sur le dernier lot.
    const selectedVideo = videoAssets.find(a => a.is_selected) || latestBatchVideo;

    const isPending = videoAssets.some(a => a.status === 'pending');
    const hasAny = videoAssets.some(a => a.status === 'completed');

    if (isPending) _ensureScenePolling(scene.id);

    let visualContent;
    if (selectedVideo && selectedVideo.status === 'completed') {
        visualContent = `
            <div class="scene-video-player-wrap">
                <video controls class="scene-video-player" src="${escapeHtml(selectedVideo.url)}"></video>
                <button class="agent-card-btn agent-card-btn-secondary scene-video-expand-btn" onclick="openVideoLightbox('${escapeHtml(selectedVideo.url)}', event)" title="View larger">
                    <i class="fas fa-expand"></i>
                </button>
            </div>`;
    } else if (isPending) {
        visualContent = `<p class="agent-card-summary-text">Generating… this can take several minutes. Feel free to keep working on other shots meanwhile.</p>`;
    } else if (latestBatchVideo && latestBatchVideo.status === 'failed') {
        visualContent = `<p class="agent-card-summary-text scene-video-error">Generation failed — try a different model, or edit the prompt below.</p>`;
    } else {
        visualContent = `<p class="agent-card-summary-text">No video yet.</p>`;
    }

    const canGenerate = !isPending && storyboard && !hasMissingRefs;
    let disabledReason = '';
    if (!storyboard) disabledReason = 'Select a storyboard first';
    else if (hasMissingRefs) {
        const missing = [...missingCharRefs.map(c => c.name), ...(missingLocRef ? [loc.name] : [])];
        disabledReason = `Missing selected reference image for: ${missing.join(', ')}`;
    }

    const refThumb = (name, url) => url
        ? `<div class="scene-ref-thumb-wrap"><img src="${escapeHtml(url)}" class="scene-ref-thumb" onclick="openImageLightbox('${escapeHtml(url)}', event)" title="${escapeHtml(name)}"></div>`
        : `<div class="scene-ref-thumb-wrap scene-ref-thumb-missing" title="No selected image for ${escapeHtml(name)}"><i class="fas fa-triangle-exclamation"></i></div>`;

    // Historique des lots précédents, chacun sélectionnable
    const historyHtml = ui.historyOpen ? `
        <div class="character-image-history">
            ${batchNumbers.slice(0, -1).reverse().map(bn => `
                <div class="character-image-history-batch">
                    <span class="agent-card-section-label">Batch ${bn} — ${escapeHtml(batches[bn][0].model_used || '')}</span>
                    ${batches[bn].filter(a => a.status === 'completed').map(a => `
                        <div class="scene-video-history-item">
                            <video class="scene-video-history-thumb" src="${escapeHtml(a.url)}" muted onclick="openVideoLightbox('${escapeHtml(a.url)}', event)"></video>
                            <button class="agent-card-btn ${a.is_selected ? 'agent-card-btn-primary' : 'agent-card-btn-secondary'}" onclick="selectSceneVideo(${scene.id}, ${a.id})">
                                ${a.is_selected ? '✓ Selected' : 'Select'}
                            </button>
                        </div>
                    `).join('')}
                </div>
            `).join('')}
        </div>
    ` : '';

    // Prompt utilisé + édition manuelle avant régénération
    const currentPromptText = selectedVideo?.prompt_used || '';
    const promptsHtml = ui.promptsOpen ? `
        <div class="agent-card-logs">
            <textarea class="form-textarea scene-video-prompt-edit" id="scene-video-prompt-${scene.id}" rows="5"
                      oninput="cardUiState['${uiKey}'].customPrompt = this.value">${escapeHtml(ui.customPrompt !== null ? ui.customPrompt : currentPromptText)}</textarea>
            <div class="agent-card-actions" style="margin-top:0.5rem;">
                <button class="agent-card-btn agent-card-btn-secondary" onclick="resetSceneVideoPrompt(${scene.id})">Reset to auto-generated</button>
                <button class="agent-card-btn agent-card-btn-primary" ${!canGenerate ? 'disabled' : ''} onclick="buildSceneVideo(${scene.id}, true)">
                    <i class="fas fa-video"></i> Regenerate with this prompt
                </button>
            </div>
        </div>
    ` : '';

    return `
        <div class="scene-video-row">
            <div class="scene-video-info">
                <div class="agent-card-section-label">Shot ${scene.number}${scene.is_cliffhanger ? ' — Cliffhanger' : ''}</div>
                ${storyboard
                    ? `<img src="${escapeHtml(storyboard.url)}" class="scene-video-storyboard-thumb" onclick="openImageLightbox('${escapeHtml(storyboard.url)}', event)" alt="storyboard" title="Click to enlarge">`
                    : `<p class="agent-card-summary-text">No storyboard selected for this shot yet.</p>`}
                <div class="scene-ref-thumbs-row">
                    ${charThumbs.map(c => refThumb(c.name, c.url)).join('')}
                    ${loc ? refThumb(loc.name, locThumb?.url) : ''}
                </div>
                ${hasMissingRefs ? `<p class="agent-card-summary-text scene-video-error" style="font-size:0.75rem;"><i class="fas fa-triangle-exclamation"></i> ${escapeHtml(disabledReason)}</p>` : ''}
                <div class="agent-card-section"><span class="agent-card-section-value">${escapeHtml(scene.description || '')}</span></div>
                <div class="agent-card-section"><span class="agent-card-section-label">Duration</span><span class="agent-card-section-value">${scene.duration_seconds}s</span></div>
                <div class="agent-card-section"><span class="agent-card-section-label">Characters</span><span class="agent-card-section-value">${chars.length ? escapeHtml(chars.map(c => c.name).join(', ')) : '—'}</span></div>
                <div class="agent-card-section"><span class="agent-card-section-label">Location</span><span class="agent-card-section-value">${loc ? escapeHtml(loc.name) : '—'}</span></div>
            </div>
            <div class="scene-video-visual">
                <div class="character-card-buttons character-sheet-controls">
                    <select class="form-input character-sheet-model-select" onchange="setSceneVideoModel(${scene.id}, this.value)">
                        ${VIDEO_MODELS.map(m => `<option value="${m}" ${m === ui.selectedModel ? 'selected' : ''}>${m}</option>`).join('')}
                    </select>
                    <button class="agent-card-btn agent-card-btn-primary" ${!canGenerate ? 'disabled' : ''}
                            title="${escapeHtml(disabledReason)}"
                            onclick="buildSceneVideo(${scene.id})">
                        <i class="fas fa-video ${isPending ? 'fa-spin' : ''}"></i> ${isPending ? 'Generating…' : (hasAny ? 'Regenerate' : 'Generate Video')}
                    </button>
                </div>
                ${visualContent}
                ${batchNumbers.length > 1 ? `
                    <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${scene.id}, 'historyOpen', event, '${uiKey}')">
                        <i class="fas fa-chevron-${ui.historyOpen ? 'down' : 'right'}"></i>
                        <span>Previous videos (${batchNumbers.length - 1})</span>
                    </div>
                    ${historyHtml}
                ` : ''}
                ${hasAny ? `
                    <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${scene.id}, 'promptsOpen', event, '${uiKey}')">
                        <i class="fas fa-chevron-${ui.promptsOpen ? 'down' : 'right'}"></i>
                        <span>Prompt used</span>
                    </div>
                    ${promptsHtml}
                ` : ''}
            </div>
        </div>
    `;
}

function setSceneVideoModel(sceneId, model) {
    const uiKey = `video-${sceneId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { selectedModel: VIDEO_MODELS[0], historyOpen: false, promptsOpen: false, customPrompt: null };
    cardUiState[uiKey].selectedModel = model;
}

function resetSceneVideoPrompt(sceneId) {
    const uiKey = `video-${sceneId}`;
    if (cardUiState[uiKey]) cardUiState[uiKey].customPrompt = null;
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function selectSceneVideo(sceneId, assetId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/scenes/${sceneId}/select-video`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ asset_id: assetId })
        });
        if (!response.ok) throw new Error('Selection failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Video selection error:', e);
        alert('Failed to select video.');
    }
}

function openVideoLightbox(url, event) {
    if (event) event.stopPropagation();
    closeImageLightbox(); // ferme un éventuel lightbox image déjà ouvert

    const overlay = document.createElement('div');
    overlay.id = 'image-lightbox-overlay'; // même id pour réutiliser closeImageLightbox()/Échap
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) closeImageLightbox(); };

    overlay.innerHTML = `
        <div class="lightbox-panel">
            <button class="modal-close-btn lightbox-close-btn" onclick="closeImageLightbox()"><i class="fas fa-xmark"></i></button>
            <video class="lightbox-image" src="${escapeHtml(url)}" controls autoplay></video>
        </div>
    `;
    document.body.appendChild(overlay);
    document.addEventListener('keydown', _lightboxEscHandler);
}

async function buildSceneVideo(sceneId, useCustomPrompt) {
    const uiKey = `video-${sceneId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { selectedModel: VIDEO_MODELS[0], historyOpen: false, promptsOpen: false, customPrompt: null };
    try {
        const token = localStorage.getItem('access_token');
        const payload = { model: cardUiState[uiKey].selectedModel };
        if (useCustomPrompt && cardUiState[uiKey].customPrompt) {
            payload.custom_prompt = cardUiState[uiKey].customPrompt;
        }
        const response = await fetch(`/api/scenes/${sceneId}/generate-video`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Video generation failed to start');
        }
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Scene video generation error:', e);
        alert(e.message || 'Failed to start video generation.');
    }
}

// La génération vidéo prend plusieurs minutes : polling léger dédié,
// indépendant du polling principal du pipeline, tant qu'au moins une vidéo
// de ce plan est "pending".
const _scenePollingIntervals = {};
function _ensureScenePolling(sceneId) {
    if (_scenePollingIntervals[sceneId]) return;
    _scenePollingIntervals[sceneId] = setInterval(async () => {
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (!data) return;
        const scene = (data.scenes || []).find(s => s.id === sceneId);
        const stillPending = (scene?.assets || []).some(a => a.asset_type === 'video' && a.status === 'pending');
        if (!stillPending) {
            clearInterval(_scenePollingIntervals[sceneId]);
            delete _scenePollingIntervals[sceneId];
        }
        renderTimeline(data, true);
    }, 15000);
}

function renderPendingCard(container, agent, mode, index) {
    let card = document.getElementById(`agent-card-${agent.key}`);
    if (!card) {
        card = document.createElement('div');
        card.id = `agent-card-${agent.key}`;
        _insertCardInOrder(container, card, index);
    }
    card.className = `agent-card agent-card-pending ${index % 2 === 0 ? 'zebra-even' : 'zebra-odd'}`;

    if (mode === 'ready') {
        card.innerHTML = `
            <div class="agent-card-header">
                <span class="agent-card-title"><i class="fas ${agent.icon}"></i> ${agent.label}</span>
                <span class="status-badge status-pending">Ready</span>
            </div>
            <div class="agent-card-body">
                <p class="agent-card-summary-text">Ready to generate.</p>
                <div class="agent-card-actions">
                    <button class="agent-card-btn agent-card-btn-primary" onclick="regenerateStep('${agent.key}', false)">
                        <i class="fas fa-play"></i> Generate
                    </button>
                </div>
            </div>
        `;
    } else {
        const prevAgent = AGENT_PIPELINE[index - 1];
        card.innerHTML = `
            <div class="agent-card-header">
                <span class="agent-card-title"><i class="fas ${agent.icon}"></i> ${agent.label}</span>
                <span class="status-badge status-pending">Queued</span>
            </div>
            <div class="agent-card-body">
                <p class="agent-card-summary-text">Waiting for ${prevAgent ? prevAgent.label : 'previous step'} to complete…</p>
            </div>
        `;
    }
}

// ===== INDICATEURS SUR LES CASES À COCHER (🔒 = déjà généré) =====
// Recale les cases à cocher sur la réalité de la base, une seule fois au
// chargement — sans ça, une étape déjà générée dans une session précédente
// apparaît décochée juste parce que ce n'est pas l'état par défaut du HTML.
function _syncCheckboxesWithReality(data) {
    const generations = data.generations || {};
    const hasAnyStoryboard = (data.scenes || []).some(s => (s.assets || []).some(a => a.asset_type === 'storyboard' && a.status === 'completed'));
    const hasAnyVideo = (data.scenes || []).some(s => (s.assets || []).some(a => a.asset_type === 'video' && a.status === 'completed'));

    document.querySelectorAll('.workflow-step').forEach(cb => {
        if (cb.dataset.step === 'scene_generator') {
            if (hasAnyVideo) cb.checked = true;
            return;
        }
        if (cb.dataset.step === 'storyboard_art') {
            if (hasAnyStoryboard || generations['storyboard_art']?.status === 'completed') cb.checked = true;
            return;
        }
        const skillKey = STEP_TO_SKILL[cb.dataset.step];
        if (generations[skillKey]?.status === 'completed') {
            cb.checked = true;
        }
    });
}

function updateWorkflowCheckboxIndicators(generations) {
    document.querySelectorAll('.workflow-step-item').forEach(item => {
        const cb = item.querySelector('.workflow-step');
        if (!cb) return;
        const skillKey = STEP_TO_SKILL[cb.dataset.step];
        const isDone = generations?.[skillKey]?.status === 'completed';

        const old = item.querySelector('.workflow-step-done-indicator');
        if (old) old.remove();

        if (isDone) {
            const indicator = document.createElement('span');
            indicator.className = 'workflow-step-done-indicator';
            indicator.title = 'Already generated — unchecking will not delete it';
            indicator.innerHTML = '<i class="fas fa-lock"></i>';
            item.appendChild(indicator);
        }
    });
}

// Une carte (ou une fiche personnage à l'intérieur) est-elle en cours d'édition ?
// Sert à ne JAMAIS écraser un formulaire en cours de saisie pendant un
// rafraîchissement silencieux du polling (bug corrigé : ça pouvait vider le
// texte en cours d'édition avant même que l'utilisateur clique Save).
function _cardHasActiveEdit(agentKey) {
    if (agentKey === 'casting') {
        return Object.keys(cardUiState).some(k => k.startsWith('char-') && cardUiState[k].editing);
    }
    if (agentKey === 'scriptwriter') {
        return Object.keys(cardUiState).some(k => k.startsWith('ep-') && cardUiState[k].editing);
    }
    return !!getCardState(agentKey).editing;
}

// ===== UNE CARTE AGENT =====
function renderAgentCard(container, agent, gen, liveData, index, isPollRefresh, isExcluded) {
    // Ne JAMAIS toucher au DOM d'une carte que l'utilisateur est en train
    // d'éditer lors d'un rafraîchissement automatique (polling). On ne
    // re-rendra cette carte que suite à une action explicite (Save/Cancel).
    if (isPollRefresh && _cardHasActiveEdit(agent.key)) return;

    const state = getCardState(agent.key);

    // Repli automatique la première fois qu'une carte termine (une seule fois,
    // ensuite on respecte le choix de l'utilisateur).
    if (!state.initialized && gen.status === 'completed') {
        state.expanded = false;
        state.initialized = true;
    }
    if (gen.status === 'running' || gen.status === 'pending') {
        state.initialized = false; // pour re-déclencher le repli auto à la prochaine complétion
    }

    let card = document.getElementById(`agent-card-${agent.key}`);
    if (!card) {
        card = document.createElement('div');
        card.id = `agent-card-${agent.key}`;
        _insertCardInOrder(container, card, index);
    }
    // Zebra striping : cartes paires/impaires légèrement teintées différemment
    card.className = `agent-card ${index % 2 === 0 ? 'zebra-even' : 'zebra-odd'}`;

    const statusClass = {
        running: 'status-running', completed: 'status-completed',
        failed: 'status-failed', pending: 'status-pending'
    }[gen.status] || 'status-pending';

    const statusLabel = {
        running: 'Working…', completed: 'Done', failed: 'Failed', pending: 'Pending'
    }[gen.status] || gen.status;

    const isStale = gen.result && gen.result.stale;

    card.innerHTML = `
        <div class="agent-card-header" onclick="toggleCardExpand('${agent.key}')">
            <span class="agent-card-title"><i class="fas ${agent.icon}"></i> ${agent.label}</span>
            <div class="agent-card-header-right">
                ${isExcluded ? '<span class="stale-badge" title="Excluded from Generate All — content kept, not deleted">Excluded</span>' : ''}
                ${isStale ? '<span class="stale-badge" title="Le contenu source a changé depuis cette génération">⚠ May be outdated</span>' : ''}
                <span class="status-badge ${statusClass}">${statusLabel}</span>
                ${gen.status === 'completed' ? `<i class="fas fa-clock-rotate-left agent-card-history-icon" title="Version history" onclick="openVersionHistory('${agent.key}', event)"></i>` : ''}
                <i class="fas fa-chevron-down agent-card-chevron ${state.expanded ? 'expanded' : ''}"></i>
            </div>
        </div>
        <div class="agent-card-summary" style="${state.expanded ? 'display:none' : ''}">
            ${renderCardSummary(agent.key, gen, liveData)}
        </div>
        <div class="agent-card-body" style="${state.expanded ? '' : 'display:none'}">
            <div class="agent-card-content" id="agent-card-content-${agent.key}">
                ${renderResultSection(agent.key, gen, liveData, state)}
            </div>
            ${gen.status === 'running' ? '<div class="agent-card-progress"><div class="agent-card-progress-bar" style="width: 60%"></div></div>' : ''}
            ${(gen.status === 'completed' || gen.status === 'failed') ? renderActionButtons(agent) : ''}
            ${renderLogsAccordion(agent.key, gen, state)}
        </div>
    `;
}

// Résumé court affiché carte repliée
function renderCardSummary(agentKey, gen, liveData) {
    if (agentKey === 'showrunner') {
        return `<span class="agent-card-summary-text">${escapeHtml(liveData.project?.hook || 'No hook yet')}</span>`;
    }
    if (agentKey === 'casting') {
        const chars = liveData.characters || [];
        const names = chars.map(c => escapeHtml(c.name)).join(', ');
        return `<span class="agent-card-summary-text">${chars.length} character(s)${names ? ' — ' + names : ''}</span>`;
    }
    if (agentKey === 'scriptwriter') {
        const eps = liveData.episodes || [];
        if (!eps.length) return `<span class="agent-card-summary-text">No script yet</span>`;
        if (eps.length === 1) return `<span class="agent-card-summary-text">${escapeHtml(eps[0].title)}</span>`;
        return `<span class="agent-card-summary-text">${eps.length} episodes — ${escapeHtml(eps[0].title)}...</span>`;
    }
    if (agentKey === 'location_scout') {
        const locs = liveData.locations || [];
        const names = locs.map(l => escapeHtml(l.name)).join(', ');
        return `<span class="agent-card-summary-text">${locs.length} location(s)${names ? ' — ' + names : ''}</span>`;
    }
    if (agentKey === 'location_design') {
        const locs = liveData.locations || [];
        const totalImages = locs.reduce((sum, l) => sum + (l.assets?.filter(a => a.status === 'completed').length || 0), 0);
        return `<span class="agent-card-summary-text">${totalImages} image(s) across ${locs.length} location(s)</span>`;
    }
    if (agentKey === 'shot_breakdown') {
        const scenes = liveData.scenes || [];
        return `<span class="agent-card-summary-text">${scenes.length} shot(s) identified</span>`;
    }
    if (agentKey === 'storyboard_art') {
        const scenes = liveData.scenes || [];
        const totalImages = scenes.reduce((sum, s) => sum + (s.assets?.filter(a => a.status === 'completed').length || 0), 0);
        return `<span class="agent-card-summary-text">${totalImages} storyboard frame(s) across ${scenes.length} shot(s)</span>`;
    }
    return '';
}

function toggleCardExpand(key) {
    const state = getCardState(key);
    state.expanded = !state.expanded;
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

function toggleLogsAccordion(key, event) {
    if (event) event.stopPropagation();
    const state = getCardState(key);
    state.logsOpen = !state.logsOpen;
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

// ===== ACCORDÉON LOGS TECHNIQUES (fermé par défaut) =====
function renderLogsAccordion(agentKey, gen, state) {
    if (!gen.logs || !gen.logs.length) return '';

    const logsHtml = gen.logs.map(entry => {
        const time = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '';
        let msg = escapeHtml(entry.message || '');
        if (entry.type === 'prompt' && entry.user_prompt) {
            msg += `<br><span class="agent-card-log-prompt">${escapeHtml(entry.user_prompt)}</span>`;
        }
        if (entry.duration_sec !== undefined && entry.duration_sec !== null) {
            msg += ` (${entry.duration_sec}s`;
            if (entry.tokens && entry.tokens.total) msg += `, ${entry.tokens.total} tokens`;
            msg += ')';
        }
        return `<div class="agent-card-log"><span class="agent-card-log-time">[${time}]</span><span>${msg}</span></div>`;
    }).join('');

    return `
        <div class="agent-card-accordion-toggle" onclick="toggleLogsAccordion('${agentKey}', event)">
            <i class="fas fa-chevron-${state.logsOpen ? 'down' : 'right'}"></i>
            <span>Technical details (prompts, timing, tokens)</span>
        </div>
        <div class="agent-card-logs" style="${state.logsOpen ? '' : 'display:none'}">${logsHtml}</div>
    `;
}

// ===== RÉSULTAT CRÉATIF (texte intégral, jamais tronqué) =====
function renderResultSection(agentKey, gen, liveData, state) {
    if (agentKey === 'showrunner') {
        const synopsis = liveData.project?.synopsis || '';
        const hook = liveData.project?.hook || '';
        if (state.editing) {
            return `
                <div class="agent-card-section">
                    <span class="agent-card-section-label">Hook</span>
                    <input type="text" class="form-input" id="edit-hook-showrunner" value="${escapeHtml(hook)}">
                </div>
                <div class="agent-card-section">
                    <span class="agent-card-section-label">Synopsis</span>
                    <textarea class="form-textarea" id="edit-synopsis-showrunner" rows="6">${escapeHtml(synopsis)}</textarea>
                </div>
            `;
        }
        return `
            <div class="agent-card-section">
                <span class="agent-card-section-label">Hook</span>
                <span class="agent-card-section-value hook">${escapeHtml(hook)}</span>
            </div>
            <div class="agent-card-section">
                <span class="agent-card-section-label">Synopsis</span>
                <span class="agent-card-section-value synopsis">${escapeHtml(synopsis)}</span>
            </div>
        `;
    }

    if (agentKey === 'casting') {
        const chars = liveData.characters || [];
        return `
            <div class="agent-card-section">
                <span class="agent-card-section-label">Characters (${chars.length})</span>
                <div class="character-cards-grid">
                    ${chars.map(c => renderCharacterCard(c)).join('')}
                </div>
            </div>
        `;
    }

    if (agentKey === 'scriptwriter') {
        const eps = liveData.episodes || [];
        if (!eps.length) return '';
        return `
            <div class="agent-card-section">
                <span class="agent-card-section-label">Episodes (${eps.length})</span>
                <div class="character-cards-grid">
                    ${eps.map(ep => renderEpisodeCard(ep, eps.length)).join('')}
                </div>
            </div>
        `;
    }

    if (agentKey === 'character_visualizer') {
        const chars = liveData.characters || [];
        return `
            <div class="agent-card-section">
                ${chars.map(c => renderCharacterImageGroup(c)).join('')}
            </div>
        `;
    }

    if (agentKey === 'location_scout') {
        const locs = liveData.locations || [];
        return `
            <div class="agent-card-section">
                <span class="agent-card-section-label">Locations (${locs.length})</span>
                <div class="character-cards-grid">
                    ${locs.map(l => renderLocationCard(l)).join('')}
                </div>
            </div>
        `;
    }

    if (agentKey === 'location_design') {
        const locs = liveData.locations || [];
        return `
            <div class="agent-card-section">
                ${locs.map(l => renderLocationImageGroup(l)).join('')}
            </div>
        `;
    }

    if (agentKey === 'shot_breakdown') {
        const scenes = liveData.scenes || [];
        const episodes = liveData.episodes || [];
        const byEpisode = {};
        scenes.forEach(s => (byEpisode[s.episode_id] = byEpisode[s.episode_id] || []).push(s));

        return `
            <div class="agent-card-section">
                <span class="agent-card-section-label">Shots (${scenes.length})</span>
                ${Object.entries(byEpisode).map(([epId, shots]) => {
                    const ep = episodes.find(e => e.id == epId);
                    return `
                        <div class="agent-card-section-label" style="margin-top:0.75rem;">${ep ? escapeHtml(ep.title) : 'Episode'}</div>
                        <div class="character-cards-grid">
                            ${shots.map(s => renderSceneCard(s, liveData)).join('')}
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    if (agentKey === 'storyboard_art') {
        const scenes = liveData.scenes || [];
        return `
            <div class="agent-card-section">
                ${scenes.map(s => renderSceneStoryboardGroup(s, liveData)).join('')}
            </div>
        `;
    }
    return '';
}

// ===== IMAGES D'UN PERSONNAGE, REGROUPÉES PAR STYLE =====
const SHEET_MODELS = ['qwen-image-edit-plus', 'qwen-image-edit-max', 'qwen-image-2.0-pro', 'qwen-image-2.0', 'wan2.7-image-pro'];
const DEFAULT_STORYBOARD_MODEL_UI = 'qwen-image-2.0-pro'; // meilleur résultat confirmé sur nos tests
const IMAGE_MODELS = ['wan2.2-t2i-plus', 'wan2.6-t2i', 'wan2.7-image-pro'];
const COVER_MODELS = ['qwen-image-2.0-pro', 'qwen-image-edit-plus', 'qwen-image-edit-max', 'qwen-image-2.0'];

function renderCharacterImageGroup(character) {
    const portraitAssets = (character.assets || []).filter(a => a.asset_type === 'portrait');
    if (!portraitAssets.length) return '';

    const uiKey = `charimg-${character.id}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, promptsOpen: false, regenerating: false, selectedModel: IMAGE_MODELS[0] };
    const ui = cardUiState[uiKey];

    // Regrouper par lot de génération ; le dernier lot est affiché par défaut,
    // les précédents restent consultables via "History" (rien n'est jamais supprimé).
    const batches = {};
    portraitAssets.forEach(a => {
        (batches[a.generation_batch] = batches[a.generation_batch] || []).push(a);
    });
    const batchNumbers = Object.keys(batches).map(Number).sort((a, b) => a - b);
    const latestBatch = batchNumbers[batchNumbers.length - 1];
    const currentImgs = batches[latestBatch];
    const hasSelectedPortrait = portraitAssets.some(a => a.is_selected);

    const imagesHtml = currentImgs.map(img => renderSelectableImage(character.id, img)).join('');

    const historyHtml = ui.historyOpen ? `
        <div class="character-image-history">
            ${batchNumbers.slice(0, -1).reverse().map(bn => `
                <div class="character-image-history-batch">
                    <span class="agent-card-section-label">Batch ${bn}</span>
                    <div class="character-image-grid">
                        ${batches[bn].map(img => renderSelectableImage(character.id, img)).join('')}
                    </div>
                </div>
            `).join('')}
        </div>
    ` : '';

    const promptsHtml = ui.promptsOpen ? `
        <div class="agent-card-logs">
            ${currentImgs.map(img => `
                <div class="agent-card-log">
                    <span class="agent-card-log-time">Proposal ${img.version}${img.model_used === 'user_upload' ? ' (uploaded)' : ''}</span>
                    <span>${img.prompt_used ? escapeHtml(img.prompt_used) : '<em>No prompt (manual upload)</em>'}</span>
                </div>
            `).join('')}
        </div>
    ` : '';

    return `
        <div class="character-card" id="char-images-${character.id}">
            <div class="character-card-header">
                <strong>${escapeHtml(character.name)}</strong>
                <div class="character-card-buttons">
                    <label class="agent-card-btn agent-card-btn-secondary character-upload-btn">
                        <i class="fas fa-upload"></i> Upload your own
                        <input type="file" accept="image/*" style="display:none" onchange="uploadCharacterImage(${character.id}, this.files[0])">
                    </label>
                    <select class="form-input character-sheet-model-select" onchange="setCharacterImageModel(${character.id}, this.value)">
                        ${IMAGE_MODELS.map(m => `<option value="${m}" ${m === ui.selectedModel ? 'selected' : ''}>${m}</option>`).join('')}
                    </select>
                    <button class="agent-card-btn agent-card-btn-secondary" ${ui.regenerating ? 'disabled' : ''} onclick="regenerateCharacterImages(${character.id})">
                        <i class="fas fa-rotate ${ui.regenerating ? 'fa-spin' : ''}"></i> ${ui.regenerating ? 'Generating…' : 'Regenerate'}
                    </button>
                </div>
            </div>
            <div class="character-image-grid">${imagesHtml}</div>
            ${batchNumbers.length > 1 ? `
                <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${character.id}, 'historyOpen', event)">
                    <i class="fas fa-chevron-${ui.historyOpen ? 'down' : 'right'}"></i>
                    <span>Previous batches (${batchNumbers.length - 1})</span>
                </div>
                ${historyHtml}
            ` : ''}
            <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${character.id}, 'promptsOpen', event)">
                <i class="fas fa-chevron-${ui.promptsOpen ? 'down' : 'right'}"></i>
                <span>Prompts used</span>
            </div>
            ${promptsHtml}
            ${renderModelSheetSection(character, hasSelectedPortrait)}
        </div>
    `;
}

// ===== MODEL SHEET (planche de référence turnaround) =====
function renderModelSheetSection(character, hasSelectedPortrait) {
    const sheetAssets = (character.assets || []).filter(a => a.asset_type === 'reference_sheet');
    const uiKey = `sheet-${character.id}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, generating: false, selectedModel: SHEET_MODELS[0] };
    const ui = cardUiState[uiKey];

    const batches = {};
    sheetAssets.forEach(a => (batches[a.generation_batch] = batches[a.generation_batch] || []).push(a));
    const batchNumbers = Object.keys(batches).map(Number).sort((a, b) => a - b);
    const latestBatch = batchNumbers[batchNumbers.length - 1];
    const currentSheets = latestBatch ? batches[latestBatch] : [];

    const historyHtml = ui.historyOpen ? `
        <div class="character-image-history">
            ${batchNumbers.slice(0, -1).reverse().map(bn => `
                <div class="character-image-history-batch">
                    <span class="agent-card-section-label">Batch ${bn} — ${escapeHtml(batches[bn][0].model_used || '')}</span>
                    <div class="character-image-grid">
                        ${batches[bn].map(img => renderSelectableImage(character.id, img)).join('')}
                    </div>
                </div>
            `).join('')}
        </div>
    ` : '';

    return `
        <div class="character-model-sheet-section">
            <div class="agent-card-section-label" style="margin-top:0.75rem;">Model Sheet</div>
            <div class="character-card-buttons character-sheet-controls">
                <select class="form-input character-sheet-model-select" onchange="setCharacterSheetModel(${character.id}, this.value)">
                    ${SHEET_MODELS.map(m => `<option value="${m}" ${m === ui.selectedModel ? 'selected' : ''}>${m}</option>`).join('')}
                </select>
                <label class="agent-card-btn agent-card-btn-secondary character-upload-btn">
                    <i class="fas fa-upload"></i> Upload sheet
                    <input type="file" accept="image/*" style="display:none" onchange="uploadCharacterSheet(${character.id}, this.files[0])">
                </label>
                <button class="agent-card-btn agent-card-btn-primary" ${!hasSelectedPortrait || ui.generating ? 'disabled' : ''}
                        title="${!hasSelectedPortrait ? 'Select a portrait first' : ''}"
                        onclick="buildCharacterSheet(${character.id})">
                    <i class="fas fa-image ${ui.generating ? 'fa-spin' : ''}"></i> ${ui.generating ? 'Building…' : 'Build Model Sheet'}
                </button>
            </div>
            ${currentSheets.length
                ? `<div class="character-image-grid">${currentSheets.map(s => renderSelectableImage(character.id, s)).join('')}</div>`
                : `<p class="agent-card-summary-text">No Model Sheet yet. ${hasSelectedPortrait ? '' : 'Select a portrait above first.'}</p>`}
            ${batchNumbers.length > 1 ? `
                <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${character.id}, 'historyOpen', event, 'sheet-${character.id}')">
                    <i class="fas fa-chevron-${ui.historyOpen ? 'down' : 'right'}"></i>
                    <span>Previous Model Sheets (${batchNumbers.length - 1})</span>
                </div>
                ${historyHtml}
            ` : ''}
        </div>
    `;
}

function setCharacterSheetModel(characterId, model) {
    const uiKey = `sheet-${characterId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, generating: false, selectedModel: SHEET_MODELS[0] };
    cardUiState[uiKey].selectedModel = model;
}

async function buildCharacterSheet(characterId) {
    const uiKey = `sheet-${characterId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, generating: false, selectedModel: SHEET_MODELS[0] };
    cardUiState[uiKey].generating = true;
    if (lastGenerationData) renderTimeline(lastGenerationData);

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/characters/${characterId}/generate-sheet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ model: cardUiState[uiKey].selectedModel })
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Model Sheet generation failed');
        }
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Model Sheet generation error:', e);
        alert(e.message || 'Failed to build Model Sheet. Try a different model.');
    } finally {
        cardUiState[uiKey].generating = false;
        if (lastGenerationData) renderTimeline(lastGenerationData);
    }
}

async function uploadCharacterSheet(characterId, file) {
    if (!file) return;
    try {
        const token = localStorage.getItem('access_token');
        const formData = new FormData();
        formData.append('file', file);
        formData.append('asset_type', 'reference_sheet');
        const response = await fetch(`/api/characters/${characterId}/upload-image`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        if (!response.ok) throw new Error('Upload failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Model Sheet upload error:', e);
        alert('Failed to upload Model Sheet.');
    }
}

function renderSelectableImage(characterId, img) {
    if (img.status !== 'completed') {
        return `<div class="character-proposal-img character-proposal-failed"><i class="fas fa-triangle-exclamation"></i></div>`;
    }
    return `
        <div class="character-proposal-wrap ${img.is_selected ? 'selected' : 'dimmed'}" onclick="selectCharacterImage(${characterId}, ${img.id})">
            <img src="${escapeHtml(img.url)}" class="character-proposal-img" alt="proposal" title="Proposal ${img.version}${img.model_used === 'user_upload' ? ' — uploaded' : ''}">
            <button class="character-proposal-zoom" onclick="openImageLightbox('${escapeHtml(img.url)}', event)" title="Enlarge">
                <i class="fas fa-magnifying-glass-plus"></i>
            </button>
            <button class="character-proposal-delete" onclick="deleteCharacterImage(${characterId}, ${img.id}, event)" title="Delete this image permanently">
                <i class="fas fa-trash"></i>
            </button>
            ${img.is_selected ? '<span class="character-proposal-check"><i class="fas fa-check"></i> Selected</span>' : ''}
        </div>
    `;
}

async function deleteCharacterImage(characterId, assetId, event) {
    if (event) event.stopPropagation();
    if (!confirm('Delete this image permanently? This cannot be undone.')) return;
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/characters/${characterId}/images/${assetId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Delete failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Image delete error:', e);
        alert('Failed to delete image.');
    }
}

// ===== LIGHTBOX (agrandir une image sans la sélectionner) =====
function openImageLightbox(url, event) {
    if (event) event.stopPropagation();
    closeImageLightbox();

    const overlay = document.createElement('div');
    overlay.id = 'image-lightbox-overlay';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) closeImageLightbox(); };

    overlay.innerHTML = `
        <div class="lightbox-panel">
            <button class="modal-close-btn lightbox-close-btn" onclick="closeImageLightbox()"><i class="fas fa-xmark"></i></button>
            <img src="${escapeHtml(url)}" class="lightbox-image" alt="enlarged">
        </div>
    `;
    document.body.appendChild(overlay);
    document.addEventListener('keydown', _lightboxEscHandler);
}

function _lightboxEscHandler(e) {
    if (e.key === 'Escape') closeImageLightbox();
}

function closeImageLightbox() {
    const overlay = document.getElementById('image-lightbox-overlay');
    if (overlay) overlay.remove();
    document.removeEventListener('keydown', _lightboxEscHandler);
}

// Ce que "Generate All" fait réellement à chaque type de contenu — pour un
// rapport honnête plutôt qu'un simple "tout sera perdu" générique.
const STEP_REGEN_INFO = {
    showrunner: 'The synopsis & hook will be overwritten with a new version (previous version viewable via History).',
    casting: 'All current characters will be deleted and regenerated from scratch (previous version viewable via History).',
    scriptwriter: 'All episodes will be deleted and rewritten from scratch (previous version viewable via History).',
    location_scout: 'All current locations will be deleted and regenerated from scratch (previous version viewable via History).',
    character_visualizer: 'A new image batch will be added for every character — previous batches stay available, but this still uses new credits.',
    location_design: 'A new image batch will be added for every location — previous batches stay available, but this still uses new credits.',
    storyboard_art: 'A new storyboard batch will be added for every shot — previous batches stay available, but this still uses new credits.',
};

function _showGenerateAllReportModal(alreadyDone) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.id = 'generate-all-report-overlay';
        overlay.className = 'modal-overlay';

        const rows = alreadyDone.map(a => `
            <div class="agent-card-log">
                <span class="agent-card-log-time">${escapeHtml(a.label)}</span>
                <span>${escapeHtml(STEP_REGEN_INFO[a.key] || 'This will be regenerated.')}</span>
            </div>
        `).join('');

        const cleanup = (result) => {
            overlay.remove();
            resolve(result);
        };

        overlay.innerHTML = `
            <div class="lightbox-panel" style="max-width: 34rem; background:#0f172a; border-radius:0.75rem; padding:1.5rem; text-align:left; display:block;">
                <h3 style="color:#fca5a5; margin-top:0;"><i class="fas fa-triangle-exclamation"></i> Generate All — please review before continuing</h3>
                <p class="agent-card-summary-text">The following step(s) already have generated content:</p>
                <div class="agent-card-logs" style="margin:0.75rem 0;">${rows}</div>
                <p class="agent-card-summary-text">
                    <strong>This will consume real API credits again</strong> for everything selected above —
                    the cost multiplies with each additional step you regenerate.
                </p>
                <p class="agent-card-summary-text">
                    Prefer to improve just one piece instead? Cancel here, then use the
                    <strong>Regenerate</strong> button on that specific card — it won't touch anything else.
                </p>
                <div class="agent-card-actions" style="margin-top:1rem;">
                    <button class="agent-card-btn agent-card-btn-secondary" id="generate-all-report-cancel">Cancel</button>
                    <button class="agent-card-btn agent-card-btn-primary" id="generate-all-report-proceed">Generate Anyway</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        document.getElementById('generate-all-report-cancel').onclick = () => cleanup(false);
        document.getElementById('generate-all-report-proceed').onclick = () => cleanup(true);
        overlay.onclick = (e) => { if (e.target === overlay) cleanup(false); };
    });
}

function toggleCharacterUiFlag(characterId, flag, event, customKey) {
    if (event) event.stopPropagation();
    const uiKey = customKey || `charimg-${characterId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, promptsOpen: false, regenerating: false, generating: false, selectedModel: SHEET_MODELS[0] };
    cardUiState[uiKey][flag] = !cardUiState[uiKey][flag];
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function selectCharacterImage(characterId, assetId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/characters/${characterId}/select-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ asset_id: assetId })
        });
        if (!response.ok) throw new Error('Selection failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Image selection error:', e);
        alert('Failed to select image.');
    }
}

function setCharacterImageModel(characterId, model) {
    const uiKey = `charimg-${characterId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, promptsOpen: false, regenerating: false, selectedModel: IMAGE_MODELS[0] };
    cardUiState[uiKey].selectedModel = model;
}

async function regenerateCharacterImages(characterId) {
    const uiKey = `charimg-${characterId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, promptsOpen: false, regenerating: false, selectedModel: IMAGE_MODELS[0] };
    cardUiState[uiKey].regenerating = true;
    if (lastGenerationData) renderTimeline(lastGenerationData);

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/characters/${characterId}/generate-images`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ model: cardUiState[uiKey].selectedModel })
        });
        if (!response.ok) throw new Error('Generation failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Character image regenerate error:', e);
        alert('Failed to regenerate images for this character.');
    } finally {
        cardUiState[uiKey].regenerating = false;
        if (lastGenerationData) renderTimeline(lastGenerationData);
    }
}

async function uploadCharacterImage(characterId, file) {
    if (!file) return;
    try {
        const token = localStorage.getItem('access_token');
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`/api/characters/${characterId}/upload-image`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        if (!response.ok) throw new Error('Upload failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Character image upload error:', e);
        alert('Failed to upload image.');
    }
}

// ===== UNE FICHE PERSONNAGE (avec édition individuelle) =====
// ===== UNE CARTE ÉPISODE (avec édition individuelle) =====
function renderEpisodeCard(ep, totalEpisodes) {
    const editing = !!cardUiState[`ep-${ep.id}`]?.editing;
    const epLabel = totalEpisodes > 1 ? `Episode ${ep.episode_number}` : 'Script';

    if (editing) {
        return `
            <div class="character-card editing" id="episode-card-${ep.id}">
                <input type="text" class="form-input" id="ep-title-${ep.id}" value="${escapeHtml(ep.title)}" placeholder="Title">
                <textarea class="form-textarea" id="ep-script-${ep.id}" rows="14" placeholder="Script">${escapeHtml(ep.script_content)}</textarea>
                <div class="agent-card-actions">
                    <button class="agent-card-btn agent-card-btn-primary" onclick="saveEpisodeEdit(${ep.id})">Save</button>
                    <button class="agent-card-btn agent-card-btn-secondary" onclick="cancelEpisodeEdit(${ep.id})">Cancel</button>
                </div>
            </div>
        `;
    }

    return `
        <div class="character-card" id="episode-card-${ep.id}">
            <div class="character-card-header">
                <strong>${epLabel} — ${escapeHtml(ep.title)}</strong>
                ${ep.ends_with_cliffhanger ? '<span class="stale-badge" style="background:rgba(219,39,119,0.15);color:#f9a8d4;">Cliffhanger</span>' : ''}
                <div class="character-card-buttons">
                    <button class="agent-card-btn agent-card-btn-secondary character-edit-btn" onclick="startEpisodeEdit(${ep.id})"><i class="fas fa-pen"></i> Edit</button>
                </div>
            </div>
            <div class="agent-card-section-value note script-full">${escapeHtml(ep.script_content)}</div>
            ${ep.cliffhanger_description ? `<div class="agent-card-section"><span class="agent-card-section-label">Cliffhanger</span><span class="agent-card-section-value">${escapeHtml(ep.cliffhanger_description)}</span></div>` : ''}
        </div>
    `;
}

function startEpisodeEdit(epId) {
    cardUiState[`ep-${epId}`] = { editing: true };
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

function cancelEpisodeEdit(epId) {
    cardUiState[`ep-${epId}`] = { editing: false };
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function saveEpisodeEdit(epId) {
    const title = document.getElementById(`ep-title-${epId}`).value.trim();
    const script_content = document.getElementById(`ep-script-${epId}`).value.trim();
    if (!script_content) {
        alert("Script can't be empty. Edit the text or click Cancel to discard.");
        return;
    }

    try {
        const token = localStorage.getItem('access_token');
        const projectId = getCurrentProjectId();
        const response = await fetch(`/api/projects/${projectId}/episodes/${epId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ title, script_content })
        });
        if (!response.ok) throw new Error('Save failed');

        cardUiState[`ep-${epId}`] = { editing: false };
        const data = await fetchGenerationStatus(projectId);
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Episode save error:', e);
        alert('Failed to save episode.');
    }
}

function renderCharacterCard(c) {
    const editing = !!cardUiState[`char-${c.id}`]?.editing;

    if (editing) {
        return `
            <div class="character-card editing" id="character-card-${c.id}">
                <input type="text" class="form-input" id="char-name-${c.id}" value="${escapeHtml(c.name)}" placeholder="Name">
                <input type="text" class="form-input" id="char-alias-${c.id}" value="${escapeHtml(c.alias || '')}" placeholder="Alias">
                <div class="form-row">
                    <input type="text" class="form-input" id="char-role-${c.id}" value="${escapeHtml(c.role || '')}" placeholder="Role">
                    <input type="number" class="form-input" id="char-age-${c.id}" value="${c.age ?? ''}" placeholder="Age">
                </div>
                <textarea class="form-textarea" id="char-visual-${c.id}" rows="2" placeholder="Visual trait">${escapeHtml(c.visual_trait || '')}</textarea>
                <textarea class="form-textarea" id="char-objective-${c.id}" rows="2" placeholder="Objective">${escapeHtml(c.objective || '')}</textarea>
                <textarea class="form-textarea" id="char-secret-${c.id}" rows="2" placeholder="Secret">${escapeHtml(c.secret || '')}</textarea>
                <input type="text" class="form-input" id="char-traits-${c.id}" value="${escapeHtml((c.traits || []).join(', '))}" placeholder="Traits (comma separated)">
                <textarea class="form-textarea" id="char-arc-${c.id}" rows="2" placeholder="Arc potential (season 2)">${escapeHtml(c.arc_potential || '')}</textarea>
                <div class="agent-card-actions">
                    <button class="agent-card-btn agent-card-btn-primary" onclick="saveCharacterEdit(${c.id})">Save</button>
                    <button class="agent-card-btn agent-card-btn-secondary" onclick="cancelCharacterEdit(${c.id})">Cancel</button>
                </div>
            </div>
        `;
    }

    return `
        <div class="character-card" id="character-card-${c.id}">
            <div class="character-card-header">
                <strong>${escapeHtml(c.name)}</strong>${c.alias ? ` "${escapeHtml(c.alias)}"` : ''} — ${escapeHtml(c.role || '')}${c.age ? ` (${c.age})` : ''}
                <div class="character-card-buttons">
                    <button class="agent-card-btn agent-card-btn-secondary character-edit-btn" onclick="startCharacterEdit(${c.id})"><i class="fas fa-pen"></i> Edit</button>
                    <button class="agent-card-btn agent-card-btn-danger character-edit-btn" onclick="deleteCharacter(${c.id}, '${escapeHtml(c.name).replace(/'/g, "\\'")}')"><i class="fas fa-trash"></i> Delete</button>
                </div>
            </div>
            ${c.visual_trait ? `<div class="agent-card-section"><span class="agent-card-section-label">Visual</span><span class="agent-card-section-value">${escapeHtml(c.visual_trait)}</span></div>` : ''}
            ${c.objective ? `<div class="agent-card-section"><span class="agent-card-section-label">Objective</span><span class="agent-card-section-value">${escapeHtml(c.objective)}</span></div>` : ''}
            ${c.secret ? `<div class="agent-card-section"><span class="agent-card-section-label">Secret</span><span class="agent-card-section-value">${escapeHtml(c.secret)}</span></div>` : ''}
            ${c.traits && c.traits.length ? `<div class="agent-card-section"><span class="agent-card-section-label">Traits</span><span class="agent-card-section-value">${escapeHtml(c.traits.join(', '))}</span></div>` : ''}
            ${c.arc_potential ? `<div class="agent-card-section"><span class="agent-card-section-label">Arc Potential</span><span class="agent-card-section-value">${escapeHtml(c.arc_potential)}</span></div>` : ''}
        </div>
    `;
}

function startCharacterEdit(charId) {
    cardUiState[`char-${charId}`] = { editing: true };
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function deleteCharacter(charId, charName) {
    if (!confirm(`Delete character "${charName}"? This cannot be undone.`)) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/characters/${charId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Delete failed');

        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Character delete error:', e);
        alert('Failed to delete character.');
    }
}

function cancelCharacterEdit(charId) {
    cardUiState[`char-${charId}`] = { editing: false };
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function saveCharacterEdit(charId) {
    const traitsRaw = document.getElementById(`char-traits-${charId}`).value;
    const payload = {
        name: document.getElementById(`char-name-${charId}`).value,
        alias: document.getElementById(`char-alias-${charId}`).value || null,
        role: document.getElementById(`char-role-${charId}`).value,
        age: parseInt(document.getElementById(`char-age-${charId}`).value) || null,
        visual_trait: document.getElementById(`char-visual-${charId}`).value,
        objective: document.getElementById(`char-objective-${charId}`).value,
        secret: document.getElementById(`char-secret-${charId}`).value,
        traits: traitsRaw ? traitsRaw.split(',').map(t => t.trim()).filter(Boolean) : [],
        arc_potential: document.getElementById(`char-arc-${charId}`).value,
    };

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/characters/${charId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error('Save failed');

        cardUiState[`char-${charId}`] = { editing: false };
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Character save error:', e);
        alert('Failed to save character.');
    }
}

// ===== FICHE LIEU (miroir de la fiche personnage) =====
function renderLocationCard(l) {
    const editing = !!cardUiState[`loc-${l.id}`]?.editing;

    if (editing) {
        return `
            <div class="character-card editing" id="location-card-${l.id}">
                <input type="text" class="form-input" id="loc-name-${l.id}" value="${escapeHtml(l.name)}" placeholder="Name">
                <textarea class="form-textarea" id="loc-description-${l.id}" rows="2" placeholder="Description">${escapeHtml(l.description || '')}</textarea>
                <input type="text" class="form-input" id="loc-mood-${l.id}" value="${escapeHtml(l.mood || '')}" placeholder="Mood">
                <textarea class="form-textarea" id="loc-visual-${l.id}" rows="2" placeholder="Key visual details">${escapeHtml(l.key_visual_details || '')}</textarea>
                <div class="agent-card-actions">
                    <button class="agent-card-btn agent-card-btn-primary" onclick="saveLocationEdit(${l.id})">Save</button>
                    <button class="agent-card-btn agent-card-btn-secondary" onclick="cancelLocationEdit(${l.id})">Cancel</button>
                </div>
            </div>
        `;
    }

    return `
        <div class="character-card" id="location-card-${l.id}">
            <div class="character-card-header">
                <strong>${escapeHtml(l.name)}</strong>
                <div class="character-card-buttons">
                    <button class="agent-card-btn agent-card-btn-secondary character-edit-btn" onclick="startLocationEdit(${l.id})"><i class="fas fa-pen"></i> Edit</button>
                    <button class="agent-card-btn agent-card-btn-danger character-edit-btn" onclick="deleteLocation(${l.id}, '${escapeHtml(l.name).replace(/'/g, "\\'")}')"><i class="fas fa-trash"></i> Delete</button>
                </div>
            </div>
            ${l.description ? `<div class="agent-card-section"><span class="agent-card-section-label">Description</span><span class="agent-card-section-value">${escapeHtml(l.description)}</span></div>` : ''}
            ${l.mood ? `<div class="agent-card-section"><span class="agent-card-section-label">Mood</span><span class="agent-card-section-value">${escapeHtml(l.mood)}</span></div>` : ''}
            ${l.key_visual_details ? `<div class="agent-card-section"><span class="agent-card-section-label">Key Visual Details</span><span class="agent-card-section-value">${escapeHtml(l.key_visual_details)}</span></div>` : ''}
        </div>
    `;
}

function startLocationEdit(locId) {
    cardUiState[`loc-${locId}`] = { editing: true };
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function deleteLocation(locId, locName) {
    if (!confirm(`Delete location "${locName}"? This cannot be undone.`)) return;
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/locations/${locId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Delete failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Location delete error:', e);
        alert('Failed to delete location.');
    }
}

function cancelLocationEdit(locId) {
    cardUiState[`loc-${locId}`] = { editing: false };
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function saveLocationEdit(locId) {
    const payload = {
        name: document.getElementById(`loc-name-${locId}`).value,
        description: document.getElementById(`loc-description-${locId}`).value,
        mood: document.getElementById(`loc-mood-${locId}`).value,
        key_visual_details: document.getElementById(`loc-visual-${locId}`).value,
    };
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/locations/${locId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error('Save failed');

        cardUiState[`loc-${locId}`] = { editing: false };
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Location save error:', e);
        alert('Failed to save location.');
    }
}

// ===== IMAGES DE LIEU (miroir de renderCharacterImageGroup, plus simple : pas de Model Sheet) =====
function renderLocationImageGroup(location) {
    const allAssets = (location.assets || []).filter(a => a.asset_type === 'reference');
    if (!allAssets.length) return '';

    const uiKey = `locimg-${location.id}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, promptsOpen: false, regenerating: false, selectedModel: IMAGE_MODELS[0] };
    const ui = cardUiState[uiKey];

    const batches = {};
    allAssets.forEach(a => (batches[a.generation_batch] = batches[a.generation_batch] || []).push(a));
    const batchNumbers = Object.keys(batches).map(Number).sort((a, b) => a - b);
    const latestBatch = batchNumbers[batchNumbers.length - 1];
    const currentImgs = batches[latestBatch];

    const imagesHtml = currentImgs.map(img => renderSelectableLocationImage(location.id, img)).join('');

    const historyHtml = ui.historyOpen ? `
        <div class="character-image-history">
            ${batchNumbers.slice(0, -1).reverse().map(bn => `
                <div class="character-image-history-batch">
                    <span class="agent-card-section-label">Batch ${bn}</span>
                    <div class="character-image-grid">
                        ${batches[bn].map(img => renderSelectableLocationImage(location.id, img)).join('')}
                    </div>
                </div>
            `).join('')}
        </div>
    ` : '';

    const promptsHtml = ui.promptsOpen ? `
        <div class="agent-card-logs">
            ${currentImgs.map(img => `
                <div class="agent-card-log">
                    <span class="agent-card-log-time">Proposal ${img.version}${img.model_used === 'user_upload' ? ' (uploaded)' : ''}</span>
                    <span>${img.prompt_used ? escapeHtml(img.prompt_used) : '<em>No prompt (manual upload)</em>'}</span>
                </div>
            `).join('')}
        </div>
    ` : '';

    return `
        <div class="character-card" id="loc-images-${location.id}">
            <div class="character-card-header">
                <strong>${escapeHtml(location.name)}</strong>
                <div class="character-card-buttons">
                    <label class="agent-card-btn agent-card-btn-secondary character-upload-btn">
                        <i class="fas fa-upload"></i> Upload your own
                        <input type="file" accept="image/*" style="display:none" onchange="uploadLocationImage(${location.id}, this.files[0])">
                    </label>
                    <select class="form-input character-sheet-model-select" onchange="setLocationImageModel(${location.id}, this.value)">
                        ${IMAGE_MODELS.map(m => `<option value="${m}" ${m === ui.selectedModel ? 'selected' : ''}>${m}</option>`).join('')}
                    </select>
                    <button class="agent-card-btn agent-card-btn-secondary" ${ui.regenerating ? 'disabled' : ''} onclick="regenerateLocationImages(${location.id})">
                        <i class="fas fa-rotate ${ui.regenerating ? 'fa-spin' : ''}"></i> ${ui.regenerating ? 'Generating…' : 'Regenerate'}
                    </button>
                </div>
            </div>
            <div class="character-image-grid">${imagesHtml}</div>
            ${batchNumbers.length > 1 ? `
                <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${location.id}, 'historyOpen', event, 'locimg-${location.id}')">
                    <i class="fas fa-chevron-${ui.historyOpen ? 'down' : 'right'}"></i>
                    <span>Previous batches (${batchNumbers.length - 1})</span>
                </div>
                ${historyHtml}
            ` : ''}
            <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${location.id}, 'promptsOpen', event, 'locimg-${location.id}')">
                <i class="fas fa-chevron-${ui.promptsOpen ? 'down' : 'right'}"></i>
                <span>Prompts used</span>
            </div>
            ${promptsHtml}
        </div>
    `;
}

function renderSelectableLocationImage(locationId, img) {
    if (img.status !== 'completed') {
        return `<div class="character-proposal-img character-proposal-failed"><i class="fas fa-triangle-exclamation"></i></div>`;
    }
    return `
        <div class="character-proposal-wrap ${img.is_selected ? 'selected' : 'dimmed'}" onclick="selectLocationImage(${locationId}, ${img.id})">
            <img src="${escapeHtml(img.url)}" class="character-proposal-img" alt="proposal" title="Proposal ${img.version}${img.model_used === 'user_upload' ? ' — uploaded' : ''}">
            <button class="character-proposal-zoom" onclick="openImageLightbox('${escapeHtml(img.url)}', event)" title="Enlarge">
                <i class="fas fa-magnifying-glass-plus"></i>
            </button>
            ${img.is_selected ? '<span class="character-proposal-check"><i class="fas fa-check"></i> Selected</span>' : ''}
        </div>
    `;
}

async function selectLocationImage(locationId, assetId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/locations/${locationId}/select-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ asset_id: assetId })
        });
        if (!response.ok) throw new Error('Selection failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Location image selection error:', e);
        alert('Failed to select image.');
    }
}

function setLocationImageModel(locationId, model) {
    const uiKey = `locimg-${locationId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, promptsOpen: false, regenerating: false, selectedModel: IMAGE_MODELS[0] };
    cardUiState[uiKey].selectedModel = model;
}

async function regenerateLocationImages(locationId) {
    const uiKey = `locimg-${locationId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, promptsOpen: false, regenerating: false, selectedModel: IMAGE_MODELS[0] };
    cardUiState[uiKey].regenerating = true;
    if (lastGenerationData) renderTimeline(lastGenerationData);

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/locations/${locationId}/generate-images`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ model: cardUiState[uiKey].selectedModel })
        });
        if (!response.ok) throw new Error('Generation failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Location image regenerate error:', e);
        alert('Failed to regenerate images for this location.');
    } finally {
        cardUiState[uiKey].regenerating = false;
        if (lastGenerationData) renderTimeline(lastGenerationData);
    }
}

async function uploadLocationImage(locationId, file) {
    if (!file) return;
    try {
        const token = localStorage.getItem('access_token');
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`/api/locations/${locationId}/upload-image`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        if (!response.ok) throw new Error('Upload failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Location image upload error:', e);
        alert('Failed to upload image.');
    }
}

// ===== FICHE PLAN (Shot Breakdown) — lecture seule + édition texte =====
function renderSceneCard(s, liveData) {
    const editing = !!cardUiState[`scene-${s.id}`]?.editing;
    const loc = (liveData.locations || []).find(l => l.id === s.location_id);
    const chars = (liveData.characters || []).filter(c => (s.character_ids || []).includes(c.id));

    if (editing) {
        return `
            <div class="character-card editing" id="scene-card-${s.id}">
                <textarea class="form-textarea" id="scene-description-${s.id}" rows="2" placeholder="Description">${escapeHtml(s.description || '')}</textarea>
                <input type="text" class="form-input" id="scene-camera-${s.id}" value="${escapeHtml(s.camera_movement || '')}" placeholder="Camera movement">
                <div class="form-row">
                    <input type="text" class="form-input" id="scene-mood-${s.id}" value="${escapeHtml(s.mood || '')}" placeholder="Mood">
                    <input type="number" class="form-input" id="scene-duration-${s.id}" value="${s.duration_seconds ?? 10}" placeholder="Duration (s)" max="10" step="0.5">
                </div>
                <textarea class="form-textarea" id="scene-dialogue-${s.id}" rows="2" placeholder="Dialogue">${escapeHtml(s.dialogue || '')}</textarea>
                <div class="agent-card-actions">
                    <button class="agent-card-btn agent-card-btn-primary" onclick="saveSceneEdit(${s.id})">Save</button>
                    <button class="agent-card-btn agent-card-btn-secondary" onclick="cancelSceneEdit(${s.id})">Cancel</button>
                </div>
            </div>
        `;
    }

    return `
        <div class="character-card" id="scene-card-${s.id}">
            <div class="character-card-header">
                <strong>Shot ${s.number}</strong>${s.is_cliffhanger ? ' <span class="stale-badge" style="background:rgba(219,39,119,0.15);color:#f9a8d4;">Cliffhanger</span>' : ''}
                <div class="character-card-buttons">
                    <button class="agent-card-btn agent-card-btn-secondary character-edit-btn" onclick="startSceneEdit(${s.id})"><i class="fas fa-pen"></i> Edit</button>
                </div>
            </div>
            <div class="agent-card-section"><span class="agent-card-section-label">Description</span><span class="agent-card-section-value">${escapeHtml(s.description || '')}</span></div>
            ${s.camera_movement ? `<div class="agent-card-section"><span class="agent-card-section-label">Camera</span><span class="agent-card-section-value">${escapeHtml(s.camera_movement)}</span></div>` : ''}
            ${s.mood ? `<div class="agent-card-section"><span class="agent-card-section-label">Mood</span><span class="agent-card-section-value">${escapeHtml(s.mood)}</span></div>` : ''}
            ${s.dialogue ? `<div class="agent-card-section"><span class="agent-card-section-label">Dialogue</span><span class="agent-card-section-value">${escapeHtml(s.dialogue)}</span></div>` : ''}
            <div class="agent-card-section"><span class="agent-card-section-label">Duration</span><span class="agent-card-section-value">${s.duration_seconds}s</span></div>
            <div class="agent-card-section"><span class="agent-card-section-label">Characters</span><span class="agent-card-section-value">${chars.length ? escapeHtml(chars.map(c => c.name).join(', ')) : '—'}</span></div>
            <div class="agent-card-section"><span class="agent-card-section-label">Location</span><span class="agent-card-section-value">${loc ? escapeHtml(loc.name) : '—'}</span></div>
        </div>
    `;
}

function startSceneEdit(sceneId) {
    cardUiState[`scene-${sceneId}`] = { editing: true };
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

function cancelSceneEdit(sceneId) {
    cardUiState[`scene-${sceneId}`] = { editing: false };
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function saveSceneEdit(sceneId) {
    const payload = {
        description: document.getElementById(`scene-description-${sceneId}`).value,
        camera_movement: document.getElementById(`scene-camera-${sceneId}`).value,
        mood: document.getElementById(`scene-mood-${sceneId}`).value,
        dialogue: document.getElementById(`scene-dialogue-${sceneId}`).value || null,
        duration_seconds: Math.min(parseFloat(document.getElementById(`scene-duration-${sceneId}`).value) || 10, 10),
    };
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/scenes/${sceneId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error('Save failed');

        cardUiState[`scene-${sceneId}`] = { editing: false };
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Scene save error:', e);
        alert('Failed to save shot.');
    }
}

// ===== STORYBOARD D'UN PLAN (miroir simplifié : 1 image, choix de modèle) =====
function renderSceneStoryboardGroup(scene, liveData) {
    const allAssets = (scene.assets || []).filter(a => a.asset_type === 'storyboard');
    const uiKey = `sbimg-${scene.id}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, generating: false, selectedModel: DEFAULT_STORYBOARD_MODEL_UI, usePromptDirector: true };
    const ui = cardUiState[uiKey];

    const batches = {};
    allAssets.forEach(a => (batches[a.generation_batch] = batches[a.generation_batch] || []).push(a));
    const batchNumbers = Object.keys(batches).map(Number).sort((a, b) => a - b);
    const latestBatch = batchNumbers[batchNumbers.length - 1];
    const currentImgs = latestBatch ? batches[latestBatch] : [];
    const hasAnyImage = allAssets.some(a => a.status === 'completed');

    const historyHtml = ui.historyOpen ? `
        <div class="character-image-history">
            ${batchNumbers.slice(0, -1).reverse().map(bn => `
                <div class="character-image-history-batch">
                    <span class="agent-card-section-label">Batch ${bn} — ${escapeHtml(batches[bn][0].model_used || '')}</span>
                    <div class="character-image-grid">
                        ${batches[bn].map(img => renderSelectableSceneImage(scene.id, img)).join('')}
                    </div>
                </div>
            `).join('')}
        </div>
    ` : '';

    const loc = (liveData.locations || []).find(l => l.id === scene.location_id);
    const chars = (liveData.characters || []).filter(c => (scene.character_ids || []).includes(c.id));

    return `
        <div class="character-model-sheet-section storyboard-row" style="border-top:none; margin-top:0;">
            <div class="storyboard-row-info">
                <div class="agent-card-section-label">Shot ${scene.number}${scene.is_cliffhanger ? ' — Cliffhanger' : ''}</div>
                <div class="agent-card-section"><span class="agent-card-section-value">${escapeHtml(scene.description || '')}</span></div>
                ${scene.camera_movement ? `<div class="agent-card-section"><span class="agent-card-section-label">Camera</span><span class="agent-card-section-value">${escapeHtml(scene.camera_movement)}</span></div>` : ''}
                ${scene.mood ? `<div class="agent-card-section"><span class="agent-card-section-label">Mood</span><span class="agent-card-section-value">${escapeHtml(scene.mood)}</span></div>` : ''}
                ${scene.dialogue ? `<div class="agent-card-section"><span class="agent-card-section-label">Dialogue</span><span class="agent-card-section-value">${escapeHtml(scene.dialogue)}</span></div>` : ''}
                <div class="agent-card-section"><span class="agent-card-section-label">Duration</span><span class="agent-card-section-value">${scene.duration_seconds}s</span></div>
                <div class="agent-card-section"><span class="agent-card-section-label">Characters</span><span class="agent-card-section-value">${chars.length ? escapeHtml(chars.map(c => c.name).join(', ')) : '—'}</span></div>
                <div class="agent-card-section"><span class="agent-card-section-label">Location</span><span class="agent-card-section-value">${loc ? escapeHtml(loc.name) : '—'}</span></div>
            </div>
            <div class="storyboard-row-visual">
                <div class="character-card-buttons character-sheet-controls">
                    <select class="form-input character-sheet-model-select" onchange="setSceneStoryboardModel(${scene.id}, this.value)">
                        ${SHEET_MODELS.map(m => `<option value="${m}" ${m === ui.selectedModel ? 'selected' : ''}>${m}</option>`).join('')}
                    </select>
                    <select class="form-input character-sheet-model-select" onchange="setSceneStoryboardMode(${scene.id}, this.value)" title="Number of storyboard panels">
                        <option value="one_frame" ${(ui.mode || 'one_frame') === 'one_frame' ? 'selected' : ''}>One frame</option>
                        <option value="2x2" ${ui.mode === '2x2' ? 'selected' : ''}>2×2 grid</option>
                        <option value="3x3" ${ui.mode === '3x3' ? 'selected' : ''}>3×3 grid</option>
                        <option value="auto" ${ui.mode === 'auto' ? 'selected' : ''}>Auto (agent decides)</option>
                    </select>
                    <label class="agent-card-btn agent-card-btn-secondary" style="cursor:pointer; gap:0.4rem;" title="Uses vision to look at the actual character/location reference images before designing panels — more accurate, costs one extra API call">
                        <input type="checkbox" ${ui.usePromptDirector !== false ? 'checked' : ''} onchange="setSceneStoryboardPromptDirector(${scene.id}, this.checked)" style="margin:0;">
                        Prompt Director
                    </label>
                    <label class="agent-card-btn agent-card-btn-secondary character-upload-btn">
                        <i class="fas fa-upload"></i> Upload
                        <input type="file" accept="image/*" style="display:none" onchange="uploadSceneStoryboard(${scene.id}, this.files[0])">
                    </label>
                    <button class="agent-card-btn agent-card-btn-primary" ${ui.generating ? 'disabled' : ''}
                            onclick="buildSceneStoryboard(${scene.id})">
                        <i class="fas fa-image ${ui.generating ? 'fa-spin' : ''}"></i> ${ui.generating ? 'Building…' : (hasAnyImage ? 'Regenerate' : 'Generate')}
                    </button>
                </div>
                ${currentImgs.length
                    ? `<div class="character-image-grid">${currentImgs.map(img => renderSelectableSceneImage(scene.id, img)).join('')}</div>`
                    : `<p class="agent-card-summary-text">No storyboard yet.</p>`}
                ${batchNumbers.length > 1 ? `
                    <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${scene.id}, 'historyOpen', event, 'sbimg-${scene.id}')">
                        <i class="fas fa-chevron-${ui.historyOpen ? 'down' : 'right'}"></i>
                        <span>Previous storyboards (${batchNumbers.length - 1})</span>
                    </div>
                    ${historyHtml}
                ` : ''}
                ${currentImgs.length ? `
                    <div class="agent-card-accordion-toggle" onclick="toggleCharacterUiFlag(${scene.id}, 'promptsOpen', event, 'sbimg-${scene.id}')">
                        <i class="fas fa-chevron-${ui.promptsOpen ? 'down' : 'right'}"></i>
                        <span>Prompt used</span>
                    </div>
                    ${ui.promptsOpen ? `
                        <div class="agent-card-logs">
                            ${currentImgs.map(img => `
                                <div class="agent-card-log">
                                    <span class="agent-card-log-time">${img.model_used === 'user_upload' ? 'Uploaded' : escapeHtml(img.model_used || '')}</span>
                                    <span>${img.prompt_used ? escapeHtml(img.prompt_used) : '<em>No prompt (manual upload)</em>'}</span>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                ` : ''}
            </div>
        </div>
    `;
}

function renderSelectableSceneImage(sceneId, img) {
    if (img.status !== 'completed') {
        return `<div class="character-proposal-img character-proposal-failed"><i class="fas fa-triangle-exclamation"></i></div>`;
    }
    return `
        <div class="character-proposal-wrap ${img.is_selected ? 'selected' : 'dimmed'}" onclick="selectSceneImage(${sceneId}, ${img.id})">
            <img src="${escapeHtml(img.url)}" class="character-proposal-img" alt="storyboard" title="${img.model_used === 'user_upload' ? 'Uploaded' : escapeHtml(img.model_used || '')}">
            <button class="character-proposal-zoom" onclick="openImageLightbox('${escapeHtml(img.url)}', event)" title="Enlarge">
                <i class="fas fa-magnifying-glass-plus"></i>
            </button>
            ${img.is_selected ? '<span class="character-proposal-check"><i class="fas fa-check"></i> Selected</span>' : ''}
        </div>
    `;
}

function setSceneStoryboardModel(sceneId, model) {
    const uiKey = `sbimg-${sceneId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, generating: false, selectedModel: DEFAULT_STORYBOARD_MODEL_UI, usePromptDirector: true };
    cardUiState[uiKey].selectedModel = model;
}

function setSceneStoryboardMode(sceneId, mode) {
    const uiKey = `sbimg-${sceneId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, generating: false, selectedModel: DEFAULT_STORYBOARD_MODEL_UI, usePromptDirector: true };
    cardUiState[uiKey].mode = mode;
}

function setSceneStoryboardPromptDirector(sceneId, enabled) {
    const uiKey = `sbimg-${sceneId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, generating: false, selectedModel: DEFAULT_STORYBOARD_MODEL_UI, usePromptDirector: true };
    cardUiState[uiKey].usePromptDirector = enabled;
}

async function selectSceneImage(sceneId, assetId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/scenes/${sceneId}/select-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ asset_id: assetId })
        });
        if (!response.ok) throw new Error('Selection failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Storyboard selection error:', e);
        alert('Failed to select image.');
    }
}

async function buildSceneStoryboard(sceneId) {
    const uiKey = `sbimg-${sceneId}`;
    if (!cardUiState[uiKey]) cardUiState[uiKey] = { historyOpen: false, generating: false, selectedModel: DEFAULT_STORYBOARD_MODEL_UI, usePromptDirector: true };
    cardUiState[uiKey].generating = true;
    if (lastGenerationData) renderTimeline(lastGenerationData);

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/scenes/${sceneId}/generate-storyboard`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({
                model: cardUiState[uiKey].selectedModel,
                mode: cardUiState[uiKey].mode || 'one_frame',
                use_prompt_director: cardUiState[uiKey].usePromptDirector !== false
            })
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Storyboard generation failed');
        }
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Storyboard generation error:', e);
        alert(e.message || 'Failed to build storyboard.');
    } finally {
        cardUiState[uiKey].generating = false;
        if (lastGenerationData) renderTimeline(lastGenerationData);
    }
}

async function uploadSceneStoryboard(sceneId, file) {
    if (!file) return;
    try {
        const token = localStorage.getItem('access_token');
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`/api/scenes/${sceneId}/upload-image`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        if (!response.ok) throw new Error('Upload failed');
        const data = await fetchGenerationStatus(getCurrentProjectId());
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Storyboard upload error:', e);
        alert('Failed to upload image.');
    }
}

// ===== BOUTONS EDIT / SAVE / REGENERATE (Showrunner & Scriptwriter) =====
function renderActionButtons(agent) {
    const state = getCardState(agent.key);
    const section = SKILL_TO_STEP[agent.key]; // 'synopsis' | 'casting' | 'script'
    const exportButtons = `
        <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('${section}', 'pdf')" title="Export this section as PDF"><i class="fas fa-file-pdf"></i></button>
        <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('${section}', 'markdown')" title="Export this section as Markdown"><i class="fas fa-file-lines"></i></button>
    `;

    // La carte Casting gère l'édition personnage par personnage (voir renderCharacterCard),
    // et Scriptwriter gère l'édition épisode par épisode (voir renderEpisodeCard).
    if (agent.key === 'casting') {
        return `
            <div class="agent-card-actions">
                <button class="agent-card-btn agent-card-btn-secondary" onclick="regenerateStep('${agent.key}', false)">
                    <i class="fas fa-rotate"></i> Regenerate All Characters
                </button>
                <label class="agent-card-cascade-label">
                    <input type="checkbox" id="cascade-${agent.key}"> also regenerate Script
                </label>
                ${exportButtons}
            </div>
        `;
    }

    if (agent.key === 'scriptwriter') {
        return `
            <div class="agent-card-actions">
                <button class="agent-card-btn agent-card-btn-secondary" onclick="regenerateStep('${agent.key}', false)">
                    <i class="fas fa-rotate"></i> Regenerate All Episodes
                </button>
                ${exportButtons}
            </div>
        `;
    }

    if (agent.key === 'character_visualizer') {
        return `
            <div class="agent-card-actions">
                <button class="agent-card-btn agent-card-btn-secondary" onclick="regenerateStep('${agent.key}', false)">
                    <i class="fas fa-rotate"></i> Regenerate All Images
                </button>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('images', 'pdf')" title="Export as PDF"><i class="fas fa-file-pdf"></i></button>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('images', 'markdown')" title="Export as Markdown"><i class="fas fa-file-lines"></i></button>
            </div>
        `;
    }

    if (agent.key === 'location_scout') {
        return `
            <div class="agent-card-actions">
                <button class="agent-card-btn agent-card-btn-secondary" onclick="regenerateStep('${agent.key}', false)">
                    <i class="fas fa-rotate"></i> Regenerate All Locations
                </button>
                <label class="agent-card-cascade-label">
                    <input type="checkbox" id="cascade-${agent.key}"> also regenerate Location Design
                </label>
            </div>
        `;
    }

    if (agent.key === 'location_design') {
        return `
            <div class="agent-card-actions">
                <button class="agent-card-btn agent-card-btn-secondary" onclick="regenerateStep('${agent.key}', false)">
                    <i class="fas fa-rotate"></i> Regenerate All Location Images
                </button>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('locations', 'pdf')" title="Export as PDF"><i class="fas fa-file-pdf"></i></button>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('locations', 'markdown')" title="Export as Markdown"><i class="fas fa-file-lines"></i></button>
            </div>
        `;
    }

    if (agent.key === 'shot_breakdown') {
        return `
            <div class="agent-card-actions">
                <button class="agent-card-btn agent-card-btn-secondary" onclick="regenerateStep('${agent.key}', false)">
                    <i class="fas fa-rotate"></i> Regenerate All Shots
                </button>
                <label class="agent-card-cascade-label">
                    <input type="checkbox" id="cascade-${agent.key}"> also regenerate Storyboard Art
                </label>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('storyboard', 'pdf')" title="Export as PDF (includes storyboard images if generated)"><i class="fas fa-file-pdf"></i></button>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('storyboard', 'markdown')" title="Export as Markdown"><i class="fas fa-file-lines"></i></button>
            </div>
        `;
    }

    if (agent.key === 'storyboard_art') {
        return `
            <div class="agent-card-actions">
                <button class="agent-card-btn agent-card-btn-secondary" onclick="regenerateStep('${agent.key}', false)">
                    <i class="fas fa-rotate"></i> Regenerate All Storyboards
                </button>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('storyboard', 'pdf')" title="Export as PDF"><i class="fas fa-file-pdf"></i></button>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="downloadExport('storyboard', 'markdown')" title="Export as Markdown"><i class="fas fa-file-lines"></i></button>
            </div>
        `;
    }

    if (state.editing) {
        return `
            <div class="agent-card-actions">
                <button class="agent-card-btn agent-card-btn-primary" onclick="saveCardEdit('${agent.key}')">Save</button>
                <button class="agent-card-btn agent-card-btn-secondary" onclick="cancelCardEdit('${agent.key}')">Cancel</button>
            </div>
        `;
    }

    const showCascade = agent.key === 'showrunner';
    return `
        <div class="agent-card-actions">
            <button class="agent-card-btn agent-card-btn-secondary" onclick="startCardEdit('${agent.key}')"><i class="fas fa-pen"></i> Edit</button>
            <button class="agent-card-btn agent-card-btn-secondary" onclick="regenerateStep('${agent.key}', false)"><i class="fas fa-rotate"></i> Regenerate</button>
            ${showCascade ? `<label class="agent-card-cascade-label"><input type="checkbox" id="cascade-${agent.key}"> also regenerate following steps</label>` : ''}
            ${exportButtons}
        </div>
    `;
}

function startCardEdit(key) {
    getCardState(key).editing = true;
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

function cancelCardEdit(key) {
    getCardState(key).editing = false;
    if (lastGenerationData) renderTimeline(lastGenerationData);
}

async function saveCardEdit(key) {
    const token = localStorage.getItem('access_token');
    const projectId = getCurrentProjectId();

    try {
        if (key === 'showrunner') {
            const synopsis = document.getElementById('edit-synopsis-showrunner').value.trim();
            const hook = document.getElementById('edit-hook-showrunner').value.trim();
            if (!synopsis) {
                alert("Synopsis can't be empty. Edit the text or click Cancel to discard.");
                return;
            }
            const response = await fetch(`/api/projects/${projectId}/synopsis`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ synopsis, hook })
            });
            if (!response.ok) throw new Error('Save failed');
        }

        // Note : Scriptwriter n'utilise plus l'édition au niveau carte — chaque
        // épisode s'édite individuellement (voir saveEpisodeEdit).

        getCardState(key).editing = false;
        const data = await fetchGenerationStatus(projectId);
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Save error:', e);
        alert('Failed to save changes.');
    }
}

// ===== RÉGÉNÉRER UNE ÉTAPE (avec cascade optionnelle) =====
async function regenerateStep(skillName, forceCascade) {
    const projectId = getCurrentProjectId();
    const cascadeCheckbox = document.getElementById(`cascade-${skillName}`);
    const cascade = forceCascade || (cascadeCheckbox ? cascadeCheckbox.checked : false);

    try {
        // Même raison que pour Generate : s'assurer que le backend voit bien
        // les réglages actuels du formulaire (ex: nombre d'épisodes changé
        // juste avant de cliquer Regenerate) avant de relancer quoi que ce soit.
        await saveProjectSettingsSilently(projectId);

        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/projects/${projectId}/regenerate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ skill_name: skillName, cascade })
        });
        if (!response.ok) throw new Error('Failed to start regeneration');

        // Un nouveau cycle démarre pour cette carte : on la ré-ouvrira
        // automatiquement à sa prochaine complétion.
        getCardState(skillName).initialized = false;
        getCardState(skillName).expanded = true;

        setHeaderStatus('Generating', 'status-running');
        startPollingGenerationStatus(projectId);
    } catch (e) {
        console.error('   ❌ Regenerate error:', e);
        alert('Failed to start regeneration.');
    }
}

// ===== HISTORIQUE DES VERSIONS (lecture seule + restauration) =====
const AGENT_LABELS = { showrunner: 'Showrunner Agent', casting: 'Casting Agent', scriptwriter: 'Scriptwriter Agent' };

async function openVersionHistory(skillName, event) {
    if (event) event.stopPropagation();
    const projectId = getCurrentProjectId();
    const token = localStorage.getItem('access_token');

    let data;
    try {
        const response = await fetch(`/api/projects/${projectId}/history/${skillName}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Failed to load history');
        data = await response.json();
    } catch (e) {
        console.error('   ❌ History load error:', e);
        alert('Failed to load version history.');
        return;
    }

    renderVersionHistoryModal(skillName, data.versions || []);
}

function renderVersionHistoryModal(skillName, versions) {
    closeVersionHistory(); // au cas où un modal serait déjà ouvert

    const overlay = document.createElement('div');
    overlay.id = 'version-history-overlay';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) closeVersionHistory(); };

    const versionsHtml = versions.map((v, i) => `
        <div class="version-item">
            <div class="version-item-header">
                <span class="version-badge">${i === 0 ? 'Current' : `Version ${v.version_number}`}</span>
                <span class="version-date">${v.created_at ? new Date(v.created_at).toLocaleString() : ''}</span>
                ${i === 0 ? '' : `<button class="agent-card-btn agent-card-btn-primary version-restore-btn" onclick="restoreVersion('${skillName}', ${v.execution_id})">Restore this version</button>`}
            </div>
            <div class="version-item-summary">${escapeHtml(v.summary)}</div>
            <div class="version-item-detail">${renderVersionDetail(skillName, v.result)}</div>
        </div>
    `).join('');

    overlay.innerHTML = `
        <div class="modal-panel">
            <div class="modal-header">
                <span><i class="fas fa-clock-rotate-left"></i> Version History — ${AGENT_LABELS[skillName] || skillName}</span>
                <button class="modal-close-btn" onclick="closeVersionHistory()"><i class="fas fa-xmark"></i></button>
            </div>
            <div class="modal-body">
                ${versions.length ? versionsHtml : '<p class="agent-card-summary">No previous versions yet.</p>'}
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
}

function renderVersionDetail(skillName, result) {
    if (!result) return '';
    if (skillName === 'showrunner') {
        return `
            <div class="agent-card-section"><span class="agent-card-section-label">Hook</span><span class="agent-card-section-value hook">${escapeHtml(result.hook || '')}</span></div>
            <div class="agent-card-section"><span class="agent-card-section-label">Synopsis</span><span class="agent-card-section-value synopsis">${escapeHtml(result.synopsis || '')}</span></div>
        `;
    }
    if (skillName === 'casting') {
        const chars = result.characters || [];
        return chars.map(c => `
            <div class="character-card">
                <div class="character-card-header"><strong>${escapeHtml(c.name || '')}</strong>${c.alias ? ` "${escapeHtml(c.alias)}"` : ''} — ${escapeHtml(c.role || '')}${c.age ? ` (${c.age})` : ''}</div>
                ${c.visual_trait ? `<div class="agent-card-section"><span class="agent-card-section-label">Visual</span><span class="agent-card-section-value">${escapeHtml(c.visual_trait)}</span></div>` : ''}
                ${c.objective ? `<div class="agent-card-section"><span class="agent-card-section-label">Objective</span><span class="agent-card-section-value">${escapeHtml(c.objective)}</span></div>` : ''}
                ${c.secret ? `<div class="agent-card-section"><span class="agent-card-section-label">Secret</span><span class="agent-card-section-value">${escapeHtml(c.secret)}</span></div>` : ''}
            </div>
        `).join('');
    }
    if (skillName === 'scriptwriter') {
        const eps = result.episodes || [];
        return eps.map(ep => `
            <div class="character-card">
                <div class="character-card-header">
                    <strong>${eps.length > 1 ? `Episode ${ep.episode_number} — ` : ''}${escapeHtml(ep.title || '')}</strong>
                    ${ep.ends_with_cliffhanger ? '<span class="stale-badge" style="background:rgba(219,39,119,0.15);color:#f9a8d4;">Cliffhanger</span>' : ''}
                </div>
                <div class="agent-card-section-value note script-full">${escapeHtml(ep.script_content || '')}</div>
            </div>
        `).join('');
    }
    if (agentKey === 'character_visualizer') {
        const chars = liveData.characters || [];
        const totalImages = chars.reduce((sum, c) => sum + (c.assets?.filter(a => a.status === 'completed').length || 0), 0);
        return `<span class="agent-card-summary-text">${totalImages} image(s) across ${chars.length} character(s)</span>`;
    }
    return '';
}

function closeVersionHistory() {
    const overlay = document.getElementById('version-history-overlay');
    if (overlay) overlay.remove();
}

async function restoreVersion(skillName, executionId) {
    if (!confirm('Restore this version? It will replace the current content of this section.')) return;

    const projectId = getCurrentProjectId();
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/projects/${projectId}/restore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ skill_name: skillName, execution_id: executionId })
        });
        if (!response.ok) throw new Error('Restore failed');

        closeVersionHistory();
        const data = await fetchGenerationStatus(projectId);
        if (data) renderTimeline(data);
    } catch (e) {
        console.error('   ❌ Restore error:', e);
        alert('Failed to restore version.');
    }
}

function getCurrentProjectId() {
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.length - 1];
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
}

// ===== CHARGER LES DONNÉES DU PROJET =====
async function loadProjectData(projectId) {
    console.log(`\n📥 loadProjectData(${projectId}) called`);
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/projects/${projectId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const project = await response.json();
            console.log('   ✅ Project loaded:', project);
            
            // Remplir les champs
            document.getElementById('gen-title').value = project.title || '';
            document.getElementById('gen-idea').value = project.idea || '';
            document.getElementById('gen-season').value = project.seasons || 1;
            document.getElementById('gen-episodes').value = project.episodes_per_season || 1;
            document.getElementById('gen-duration').value = project.duration_seconds || 60;
            if (project.aspect_ratio) {
                document.getElementById('gen-aspect-ratio').value = project.aspect_ratio;
                window.aspectRatioManuallySet = true; // valeur déjà choisie, ne plus l'écraser
            }
            const formatCheckbox = document.getElementById('gen-project-format');
            if (formatCheckbox) formatCheckbox.checked = (project.project_format === 'serie');

            // Sélectionner le type de projet
            if (project.type) {
                window.selectedProjectType = project.type;
                selectProjectType(project.type);
                console.log('   ✓ Project type loaded:', project.type);
            }
            
            console.log('   Fields populated:');
            console.log('      - Title:', project.title);
            console.log('      - Idea:', project.idea);
            console.log('      - Type:', project.type);
            console.log('      - Seasons:', project.seasons);
            console.log('      - Duration:', project.duration_seconds);
            
            // Sélectionner les styles
            if (project.narrative_style) {
                const chip = document.querySelector(`.narrative-chip[data-value="${project.narrative_style}"]`);
                if (chip) {
                    chip.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-300');
                    chip.classList.add('bg-purple-600', 'border-purple-500', 'text-white');
                    console.log('   ✓ Narrative style selected:', project.narrative_style);
                }
            }
            
            if (project.genres) {
                project.genres.forEach(genre => {
                    const chip = document.querySelector(`.genre-chip[data-value="${genre}"]`);
                    if (chip) {
                        chip.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-300');
                        chip.classList.add('bg-purple-600', 'border-purple-500', 'text-white');
                    }
                });
                console.log('   ✓ Genres selected:', project.genres);
            }
            
            if (project.visual_styles) {
                project.visual_styles.forEach(style => {
                    const chip = document.querySelector(`.visual-chip[data-value="${style}"]`);
                    if (chip) {
                        chip.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-300');
                        chip.classList.add('bg-purple-600', 'border-purple-500', 'text-white');
                    }
                });
                console.log('   ✓ Visual styles selected:', project.visual_styles);
            }
            
            // Charger les images
            if (project.reference_image_world) {
                window.uploadedImages.world = project.reference_image_world;
                displayImagePreview(project.reference_image_world, 'world');
                console.log('   ✓ World image loaded:', project.reference_image_world);
            }
            
            if (project.reference_image_character) {
                window.uploadedImages.character = project.reference_image_character;
                displayImagePreview(project.reference_image_character, 'character');
                console.log('   ✓ Character image loaded:', project.reference_image_character);
            }
            
            if (project.world_style_prompt) {
                document.getElementById('gen-world-style').value = project.world_style_prompt;
                console.log('   ✓ World style loaded');
            }
            if (project.character_style_prompt) {
                document.getElementById('gen-character-style').value = project.character_style_prompt;
                console.log('   ✓ Character style loaded');
            }
            
            // Mettre à jour le header
            document.getElementById('header-project-title').textContent = project.title;
            
        } else {
            console.error('   ❌ Failed to load project:', response.status);
        }
    } catch (e) {
        console.error('   ❌ Error loading project:', e);
    }
}

// ===== UPLOAD D'IMAGE =====
async function handleImageUpload(event, type) {
    console.log(`\n handleImageUpload() - Type: ${type}`);
    const file = event.target.files[0];
    if (!file) return;
    
    console.log('   File:', file.name, 'Size:', file.size, 'bytes');
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('kind', type); // 'world' ou 'character' -> déclenche l'extraction de style côté serveur
        
        const token = localStorage.getItem('access_token');
        const uploadResponse = await fetch('/api/upload/image', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        if (uploadResponse.ok) {
            const uploadData = await uploadResponse.json();
            console.log('   ✅ Upload successful:', uploadData);
            
            // Initialiser uploadedImages si nécessaire
            if (!window.uploadedImages) {
                window.uploadedImages = {};
            }
            
            // Sauvegarder l'URL
            window.uploadedImages[type] = uploadData.url;
            console.log('   Image URL saved:', uploadData.url);
            
            // Afficher l'aperçu IMMÉDIATEMENT
            displayImagePreview(uploadData.url, type);

            // Remplir automatiquement la zone de style correspondante
            if (uploadData.extracted_style) {
                const styleField = document.getElementById(type === 'world' ? 'gen-world-style' : 'gen-character-style');
                if (styleField) styleField.value = uploadData.extracted_style;
            }
            
        } else {
            const error = await uploadResponse.json();
            console.error('   ❌ Upload failed:', error);
            alert('Failed to upload image');
        }
    } catch (e) {
        console.error('   ❌ Upload error:', e);
    }
}

// ===== AFFICHER APERÇU IMAGE =====
function displayImagePreview(imageUrl, type) {
    const preview = document.getElementById('gen-ref-preview');
    if (!preview) {
        console.error('Preview container not found!');
        return;
    }
    
    console.log('   Displaying preview for', type, ':', imageUrl);
    
    // Créer le conteneur si n'existe pas
    let container = document.getElementById(`preview-${type}`);
    if (!container) {
        container = document.createElement('div');
        container.id = `preview-${type}`;
        container.className = 'ref-preview-item';
        preview.appendChild(container);
    }
    
    // Vider le contenu existant
    container.innerHTML = '';
    
    // Créer l'image
    const img = document.createElement('img');
    img.src = imageUrl.startsWith('/') ? imageUrl : imageUrl;
    img.alt = `${type} reference`;
    
    // Créer le label
    const label = document.createElement('span');
    label.className = 'ref-preview-label';
    label.textContent = type === 'world' ? '🌍 World' : '👤 Char';
    
    // Ajouter au container
    container.appendChild(img);
    container.appendChild(label);
    
    console.log('   ✅ Preview displayed successfully');
}

// ===== BARRE DE PROGRESSION GLOBALE (Production Timeline) =====
function updateProgress(percent) {
    const progressText = document.getElementById('dash-progress-text');
    const progressBar = document.getElementById('dash-progress-bar');

    if (progressText) progressText.textContent = `${percent}%`;
    if (progressBar) progressBar.style.width = `${percent}%`;
}