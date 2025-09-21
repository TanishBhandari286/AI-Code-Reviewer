# Code Reviewer

Backend (Python, FastAPI, uv) and Frontend (React, Vite) for automated code review and interview-question augmentation.

## Backend (uv)

Use uv for everything (envs, deps, run):

- Initialize (done):
	- `uv init .`
- Add dependencies:
	- `uv add fastapi openai psycopg2-binary sqlalchemy uvicorn python-dotenv`
- Sync/lock:
	- `uv sync`
	- `uv lock`
- Run health check:
	- `uv run backend/main.py --health`
- Run API server:
	- `uv run backend/main.py --serve`
- CLI review example:
	- `uv run backend/main.py --repo https://github.com/python/cpython`

Environment:

- Copy `.env.example` to `.env` and set `DATABASE_URL`, `OPENAI_API_KEY`, `GITHUB_TOKEN`.

Review modes:

- You can select a review mode when submitting from the UI, or control defaults via env.
- Modes supported by the backend:
	- full: scan the whole repository (subject to MAX_FILES_REVIEW cap)
	- recent: prefer changed files since last reviewed commit; fallback to a small subset
	- smart: prefer code files and changed files; caps to ~20 by default
- Environment variables:
	- DEFAULT_REVIEW_MODE: full | recent | smart (default: full)
	- MAX_FILES_REVIEW: integer limit for files processed per run (default: 50)

## Frontend (React)

Use npm or yarn:

- `npm install`
- `npm run start`

The app expects backend on `http://localhost:8000`.

## Docker

Containerize backend and frontend separately. Build images from `Dockerfile.backend` and `Dockerfile.frontend`.

Quick start with docker-compose (local):

- Copy `.env.example` to `.env` and fill in values (at minimum `GITHUB_TOKEN`).
- Start services:
	- docker compose up --build
- Open frontend at http://localhost:5173
- Backend API at http://localhost:8000 (health: http://localhost:8000/health)
- Data volumes:
	- Postgres data: named volume `pgdata`
	- Cloned repos: named volume `clonedrepos`

Deploying on Coolify (outline):

1) Create a Postgres 16 database in Coolify (or use a managed DB). Capture connection string.
2) Add a new "Dockerfile from Git" app for the backend:
	 - Repository: this repo
	 - Dockerfile: `Dockerfile.backend`
	 - Port: 8000
	 - Environment variables:
		 - DATABASE_URL: postgresql+psycopg2://<user>:<pass>@<host>:<port>/<db>
		 - REPO_CLONE_DIR: /clonedrepos
		 - GITHUB_TOKEN: <your token>
		 - PORT: 8000
	 - Persistent volume: mount a volume at `/clonedrepos`
3) Add a second app for the frontend:
	 - Dockerfile: `Dockerfile.frontend`
	 - Port: 80
	 - Build args:
		 - VITE_API_BASE=https://<your-backend-domain>
	 - Domain: your chosen frontend domain
4) Ensure CORS on backend allows your frontend origin (default here is `*`).
5) Deploy both apps. Verify:
	 - Backend /health returns ok over public URL
	 - Frontend loads and uses the public backend URL

Separate domains (recommended):

- Backend public URL (example): https://backend.tanishbhandari.name
- Frontend public URL (example): https://review.tanishbhandari.name
- Set on backend:
	- CORS_ORIGINS=https://review.tanishbhandari.name
	- Optional: CORS_ALLOW_CREDENTIALS=true (only if you use cookies/auth)
- Set on frontend build args:
	- VITE_API_BASE=https://backend.tanishbhandari.name

## Notes

- GitHub PR creation requires GitHub CLI (`gh`) and `gh auth login`.
- The AI integration is a heuristic stub; replace with OpenAI API calls when ready.
- To control where repos are cloned, set `REPO_CLONE_DIR` (e.g., `/Users/<you>/code/Code_Reviewer/clonedrepos`).
