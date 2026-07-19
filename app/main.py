from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.models.project import Project
from app.database import engine, Base, get_db
from app.routes import auth, projects, characters, chat, generation, upload, export, locations, scenes, episodes
from fastapi.middleware.cors import CORSMiddleware

# ===== INITIALISATION APP =====
app = FastAPI(title="RBS AIProducer", version="1.0.0")

# ===== CORS & SECURITY =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== CRÉATION DE LA BASE DE DONNÉES =====
Base.metadata.create_all(bind=engine)
print("✅ Database tables created successfully")

# ===== MOUNT STATIC FILES =====
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ===== FIX ENCODAGE (Windows) =====
# Sur Windows, le module `mimetypes` (utilisé par Starlette/StaticFiles) lit le
# registre système et renvoie souvent "application/javascript" ou
# "text/javascript" SANS "; charset=utf-8". Le navigateur doit alors deviner
# l'encodage du fichier et retombe parfois sur Windows-1252, ce qui corrompt
# les caractères typographiques (—, …, ', etc.) écrits en UTF-8 dans nos
# fichiers .js/.css/.html (ex: "â€™" à la place de "'"). On force explicitement
# le charset ici pour tous les fichiers texte servis en statique.
TEXT_MEDIA_TYPES = (
    "text/", "application/javascript", "application/json", "image/svg+xml"
)

@app.middleware("http")
async def force_utf8_charset_on_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        content_type = response.headers.get("content-type", "")
        if content_type.startswith(TEXT_MEDIA_TYPES) and "charset=" not in content_type:
            response.headers["content-type"] = f"{content_type}; charset=utf-8"
    return response

# ===== TEMPLATES =====
templates = Jinja2Templates(directory="app/templates")

# ===== ENREGISTREMENT DES ROUTES API =====
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(characters.router)
app.include_router(chat.router)
app.include_router(generation.router)
app.include_router(upload.router)
app.include_router(export.router)
app.include_router(locations.router)
app.include_router(scenes.router)
app.include_router(episodes.router)

print("✅ All routes registered:")
print("   - /api/auth/")
print("   - /api/projects/")
print("   - /api/characters/")
print("   - /api/chat/")
print("   - /api/generation/*")
print("   - /api/upload/")

# ===== CONFIG JWT =====
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ===== FONCTION POUR RÉCUPÉRER L'UTILISATEUR =====
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        from app.models.user import User
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ===== ROUTES PAGES =====
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Page d'accueil (landing)"""
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard - accessible après connexion"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/studio/{project_id}", response_class=HTMLResponse)
async def studio(request: Request, project_id: int, db: Session = Depends(get_db)):
    """Workspace d'un projet"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return templates.TemplateResponse("studio.html", {
        "request": request,
        "project_id": project_id,
        "project": project
    })

# ⚠️ IMPORTANT: /generator/new doit être AVANT /generator/{project_id}
@app.get("/generator/new", response_class=HTMLResponse)
async def generator_new_page(request: Request):
    """Page du Générateur pour un NOUVEAU projet"""
    return templates.TemplateResponse("generator.html", {
        "request": request,
        "project_id": None,
        "project": None
    })

@app.get("/generator/{project_id}", response_class=HTMLResponse)
async def generator_page(request: Request, project_id: int, db: Session = Depends(get_db)):
    """Page du Générateur pour un projet EXISTANT"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        print(f"❌ Project with ID {project_id} not found")
    
    print(f"✅ Loaded generator page for project ID {project_id}")
    return templates.TemplateResponse("generator.html", {
        "request": request,
        "project_id": project_id,
        "project": project
    } 
    )

# ===== ROUTE DE TEST API =====
@app.get("/api/health")
async def health_check():
    """Endpoint pour vérifier que l'API fonctionne"""
    return {
        "status": "ok",
        "message": "RBS AIProducer API is running",
        "endpoints": [
            "/api/auth/register",
            "/api/auth/login",
            "/api/projects/",
            "/api/characters/",
            "/api/chat/send",
            "/api/upload/image"
        ]
    }

# ===== LANCEMENT =====
if __name__ == "__main__":
    import uvicorn
    print("\n🎬 Starting RBS AIProducer...")
    print("📡 API: http://localhost:8000/api/health")
    print("🌐 App: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)