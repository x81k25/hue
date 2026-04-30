# hue

Hue Bridge schedule manager. Two-component app deployed as one image, two pod containers:

- **API** (`api.py`, FastAPI on :8000) — wraps the Hue CLIP v2 API and owns all state files. The desktop client and the UI both call this.
- **UI** (`app.py` + `pages/`, Streamlit on :8501) — thin client of the API; no bridge access, no file I/O.

## Layout

```
api.py            # FastAPI service — all bridge + state I/O lives here
api_client.py     # HTTP wrapper used by Streamlit pages
app.py            # Streamlit entrypoint
pages/            # Streamlit multipage UI
hue_client.py     # CLIP v2 API wrapper (server-side only)
sync.py           # diff/apply state vs bridge (server-side only)
state_export.py   # serialize bridge → current_state.yaml (server-side only)
schedule_model.py # schedule dataclass + helpers (server-side only)
paths.py          # config-dir resolution (HUE_CONFIG_DIR env var)
config/           # state YAML files (rooms, scenes, current/future state, schedules)
```

## Env vars

API container:
- `HUE_BRIDGE_IP`, `HUE_API_KEY`, `HUE_CLIENT_KEY` — from `hue-secrets` k8s Secret
- `HUE_CONFIG_DIR=/app/config` — points at mounted hostPath in k8s

UI container:
- `HUE_API_BASE=http://localhost:8000` — same-pod sidecar

## Local dev

```bash
uv sync
# terminal 1
uvicorn api:app --port 8000 --reload
# terminal 2
HUE_API_BASE=http://localhost:8000 streamlit run app.py
```

`.env` (gitignored) supplies `HUE_BRIDGE_IP` / `HUE_API_KEY` / `HUE_CLIENT_KEY` for the API process.

## Deploy

GitLab CI builds `192.168.50.2:5050/infra/experiments/hue:main` on push to `main`.
ArgoCD picks up the manifests in `/infra/k8s-manifests/experiments/hue/` and deploys.
Reach the UI at `http://hue.x81/` and the API at `http://hue-api.x81/`.

## Scene recall examples

Activate a scene on a room immediately via `POST /scene/recall`.

Linux / macOS:

```bash
curl -X POST http://hue-api.x81/scene/recall \
  -H "Content-Type: application/json" \
  -d '{"room":"6std","scene":"Relax"}'
```

Windows PowerShell:

```powershell
Invoke-RestMethod -Uri http://hue-api.x81/scene/recall `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"room":"6std","scene":"Relax"}'
```

Windows cmd (`curl.exe` ships with Windows 10+):

```cmd
curl.exe -X POST http://hue-api.x81/scene/recall -H "Content-Type: application/json" -d "{\"room\":\"6std\",\"scene\":\"Relax\"}"
```
