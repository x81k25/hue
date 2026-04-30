"""FastAPI service exposing all bridge + state-file operations.

The Streamlit UI is a thin client of this API; the desktop client also
talks to this API. All file I/O and Hue Bridge calls live here.
"""

from __future__ import annotations

import shutil
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import hue_client
import sync as sync_mod
import state_export
from paths import (
    CONFIG_DIR,
    CURRENT_STATE_PATH,
    DIFF_PATH,
    FUTURE_STATE_PATH,
    ROOMS_PATH,
    SCENES_PATH,
)

app = FastAPI(title="Hue Schedule Manager API", root_path="/api")


# ── models ────────────────────────────────────────────────────────────────

class CreateRule(BaseModel):
    scene: str
    hour: int
    minute: int
    rooms: list[str]
    days: list[str]
    transition_minutes: int = 0


class RecallRequest(BaseModel):
    room: str
    scene: str


# ── helpers ───────────────────────────────────────────────────────────────

def _load_yaml(path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _load_scenes_cfg() -> list[dict]:
    if not SCENES_PATH.exists():
        return []
    with open(SCENES_PATH) as f:
        return yaml.safe_load(f).get("scenes", [])


def _scene_name_to_abbr() -> dict[str, str]:
    return {s["name"]: s["abbr"] for s in _load_scenes_cfg()}


# ── basic info ────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/bridge/info")
def bridge_info() -> dict:
    return {"ip": hue_client.BRIDGE_IP}


@app.get("/rooms")
def get_rooms() -> dict[str, str]:
    return hue_client.get_rooms()


@app.get("/scenes")
def get_scenes_config() -> dict:
    """Full scenes.yaml content (categories, abbrs, colors)."""
    return {"scenes": _load_scenes_cfg()}


@app.get("/scenes/by-room")
def get_scenes_by_room() -> dict[str, dict[str, str]]:
    return hue_client.get_scenes_by_room()


# ── bridge rules ──────────────────────────────────────────────────────────

@app.get("/bridge/rules")
def get_bridge_rules() -> list[dict]:
    return sync_mod.get_current_bridge_rules()


@app.get("/bridge/duplicates")
def get_bridge_duplicates() -> list[dict]:
    return sync_mod.find_bridge_duplicates()


@app.delete("/bridge/rules/{rid}")
def delete_bridge_rule(rid: str) -> dict:
    try:
        hue_client.delete_schedule(rid)
        return {"deleted": rid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bridge/duplicates/cleanup")
def cleanup_duplicates() -> dict:
    dups = sync_mod.find_bridge_duplicates()
    if not dups:
        return {"deleted": [], "errors": []}
    diff = {"create": [], "update": [], "delete": dups}
    results = sync_mod.apply_sync(diff)
    state_export.save_current_state()
    return {"deleted": results["deleted"], "errors": results["errors"]}


# ── state files ───────────────────────────────────────────────────────────

@app.get("/state/current")
def get_current_state() -> dict:
    return _load_yaml(CURRENT_STATE_PATH)


@app.get("/state/future")
def get_future_state() -> dict:
    return _load_yaml(FUTURE_STATE_PATH)


@app.post("/state/current/refresh")
def refresh_current_state() -> dict:
    state_export.save_current_state()
    return {"refreshed": True, "path": str(CURRENT_STATE_PATH)}


@app.post("/state/future/from-current")
def copy_current_to_future() -> dict:
    if not CURRENT_STATE_PATH.exists():
        raise HTTPException(status_code=404, detail="current_state.yaml missing")
    shutil.copy2(CURRENT_STATE_PATH, FUTURE_STATE_PATH)
    return {"copied": True}


@app.post("/state/future/dedupe")
def dedupe_future_state() -> dict:
    path = state_export.save_deduped_future_state()
    return {"saved": True, "path": str(path)}


@app.get("/state/future/rules")
def list_future_rules() -> list[dict]:
    """Flat list of unique rules in future_state.yaml."""
    state = _load_yaml(FUTURE_STATE_PATH)
    seen: dict[str, dict] = {}
    for room, days in state.get("rooms", {}).items():
        for day, day_data in days.items():
            for r in day_data.get("raw", []):
                if r["name"] not in seen:
                    seen[r["name"]] = {
                        "name": r["name"],
                        "room": room,
                        "time": r["time"],
                        "scene": r["scene"],
                        "transition_minutes": r.get("transition_minutes", 0),
                    }
    return sorted(seen.values(), key=lambda r: (r["room"], r["time"]))


@app.post("/state/future/rules")
def add_future_rule(rule: CreateRule) -> dict:
    if not 0 <= rule.hour <= 23 or not 0 <= rule.minute <= 59:
        raise HTTPException(status_code=400, detail="hour/minute out of range")
    if not 0 <= rule.transition_minutes <= 120:
        raise HTTPException(status_code=400, detail="transition_minutes out of range")
    if not rule.rooms or not rule.days:
        raise HTTPException(status_code=400, detail="rooms and days required")

    abbr = _scene_name_to_abbr().get(rule.scene, rule.scene.lower().replace(" ", "-"))
    time_str = f"{rule.hour:02d}:{rule.minute:02d}"
    state = _load_yaml(FUTURE_STATE_PATH)
    state.setdefault("rooms", {})

    for room in rule.rooms:
        name = f"{room}-{rule.hour:02d}{rule.minute:02d}-{abbr}"
        state["rooms"].setdefault(room, {})
        for day in rule.days:
            state["rooms"][room].setdefault(day, {"raw": [], "resolved": []})
            raw = state["rooms"][room][day]["raw"]
            if not any(r["name"] == name for r in raw):
                raw.append({
                    "name": name,
                    "time": time_str,
                    "scene": rule.scene,
                    "transition_minutes": rule.transition_minutes,
                })
                raw.sort(key=lambda r: r["time"])

    _recompute_resolved(state)
    _save_yaml(FUTURE_STATE_PATH, state)
    return {"added": True}


@app.delete("/state/future/rules/{rule_name}")
def delete_future_rule(rule_name: str) -> dict:
    state = _load_yaml(FUTURE_STATE_PATH)
    for room, days in state.get("rooms", {}).items():
        for day, day_data in days.items():
            day_data["raw"] = [r for r in day_data.get("raw", []) if r["name"] != rule_name]
    _recompute_resolved(state)
    _save_yaml(FUTURE_STATE_PATH, state)
    return {"deleted": rule_name}


def _recompute_resolved(state: dict) -> None:
    for room, days in state.get("rooms", {}).items():
        for day, day_data in days.items():
            raw = day_data.get("raw", [])
            rules = []
            for r in raw:
                hh, mm = r["time"].split(":")
                rules.append({
                    "hour": int(hh),
                    "minute": int(mm),
                    "scene": r["scene"],
                    "transition_minutes": r.get("transition_minutes", 0),
                })
            day_data["resolved"] = state_export.resolve_points(rules)


# ── sync ──────────────────────────────────────────────────────────────────

@app.get("/sync/preview")
def sync_preview() -> dict:
    diff = sync_mod.preview_sync()
    _save_yaml(DIFF_PATH, diff)
    return diff


@app.post("/sync/apply")
def sync_apply() -> dict:
    diff = sync_mod.preview_sync()
    results = sync_mod.apply_sync(diff)
    state_export.save_current_state()
    return results


# ── one-shot scene recall (for desktop client) ────────────────────────────

@app.post("/scene/recall")
def recall_scene(req: RecallRequest) -> dict:
    """Activate a scene immediately on a room."""
    rooms = hue_client.get_rooms()
    if req.room not in rooms:
        raise HTTPException(status_code=404, detail=f"room '{req.room}' not found")
    room_rid = rooms[req.room]
    scenes_by_room = hue_client.get_scenes_by_room()
    scene_ref = hue_client.resolve_scene_ref(room_rid, req.scene, scenes_by_room)
    if scene_ref["rtype"] == "scene":
        return hue_client.recall_scene(scene_ref["rid"])
    # recipes can't be recalled directly via PUT on /scene; create a one-shot via
    # behavior_instance is overkill, so document the limitation
    raise HTTPException(
        status_code=400,
        detail="recipe recall not supported; use a room-specific scene",
    )
