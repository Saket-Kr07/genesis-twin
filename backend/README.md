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

## Swapping dummy functions for real ones (Day 2)

All dummy functions live in `app/dummy.py`. Replace each one with the real function:
`predict_health` (ml/), `simulate_pathogen` and `fit_pathogen` (simulation/), `get_sources` (research/).
The input and output shapes must stay the same as in `api-contract.md`.
