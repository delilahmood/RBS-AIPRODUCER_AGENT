// ===== LANDING PAGE LOGIC =====
document.addEventListener('DOMContentLoaded', function() {
    console.log(' RBS AIProducer initialized');
    
    // ===== PASSWORD TOGGLE =====
    function setupPasswordToggle(toggleId, inputId) {
        const toggle = document.getElementById(toggleId);
        const input = document.getElementById(inputId);
        
        if (toggle && input) {
            toggle.addEventListener('click', function() {
                console.log('👁️ Password toggle for', inputId);
                if (input.type === 'password') {
                    input.type = 'text';
                    toggle.classList.remove('fa-eye');
                    toggle.classList.add('fa-eye-slash');
                } else {
                    input.type = 'password';
                    toggle.classList.remove('fa-eye-slash');
                    toggle.classList.add('fa-eye');
                }
            });
        }
    }
    
    setupPasswordToggle('toggle-signin-password', 'signin-password');
    setupPasswordToggle('toggle-join-password', 'join-password');

    // ===== VIDEO ROTATION =====
    const videoElement = document.getElementById('bgVideo');
    const videoSources = [
        '/static/videos/v1.mp4',
        '/static/videos/v2.mp4',
        '/static/videos/v3.mp4',
        '/static/videos/v4.mp4'
    ];
    let currentVideoIndex = 0;

    if (videoElement) {
        videoElement.src = videoSources[0];
        videoElement.load();
        videoElement.play().catch(e => console.log('Autoplay prevented:', e));
        
        videoElement.addEventListener('ended', function() {
            console.log('Video ended, switching to next...');
            currentVideoIndex = (currentVideoIndex + 1) % videoSources.length;
            videoElement.src = videoSources[currentVideoIndex];
            videoElement.load();
            videoElement.play().catch(e => console.log('Play error:', e));
        });
    }

    // ===== TAB SWITCHING =====
    const tabSignin = document.getElementById('tab-signin');
    const tabJoin = document.getElementById('tab-join');
    const formSignin = document.getElementById('form-signin');
    const formJoin = document.getElementById('form-join');
    const switchToSigninBtn = document.getElementById('switch-to-signin');

    function switchTab(tab) {
        console.log('🔄 Switching to tab:', tab);
        if (tab === 'signin') {
            tabSignin.classList.add('tab-active');
            tabJoin.classList.remove('tab-active');
            formSignin.classList.remove('hidden');
            formJoin.classList.add('hidden');
        } else {
            tabJoin.classList.add('tab-active');
            tabSignin.classList.remove('tab-active');
            formJoin.classList.remove('hidden');
            formSignin.classList.add('hidden');
        }
    }

    if (tabSignin) tabSignin.addEventListener('click', () => switchTab('signin'));
    if (tabJoin) tabJoin.addEventListener('click', () => switchTab('join'));
    if (switchToSigninBtn) switchToSigninBtn.addEventListener('click', () => switchTab('signin'));

    // ===== SIGN UP HANDLER =====
    const formJoinElement = document.getElementById('form-join');
    if (formJoinElement) {
        formJoinElement.addEventListener('submit', async function(event) {
            event.preventDefault();
            console.log('🚀 Sign up form submitted');
            
            const btn = document.getElementById('join-btn');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
            btn.disabled = true;
            
            const userData = {
                email: document.getElementById('join-email').value,
                password: document.getElementById('join-password').value,
                full_name: document.getElementById('join-fullname').value,
                studio_name: document.getElementById('join-studio').value || null
            };
            
            console.log(' Data:', userData);
            
            try {
                const response = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(userData)
                });
                
                console.log('📥 Status:', response.status);
                const data = await response.json();
                console.log('📥 Response:', data);
                
                if (response.ok) {
                    alert('✅ Account created! Redirecting...');
                    window.location.href = '/dashboard';
                } else {
                    alert('❌ Error: ' + (data.detail || 'Registration failed'));
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            } catch (error) {
                console.error('❌ Error:', error);
                alert('❌ Network error: ' + error.message);
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        });
    }

    // ===== SIGN IN HANDLER =====
    const formSigninElement = document.getElementById('form-signin');
    if (formSigninElement) {
        formSigninElement.addEventListener('submit', async function(event) {
            event.preventDefault();
            console.log('🚀 Sign in form submitted');
            
            const btn = document.getElementById('signin-btn');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';
            btn.disabled = true;
            
            const email = document.getElementById('signin-email').value;
            const password = document.getElementById('signin-password').value;
            
            console.log('📤 Email:', email);
            
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({
                        'username': email,
                        'password': password
                    })
                });
                
                console.log('📥 Status:', response.status);
                const data = await response.json();
                console.log('📥 Response:', data);
                
                if (response.ok) {
                    localStorage.setItem('access_token', data.access_token);
                    window.location.href = '/dashboard';
                } else {
                    alert('❌ Error: ' + (data.detail || 'Login failed'));
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            } catch (error) {
                console.error('❌ Error:', error);
                alert('❌ Network error');
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        });
    }

    // ===== AUTH PANEL TOGGLE =====
    const authPanel = document.getElementById('authPanel');
    const toggleAuth = document.getElementById('toggleAuth');
    const mainLanding = document.querySelector('.main-landing');
    
    if (toggleAuth && authPanel) {
        toggleAuth.addEventListener('click', function() {
            authPanel.classList.toggle('collapsed');
            
            if (authPanel.classList.contains('collapsed')) {
                if (mainLanding) {
                    mainLanding.style.paddingRight = '120px';
                }
            } else {
                if (mainLanding) {
                    mainLanding.style.paddingRight = '420px';
                }
            }
        });
    }
    
    console.log('✅ All event listeners attached');
});