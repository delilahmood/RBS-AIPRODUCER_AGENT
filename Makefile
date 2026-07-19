.PHONY: venv install dev run test clean help

# Créer l'environnement virtuel
venv:
	python -m venv venv

# Installer les dépendances
install:
	pip install -r requirements.txt

# Lancer le serveur de développement (avec hot-reload)
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Lancer le serveur en mode production
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

# Lancer les tests
test:
	pytest tests/ -v

# Nettoyer les fichiers temporaires et la base de données
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -f rbs_aiproducer.db

# Afficher l'aide
help:
	@echo "🎬 RBS AIProducer - Commandes disponibles :"
	@echo ""
	@echo "  make venv       - Créer l'environnement virtuel"
	@echo "  make install    - Installer les dépendances"
	@echo "  make dev        - Lancer le serveur de développement"
	@echo "  make run        - Lancer le serveur en production"
	@echo "  make test       - Lancer les tests"
	@echo "  make clean      - Nettoyer les fichiers temporaires"