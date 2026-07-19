import os
from dotenv import load_dotenv

load_dotenv()

# Chemin ABSOLU vers la racine du projet (dossier contenant "app/"), pour que
# la base SQLite pointe toujours vers le même fichier peu importe le
# répertoire de travail depuis lequel `uvicorn` est lancé (terminal, VS Code,
# script...). Avant ce correctif, "sqlite:///./rbs_aiproducer.db" était un
# chemin RELATIF, donc silencieusement différent selon le cwd — ce qui
# explique qu'un fichier supprimé "à l'œil" pouvait ne pas être celui
# réellement utilisé par l'application.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "rbs_aiproducer.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours  
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# URL publique de l'app. N'est PLUS nécessaire pour la génération vidéo (R2V) :
# le SDK dashscope upload automatiquement les fichiers locaux vers le stockage
# Alibaba (OSS) — voir scene_generator.py. Reste utile pour d'éventuelles
# fonctionnalités futures (partage de lien public, etc.).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

if DEBUG:
    print(f"📂 [Config] Database file: {_DEFAULT_DB_PATH if 'DATABASE_URL' not in os.environ else DATABASE_URL}")

