// ===== DASHBOARD LOGIC =====
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Dashboard initialized');
    
    // Check authentication
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.log(' No token, redirecting to login');
        window.location.href = '/';
        return;
    }
    
    console.log('✅ Token found:', token.substring(0, 20) + '...');
    
    // Load user info
    loadUserInfo(token);
    
    // Load projects
    loadProjects(token);
    
    // Setup event listeners
    setupEventListeners(token);
});

// ===== LOAD USER INFO =====
function loadUserInfo(token) {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const email = payload.sub;
        document.getElementById('user-name').textContent = email.split('@')[0];
        document.getElementById('dropdown-email').textContent = email;
        document.getElementById('user-avatar').textContent = email.charAt(0).toUpperCase();
        console.log('✅ User loaded:', email);
    } catch (error) {
        console.error('❌ Error decoding token:', error);
    }
}

// ===== LOAD PROJECTS =====
async function loadProjects(token) {
    const grid = document.getElementById('projects-grid');
    const emptyState = document.getElementById('empty-state');
    
    try {
        const response = await fetch('/api/projects/', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        console.log(' Projects response status:', response.status);
        
        if (response.status === 401) {
            console.error('❌ Token invalid, redirecting to login');
            localStorage.removeItem('access_token');
            window.location.href = '/';
            return;
        }
        
        if (response.ok) {
            const projects = await response.json();
            console.log(' Projects loaded:', projects.length);
            
            if (projects.length === 0) {
                grid.classList.add('hidden');
                emptyState.classList.remove('hidden');
            } else {
                grid.classList.remove('hidden');
                emptyState.classList.add('hidden');
                renderProjects(projects);
            }
        } else {
            console.error('❌ Failed to load projects');
            grid.innerHTML = '<p class="text-red-400 text-center">Failed to load projects</p>';
        }
    } catch (error) {
        console.error('❌ Error loading projects:', error);
        grid.innerHTML = '<p class="text-red-400 text-center">Network error</p>';
    }
}


// ===== RENDER PROJECTS (AVEC 2 BOUTONS) =====
function renderProjects(projects) {
    const grid = document.getElementById('projects-grid');
    if (!grid) {
        console.error('❌ projects-grid element not found!');
        return;
    }
    
    grid.innerHTML = '';
    
    projects.forEach(project => {
        const card = document.createElement('div');
        card.className = 'card-hover bg-gradient-to-br from-purple-900/40 to-slate-800/60 rounded-xl p-6 border border-purple-700/30';
        
        const typeIcon = project.type === 'series' ? 'fa-tv' : 'fa-film';
        const statusColor = project.status === 'active' || project.status === 'ready' || project.status === 'completed' ? 'green' : 
                           project.status === 'generating' ? 'blue' : 'yellow';
        
        card.innerHTML = `
            <div class="flex items-start justify-between mb-4">
                <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center">
                    <i class="fas ${typeIcon} text-white text-xl"></i>
                </div>
                <span class="text-xs bg-${statusColor}-600/30 text-${statusColor}-300 px-2 py-1 rounded capitalize">${project.status}</span>
            </div>
            <h4 class="text-lg font-bold text-white mb-2">${project.title}</h4>
            <p class="text-sm text-slate-400 mb-3">${project.type === 'series' ? `${project.seasons || 1} seasons` : `${project.duration_minutes || 'N/A'} min`}</p>
            <div class="flex flex-wrap gap-2 mb-4">
                ${(project.genres || []).slice(0, 3).map(g => `<span class="text-xs bg-purple-600/30 text-purple-300 px-2 py-1 rounded">${g}</span>`).join('')}
            </div>
            <div class="flex items-center justify-between text-xs text-slate-500 mb-4">
                <span><i class="fas fa-calendar mr-1"></i>${new Date(project.created_at).toLocaleDateString()}</span>
            </div>
            
            <!-- ACTIONS -->
            <div class="flex gap-2 mt-4 pt-4 border-t border-purple-700/20">
                <button onclick="window.location.href='/generator/${project.id}'" 
                    class="flex-1 px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-xs font-medium transition-all text-white"
                    title="Ouvrir le générateur IA">
                    <i class="fas fa-robot mr-1"></i> Generator
                </button>
                <button onclick="window.location.href='/studio/${project.id}'" 
                    class="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs font-medium transition-all text-white"
                    title="Ouvrir le studio de production">
                    <i class="fas fa-video mr-1"></i> Studio
                </button>
                <button onclick="deleteProject(${project.id}, '${project.title.replace(/'/g, "\\'")}')"
                    class="px-3 py-2 bg-red-900/30 hover:bg-red-900/60 text-red-300 rounded-lg text-xs font-medium transition-all"
                    title="Delete project">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        grid.appendChild(card);
    });
}

// ===== SUPPRIMER UN PROJET =====
async function deleteProject(projectId, projectTitle) {
    if (!confirm(`Delete "${projectTitle}"? This will permanently remove the project, its characters, episodes and generation history. This cannot be undone.`)) return;

    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/projects/${projectId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Delete failed');

        // Recharger la liste des projets
        if (typeof loadProjects === 'function') {
            loadProjects(token);
        } else {
            window.location.reload();
        }
    } catch (e) {
        console.error('❌ Project delete error:', e);
        alert('Failed to delete project.');
    }
}
// ===== GLOBAL VARIABLES =====
let selectedType = 'short_drama';
let selectedGenres = [];
let selectedStyles = [];
let selectedNarrativeStyle = '';
let uploadedImages = { world: null, character: null };
let extractedStylePrompt = '';

// ===== SETUP EVENT LISTENERS =====
function setupEventListeners(token) {
    console.log('️ Setting up event listeners...');
    
    // Logout
    document.getElementById('btn-logout').addEventListener('click', function() {
        localStorage.removeItem('access_token');
        window.location.href = '/';
    });
    
    // Modal controls
    const modal = document.getElementById('project-modal');
    const btnCreate = document.getElementById('btn-create-project');
    const btnCreateFirst = document.getElementById('btn-create-first');
    const btnClose = document.getElementById('btn-close-modal');
    const btnCancel = document.getElementById('btn-cancel-modal');
    const btnSaveDraft = document.getElementById('btn-save-draft');
    const btnCreateSubmit = document.getElementById('btn-create-project-submit');
    
    function openModal() {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
    
    function closeModal() {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
    
    if (btnCreate) btnCreate.addEventListener('click', openModal);
    if (btnCreateFirst) btnCreateFirst.addEventListener('click', openModal);
    if (btnClose) btnClose.addEventListener('click', closeModal);
    if (btnCancel) btnCancel.addEventListener('click', closeModal);
    
    // Close modal on overlay click
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeModal();
        });
    }
    
    // Type toggle
    const typeBtns = document.querySelectorAll('.type-btn');
    const seriesFields = document.getElementById('series-fields');
    const filmFields = document.getElementById('film-fields');
    
    typeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            if (this.disabled) return;
            
            typeBtns.forEach(b => {
                b.classList.remove('active', 'bg-purple-600', 'border-purple-500', 'text-white');
                b.classList.add('bg-slate-800', 'border-slate-700', 'text-slate-400');
            });
            
            this.classList.add('active', 'bg-purple-600', 'border-purple-500', 'text-white');
            this.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-400');
            
            selectedType = this.dataset.type;
            
            if (selectedType === 'series') {
                if (seriesFields) seriesFields.classList.remove('hidden');
                if (filmFields) filmFields.classList.add('hidden');
            } else {
                if (seriesFields) seriesFields.classList.add('hidden');
                if (filmFields) filmFields.classList.remove('hidden');
            }
        });
    });
    
    // Genre selection (max 3)
    const genreChips = document.querySelectorAll('.genre-chip');
    genreChips.forEach(chip => {
        chip.addEventListener('click', function() {
            const genre = this.dataset.genre;
            
            if (this.classList.contains('selected')) {
                this.classList.remove('selected', 'bg-purple-600', 'border-purple-500', 'text-white');
                this.classList.add('bg-slate-800', 'border-slate-700', 'text-slate-300');
                selectedGenres = selectedGenres.filter(g => g !== genre);
            } else {
                if (selectedGenres.length >= 3) {
                    alert('Maximum 3 genres allowed');
                    return;
                }
                this.classList.add('selected', 'bg-purple-600', 'border-purple-500', 'text-white');
                this.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-300');
                selectedGenres.push(genre);
            }
        });
    });
    
    // Visual Style selection (multiple)
    const styleChips = document.querySelectorAll('.style-chip');
    styleChips.forEach(chip => {
        chip.addEventListener('click', function() {
            const style = this.dataset.style;
            
            if (this.classList.contains('selected')) {
                this.classList.remove('selected', 'bg-purple-600', 'border-purple-500', 'text-white');
                this.classList.add('bg-slate-800', 'border-slate-700', 'text-slate-300');
                selectedStyles = selectedStyles.filter(s => s !== style);
            } else {
                this.classList.add('selected', 'bg-purple-600', 'border-purple-500', 'text-white');
                this.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-300');
                selectedStyles.push(style);
            }
        });
    });
    
    // Narrative Style selection (single)
    const narrativeStyleChips = document.querySelectorAll('.narrative-style-chip');
    narrativeStyleChips.forEach(chip => {
        chip.addEventListener('click', function() {
            narrativeStyleChips.forEach(c => {
                c.classList.remove('bg-purple-600', 'border-purple-500', 'text-white');
                c.classList.add('bg-slate-800', 'border-slate-700', 'text-slate-300');
            });
            
            this.classList.remove('bg-slate-800', 'border-slate-700', 'text-slate-300');
            this.classList.add('bg-purple-600', 'border-purple-500', 'text-white');
            selectedNarrativeStyle = this.dataset.style;
        });
    });
    
    // Image upload handlers
    const worldRefInput = document.getElementById('world-ref-input');
    const characterRefInput = document.getElementById('character-ref-input');
    
    if (worldRefInput) {
        worldRefInput.addEventListener('change', function() {
            handleImageUpload(this, 'world');
        });
    }
    
    if (characterRefInput) {
        characterRefInput.addEventListener('change', function() {
            handleImageUpload(this, 'character');
        });
    }
    
    // Advanced mode toggle
    const advancedModeToggle = document.getElementById('advanced-mode-toggle');
    const simpleModeInfo = document.getElementById('simple-mode-info');
    const advancedWorkflowSteps = document.getElementById('advanced-workflow-steps');
    
    if (advancedModeToggle) {
        advancedModeToggle.addEventListener('change', function() {
            const isAdvanced = this.checked;
            if (isAdvanced) {
                if (simpleModeInfo) simpleModeInfo.classList.add('hidden');
                if (advancedWorkflowSteps) advancedWorkflowSteps.classList.remove('hidden');
            } else {
                if (simpleModeInfo) simpleModeInfo.classList.remove('hidden');
                if (advancedWorkflowSteps) advancedWorkflowSteps.classList.add('hidden');
            }
        });
    }
    
    // Workflow steps with dependencies
    const workflowSteps = document.querySelectorAll('.workflow-step');
    const stepIndicators = document.querySelectorAll('.step-indicator');
    
    const stepDependencies = {
        'synopsis': [],
        'script': ['synopsis'],
        'casting': ['script'],
        'character_images': ['casting']
    };
    
    workflowSteps.forEach(step => {
        step.addEventListener('change', function() {
            const stepName = this.dataset.step;
            const isChecked = this.checked;
            
            if (isChecked) {
                const deps = stepDependencies[stepName];
                deps.forEach(dep => {
                    const depCheckbox = document.querySelector(`.workflow-step[data-step="${dep}"]`);
                    if (depCheckbox) {
                        depCheckbox.checked = true;
                        depCheckbox.disabled = true;
                    }
                });
            }
            
            updateStepIndicators();
        });
    });
    
    function updateStepIndicators() {
        const checkedSteps = Array.from(workflowSteps)
            .filter(step => step.checked)
            .map(step => step.dataset.step);
        
        stepIndicators.forEach(indicator => {
            const stepName = indicator.dataset.step;
            if (checkedSteps.includes(stepName)) {
                indicator.classList.remove('bg-slate-700', 'text-slate-400');
                indicator.classList.add('bg-purple-600', 'text-white');
            } else {
                indicator.classList.add('bg-slate-700', 'text-slate-400');
                indicator.classList.remove('bg-purple-600', 'text-white');
            }
        });
    }
    
    // Save Draft button
    if (btnSaveDraft) {
        btnSaveDraft.addEventListener('click', async function() {
            console.log('💾 Save Draft clicked');
            await saveProject(token, 'draft');
        });
    }
    
    // Create Project button
    if (btnCreateSubmit) {
        btnCreateSubmit.addEventListener('click', async function() {
            console.log('🚀 Create Project clicked');
            await saveProject(token, 'active');
        });
    }
    
    // Refresh projects
    const btnRefresh = document.getElementById('btn-refresh-projects');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', function() {
            loadProjects(token);
        });
    }
    
    console.log('✅ All dashboard event listeners attached');
}

// ===== IMAGE UPLOAD HANDLERS =====
function handleImageUpload(input, type) {
    const file = input.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        uploadedImages[type] = e.target.result;
        updateImagePreview();
        extractStyleFromImage(e.target.result);
    };
    reader.readAsDataURL(file);
}

function updateImagePreview() {
    const container = document.getElementById('uploaded-images-preview');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (uploadedImages.world) {
        const div = document.createElement('div');
        div.className = 'relative w-20 h-20 rounded overflow-hidden border-2 border-purple-500';
        div.innerHTML = `
            <img src="${uploadedImages.world}" class="w-full h-full object-cover">
            <div class="absolute top-0 left-0 bg-purple-600 text-[8px] text-white px-1">World</div>
        `;
        container.appendChild(div);
    }
    
    if (uploadedImages.character) {
        const div = document.createElement('div');
        div.className = 'relative w-20 h-20 rounded overflow-hidden border-2 border-purple-500';
        div.innerHTML = `
            <img src="${uploadedImages.character}" class="w-full h-full object-cover">
            <div class="absolute top-0 left-0 bg-purple-600 text-[8px] text-white px-1">Character</div>
        `;
        container.appendChild(div);
    }
}

async function extractStyleFromImage(imageData) {
    // TODO: Real API call to StyleExtractorAgent
    const simulatedStyle = "Dark gothic aesthetic, deep shadows, cinematic lighting, moody atmosphere";
    extractedStylePrompt = simulatedStyle;
    
    const styleContainer = document.getElementById('extracted-style-container');
    const stylePrompt = document.getElementById('extracted-style-prompt');
    
    if (styleContainer) styleContainer.classList.remove('hidden');
    if (stylePrompt) stylePrompt.value = simulatedStyle;
}

// ===== SAVE PROJECT FUNCTION =====
// ===== SAVE PROJECT FUNCTION (AVEC GÉNÉRATION AI) =====
async function saveProject(token, status) {
    const title = document.getElementById('project-title').value;
    const idea = document.getElementById('project-idea').value;
    const synopsis = document.getElementById('project-synopsis').value;
    
    if (!title) {
        alert('Please enter a project title');
        return;
    }
    
    if (selectedGenres.length === 0) {
        alert('Please select at least one genre');
        return;
    }
    
    // Récupérer les étapes workflow
    const workflowSteps = document.querySelectorAll('.workflow-step:checked');
    const selectedSteps = Array.from(workflowSteps).map(step => step.dataset.step);
    
    // Vérifier le mode avancé
    const advancedModeToggle = document.getElementById('advanced-mode-toggle');
    const isAdvancedMode = advancedModeToggle?.checked || false;
    
    const projectData = {
        title: title,
        idea: idea,
        type: selectedType,
        project_format: selectedType === 'short_drama' ? 'one_shot' : (selectedType === 'serie' ? 'serie' : 'film'),
        narrative_style: selectedNarrativeStyle,
        genres: selectedGenres,
        visual_styles: selectedStyles,
        reference_images: uploadedImages,
        extracted_style_prompt: extractedStylePrompt,
        workflow_steps: selectedSteps,
        auto_approve: !isAdvancedMode,
        seasons: selectedType === 'series' ? parseInt(document.getElementById('project-seasons')?.value) : null,
        episodes_per_season: selectedType === 'series' ? parseInt(document.getElementById('project-episodes')?.value) : null,
        duration_minutes: selectedType === 'film' ? parseInt(document.getElementById('project-duration')?.value) : null,
        synopsis: synopsis,
        status: status
    };
    
    console.log('📤 Creating project:', projectData);
    
    try {
        // ÉTAPE 1 : Créer le projet
        const response = await fetch('/api/projects/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(projectData)
        });
        
        if (response.status === 401) {
            alert('❌ Session expired. Please login again.');
            localStorage.removeItem('access_token');
            window.location.href = '/';
            return;
        }
        
        if (!response.ok) {
            const error = await response.json();
            alert('❌ Error: ' + (error.detail || 'Failed to create project'));
            return;
        }
        
        const project = await response.json();
        console.log('✅ Project created:', project);
        
        // ÉTAPE 2 : Si "Generate" (pas draft), lancer le WorkflowEngine
        if (status === 'active') {
            // Afficher la console
            const consoleLogs = document.getElementById('console-logs');
            if (consoleLogs) {
                consoleLogs.innerHTML = '';
                addLog('🚀 Project created. Starting AI generation...', 'system');
            }
            
            // Appeler l'endpoint de génération
            const generateResponse = await fetch(`/api/projects/${project.id}/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    workflow_steps: selectedSteps,
                    auto_approve: !isAdvancedMode
                })
            });
            
            if (generateResponse.ok) {
                const result = await generateResponse.json();
                console.log('✅ Generation completed:', result);
                
                // Afficher les résultats dans la console
                if (consoleLogs) {
                    addLog('✅ Synopsis generated', 'success');
                    if (result.project.hook) {
                        addLog(`⚡ Hook: ${result.project.hook}`, 'info');
                    }
                    
                    result.characters.forEach(char => {
                        addLog(`🎭 Created: ${char.name} (${char.role})`, 'info');
                    });
                    
                    result.episodes.forEach(ep => {
                        addLog(` Script: ${ep.title}`, 'success');
                    });
                    
                    addLog('🎉 Generation completed!', 'success');
                    updateProgress('Completed', 100);
                }
                
                alert(`✅ Project generated successfully!`);
                closeModal();
                loadProjects(token);
            } else {
                const error = await generateResponse.json();
                alert('❌ Generation error: ' + (error.detail || 'Failed'));
            }
        } else {
            // Mode draft
            alert(`✅ Project saved as draft!`);
            closeModal();
            loadProjects(token);
        }
        
    } catch (error) {
        console.error('❌ Network error:', error);
        alert('❌ Network error: ' + error.message);
    }
}

// ===== CONSOLE LOGGING SYSTEM =====
function addLog(message, type = 'info') {
    const consoleLogs = document.getElementById('console-logs');
    if (!consoleLogs) return;
    
    const div = document.createElement('div');
    const timestamp = new Date().toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
    
    let icon = '️';
    let color = 'text-slate-300';
    
    if (type === 'success') { icon = '✅'; color = 'text-green-400'; }
    if (type === 'error') { icon = '❌'; color = 'text-red-400'; }
    if (type === 'agent') { icon = '🤖'; color = 'text-purple-400 font-bold'; }
    if (type === 'system') { icon = '⚙️'; color = 'text-blue-400'; }

    div.className = `flex gap-2 ${color}`;
    div.innerHTML = `<span class="text-slate-600">[${timestamp}]</span> <span>${icon} ${message}</span>`;
    
    consoleLogs.appendChild(div);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

function updateProgress(step, percent) {
    const currentStepLabel = document.getElementById('current-step');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    
    if (currentStepLabel) currentStepLabel.textContent = step;
    if (progressBar) progressBar.style.width = percent + '%';
    if (progressPercent) progressPercent.textContent = percent + '%';
}