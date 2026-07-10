# Fashion App — Backend (FastAPI)

Phase 0 skeleton: app config, Supabase client wiring, and `/auth` endpoints.

## Setup

```bash
cd backend
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then fill in Supabase keys (Step 3)
```

## Run

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The app boots without Supabase credentials. Auth endpoints return `503`
until `SUPABASE_URL` / `SUPABASE_ANON_KEY` are set in `.env`.

## Endpoints (v1)

| Method | Path             | Auth        | Purpose                       |
|--------|------------------|-------------|-------------------------------|
| GET    | `/health`        | none        | Liveness + config check       |
| POST   | `/v1/auth/signup`| none        | Create account                |
| POST   | `/v1/auth/login` | none        | Email/password login          |
| GET    | `/v1/auth/me`    | Bearer token| Current authenticated user    |

## Layout

```
app/
  main.py            # FastAPI app + middleware + router wiring
  core/
    config.py        # env-backed settings (single source of env access)
    supabase_client.py
  api/
    deps.py          # shared dependencies (current-user resolver)
    v1/auth.py       # auth routes
  schemas/auth.py    # request/response models
```
