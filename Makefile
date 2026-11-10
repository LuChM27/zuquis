# Atajos de desarrollo. En Windows sin make, ejecutar los comandos equivalentes a mano.
PY := backend/.venv/Scripts/python

up:        ## Levanta DB, API y web
	docker compose up -d --build
down:
	docker compose down
db:        ## Solo PostgreSQL (para correr pruebas desde el equipo)
	docker compose up -d db
migrate:
	cd backend && ../$(PY) -m alembic upgrade head
test:
	cd backend && ../$(PY) -m pytest
	cd frontend && npm test -- --run
lint:
	cd backend && ../$(PY) -m ruff check . && ../$(PY) -m ruff format --check .
	cd frontend && npm run lint
admin:     ## Crea el usuario administrador inicial
	docker compose exec api python -m app.cli crear-admin
