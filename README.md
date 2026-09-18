# hue

Hue Bridge schedule manager. Two-component app deployed as one image, two pod containers:

- **API** (`api.py`, FastAPI on :8000) — wraps the Hue CLIP v2 API and owns all state files. The desktop client and the UI both call this.
- **UI** (`app.py` + `pages/`, Streamlit on :8501) — thin client of the API; no bridge access, no file I/O.

## Rules for callers

- **Always go through the API (`http://hue-api.x81`), never the bridge directly** — the API owns the
  bridge key, the CLIP v2 calls and `config/rooms.yaml`. The Streamlit UI is itself just a client.
- The simple commands are `POST /scene/recall {room, scene}` and `POST /room/on|off {room}`.
- `room` resolves against **`config/rooms.yaml`**, not the bridge — only the abbreviations there are
  addressable (`6std` = studio, `5den`, `1bed`, …). Scene names match **exactly** (`Fairfax`, not `fairfax`).
- **There is no colour endpoint.** Colour reaches the bridge only as a pre-existing scene; room power
  writes `{"on": …}` only.
- **Scene artwork is not fetchable from the bridge** (`metadata.image` is a `public_image` rid that
  resolves only against Signify's CDN). The Stream Deck uses the `hue-scenes` icon pack instead.

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

## Room power examples

Turn a room's lights on/off via `POST /room/off` and `POST /room/on` (off is a power state, not a scene).

```bash
curl -X POST http://hue-api.x81/room/off \
  -H "Content-Type: application/json" \
  -d '{"room":"6std"}'
```

```cmd
curl.exe -X POST http://hue-api.x81/room/off -H "Content-Type: application/json" -d "{\"room\":\"6std\"}"
```
