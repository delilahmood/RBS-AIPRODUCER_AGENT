// ===== STUDIO LOGIC =====
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Studio initialized');
    
    // Check authentication
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.log('❌ No token, redirecting to login');
        window.location.href = '/';
        return;
    }
    
    setupAiPanel();
    setupNavigation();
    setupChat();
    
    console.log('✅ Studio ready');
});

// ===== AI PANEL TOGGLE =====
function setupAiPanel() {
    const aiPanel = document.getElementById('aiPanel');
    const closeBtn = document.getElementById('closeAiPanel');
    const openBtn = document.getElementById('openAiPanel');
    
    if (closeBtn && aiPanel) {
        closeBtn.addEventListener('click', function() {
            aiPanel.classList.add('collapsed');
            openBtn.classList.remove('hidden');
        });
    }
    
    if (openBtn && aiPanel) {
        openBtn.addEventListener('click', function() {
            aiPanel.classList.remove('collapsed');
            openBtn.classList.add('hidden');
        });
    }
}

// ===== NAVIGATION =====
function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            navItems.forEach(i => i.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

// ===== CHAT =====
function setupChat() {
    const chatInput = document.querySelector('input[placeholder="Posez votre question..."]');
    const sendBtn = chatInput?.nextElementSibling;
    
    if (sendBtn && chatInput) {
        sendBtn.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendMessage();
        });
    }
    
    function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;
        
        console.log(' Sending:', message);
        chatInput.value = '';
        // TODO: Implement actual API call
    }
}

// ===== AI PANEL TOGGLE =====
function setupAiPanel() {
    const aiPanel = document.getElementById('aiPanel');
    const closeBtn = document.getElementById('closeAiPanel');
    const openBtn = document.getElementById('openAiPanel');
    const robotToggle = document.querySelector('.robot-toggle');
    
    // Close button inside panel
    if (closeBtn && aiPanel) {
        closeBtn.addEventListener('click', function() {
            aiPanel.classList.add('collapsed');
            if (openBtn) openBtn.classList.add('show');
            if (robotToggle) robotToggle.classList.remove('vibrating');
        });
    }
    
    // Floating open button
    if (openBtn && aiPanel) {
        openBtn.addEventListener('click', function() {
            aiPanel.classList.remove('collapsed');
            openBtn.classList.remove('show');
            if (robotToggle) robotToggle.classList.add('vibrating');
        });
    }
    
    // Robot toggle button (on the side of the panel)
    if (robotToggle && aiPanel) {
        robotToggle.addEventListener('click', function() {
            if (aiPanel.classList.contains('collapsed')) {
                aiPanel.classList.remove('collapsed');
                if (openBtn) openBtn.classList.remove('show');
                robotToggle.classList.add('vibrating');
            } else {
                aiPanel.classList.add('collapsed');
                if (openBtn) openBtn.classList.add('show');
                robotToggle.classList.remove('vibrating');
            }
        });
    }
}
