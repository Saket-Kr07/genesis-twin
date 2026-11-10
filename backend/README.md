# Backend (Part A: Rakhi)

FastAPI skeleton with dummy data that follows `api-contract.md`. Research and education only.

## Run it (Git Bash on Windows)

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs to see and try every endpoint.

## Test accounts (local only)

```bash
python -m app.seed
```

Creates `pro@genesis.test` and `admin@genesis.test` (password printed by the script).

## Tests

```bash
pytest
```

## Day 2 additions

- Experiments (Pro): `POST/GET /experiments`, `GET /experiments/{id}`, `POST /experiments/{id}/fork`, `GET /experiments/{id}/export`
- Uploads (Pro): `POST/GET /uploads`, `GET/DELETE /uploads/{id}`
- `GET /health/functions` shows which functions are real and which are still dummy
- Everything in Docker: from the repo root run `docker compose up --build`

## Swapping dummy functions for real ones

`app/functions.py` tries the real module first and falls back to `app/dummy.py`. Put the real import paths in `CANDIDATES` there:
`predict_health` (ml/), `simulate_pathogen` and `fit_pathogen` (simulation/), `get_sources` (research/).
The input and output shapes must stay the same as in `api-contract.md`.
