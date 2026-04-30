"""HTTP client used by the Streamlit UI to talk to the FastAPI service.

All file I/O and Hue Bridge calls happen server-side. This module mirrors
the function names the pages used to call directly so the UI stays thin.
"""

import os
import httpx

API_BASE = os.environ.get("HUE_API_BASE", "http://localhost:8000")
_client = httpx.Client(base_url=API_BASE, timeout=15.0)


def _get(path: str):
    r = _client.get(path)
    r.raise_for_status()
    return r.json()


def _post(path: str, json: dict | None = None):
    r = _client.post(path, json=json)
    r.raise_for_status()
    return r.json()


def _delete(path: str):
    r = _client.delete(path)
    r.raise_for_status()
    return r.json()


# ── basic info ────────────────────────────────────────────────────────────

def healthz() -> dict:
    return _get("/healthz")


def bridge_ip() -> str:
    return _get("/bridge/info")["ip"]


def get_rooms() -> dict[str, str]:
    return _get("/rooms")


def get_scenes_config() -> list[dict]:
    return _get("/scenes")["scenes"]


def get_scenes_by_room() -> dict[str, dict[str, str]]:
    return _get("/scenes/by-room")


# ── bridge rules ──────────────────────────────────────────────────────────

def get_bridge_rules() -> list[dict]:
    return _get("/bridge/rules")


def get_bridge_duplicates() -> list[dict]:
    return _get("/bridge/duplicates")


def delete_bridge_rule(rid: str) -> dict:
    return _delete(f"/bridge/rules/{rid}")


def cleanup_duplicates() -> dict:
    return _post("/bridge/duplicates/cleanup")


# ── state ─────────────────────────────────────────────────────────────────

def get_current_state() -> dict:
    return _get("/state/current")


def get_future_state() -> dict:
    return _get("/state/future")


def refresh_current_state() -> dict:
    return _post("/state/current/refresh")


def copy_current_to_future() -> dict:
    return _post("/state/future/from-current")


def dedupe_future_state() -> dict:
    return _post("/state/future/dedupe")


def list_future_rules() -> list[dict]:
    return _get("/state/future/rules")


def add_future_rule(scene: str, hour: int, minute: int, rooms: list[str],
                    days: list[str], transition_minutes: int) -> dict:
    return _post("/state/future/rules", json={
        "scene": scene,
        "hour": hour,
        "minute": minute,
        "rooms": rooms,
        "days": days,
        "transition_minutes": transition_minutes,
    })


def delete_future_rule(rule_name: str) -> dict:
    return _delete(f"/state/future/rules/{rule_name}")


# ── sync ──────────────────────────────────────────────────────────────────

def sync_preview() -> dict:
    return _get("/sync/preview")


def sync_apply() -> dict:
    return _post("/sync/apply")


# ── scene recall ──────────────────────────────────────────────────────────

def recall_scene(room: str, scene: str) -> dict:
    return _post("/scene/recall", json={"room": room, "scene": scene})
