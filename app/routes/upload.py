from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.style_extractor import StyleExtractorService
import os
import shutil
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/upload", tags=["upload"])

UPLOAD_DIR = "app/static/uploads/reference_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

style_extractor = StyleExtractorService()

@router.post("/image")
async def upload_image(file: UploadFile = File(...), kind: str = Form(None)):
    """Upload une image de référence, retourne son URL, et — si `kind` vaut
    'world' ou 'character' — déclenche automatiquement l'extraction du
    prompt de style correspondant (analyse vision), retournée dans la même
    réponse pour un affichage immédiat côté frontend."""
    print(f"\n{'='*60}")
    print(f"📤 UPLOAD IMAGE")
    print(f"   Filename: {file.filename}")
    print(f"   Content-Type: {file.content_type}")
    print(f"   Kind: {kind}")
    
    # Vérifier le type de fichier
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        print(f"❌ File type not allowed: {file_ext}")
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # Générer un nom de fichier unique
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    print(f"   Saving to: {file_path}")
    
    # Sauvegarder le fichier
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = os.path.getsize(file_path)
        print(f"   ✅ File saved successfully ({file_size} bytes)")
    except Exception as e:
        print(f"   ❌ Failed to save file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Retourner l'URL (relative au static)
    file_url = f"/static/uploads/reference_images/{unique_filename}"
    print(f"   Returning URL: {file_url}")

    # Extraction automatique du style (si demandée) — ne bloque jamais
    # l'upload : en cas d'échec (quota, réseau...), on renvoie juste None.
    extracted_style = None
    if kind in ("world", "character"):
        try:
            extracted_style = style_extractor.extract_style(file_path, kind)
            print(f"   🎨 Style extracted ({kind}): {extracted_style[:100] if extracted_style else 'None'}...")
        except Exception as e:
            print(f"   ⚠️ Style extraction failed (non-blocking): {e}")

    print(f"{'='*60}\n")
    
    return {
        "url": file_url,
        "filename": file.filename,
        "size": file_size,
        "extracted_style": extracted_style
    }