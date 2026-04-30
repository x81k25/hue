"""Thin wrapper around the Hue CLIP v2 API."""

import os
import yaml
import requests
from dotenv import load_dotenv
from paths import ROOMS_PATH

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BRIDGE_IP = os.environ["HUE_BRIDGE_IP"]
API_KEY = os.environ["HUE_API_KEY"]
BASE = f"https://{BRIDGE_IP}/clip/v2/resource"
HEADERS = {"hue-application-key": API_KEY}

# schedule script ID (consistent across firmware versions on this bridge)
SCHEDULE_SCRIPT_ID = "7238c707-8693-4f19-9095-ccdc1444d228"

# universal recipe IDs (not room-specific)
RECIPES = {
    "Bright": "732ff1d9-76a7-4630-aad0-c8acc499bb0b",
    "Off": "caabcf9c-984b-4a2c-a97a-0ed61a299258",
}


def _get(resource: str) -> list[dict]:
    r = requests.get(f"{BASE}/{resource}", headers=HEADERS, verify=False)
    r.raise_for_status()
    return r.json()["data"]


def _put(resource: str, rid: str, payload: dict) -> dict:
    r = requests.put(f"{BASE}/{resource}/{rid}", headers=HEADERS, json=payload, verify=False)
    r.raise_for_status()
    return r.json()


def _post(resource: str, payload: dict) -> dict:
    r = requests.post(f"{BASE}/{resource}", headers=HEADERS, json=payload, verify=False)
    r.raise_for_status()
    return r.json()


def _delete(resource: str, rid: str) -> dict:
    r = requests.delete(f"{BASE}/{resource}/{rid}", headers=HEADERS, verify=False)
    r.raise_for_status()
    return r.json()


def get_rooms() -> dict[str, str]:
    """Return {room_name: room_rid} from config/rooms.yaml."""
    with open(ROOMS_PATH) as f:
        data = yaml.safe_load(f)
    return {name: info["rid"] for name, info in data["rooms"].items()}


def get_scenes() -> list[dict]:
    """Return raw scene list."""
    return _get("scene")


def get_scenes_by_room() -> dict[str, dict[str, str]]:
    """Return {room_rid: {scene_name: scene_rid}}."""
    result: dict[str, dict[str, str]] = {}
    for s in get_scenes():
        room_rid = s["group"]["rid"]
        name = s["metadata"]["name"]
        result.setdefault(room_rid, {})[name] = s["id"]
    return result


def get_behavior_instances() -> list[dict]:
    """Return all behavior_instance resources."""
    return _get("behavior_instance")


def get_schedule_instances() -> list[dict]:
    """Return only schedule-type behavior_instances."""
    return [b for b in get_behavior_instances() if b["script_id"] == SCHEDULE_SCRIPT_ID]


def resolve_scene_ref(room_rid: str, scene_name: str, scenes_by_room: dict) -> dict:
    """Resolve a scene name to a recall dict (recipe or room-specific scene)."""
    room_scenes = scenes_by_room.get(room_rid, {})
    if scene_name in room_scenes:
        return {"rid": room_scenes[scene_name], "rtype": "scene"}
    if scene_name in RECIPES:
        return {"rid": RECIPES[scene_name], "rtype": "recipe"}
    raise ValueError(f"Scene '{scene_name}' not found for room {room_rid}")


def create_schedule(
    name: str,
    room_rid: str,
    scene_ref: dict,
    hour: int,
    minute: int,
    days: list[str],
    transition_minutes: int = 0,
    enabled: bool = True,
) -> dict:
    """Create a schedule behavior_instance."""
    start_at = {
        "time_point": {
            "time": {"hour": hour, "minute": minute},
            "type": "time",
        }
    }
    if transition_minutes > 0:
        if transition_minutes >= 60 and transition_minutes % 60 == 0:
            start_at["transition"] = {"hours": transition_minutes // 60}
        else:
            start_at["transition"] = {"minutes": transition_minutes}

    payload = {
        "type": "behavior_instance",
        "script_id": SCHEDULE_SCRIPT_ID,
        "enabled": enabled,
        "configuration": {
            "what": [
                {
                    "group": {"rid": room_rid, "rtype": "room"},
                    "recall": scene_ref,
                }
            ],
            "when_extended": {
                "recurrence_days": days,
                "start_at": start_at,
            },
            "where": [{"group": {"rid": room_rid, "rtype": "room"}}],
        },
        "metadata": {"name": name},
    }
    return _post("behavior_instance", payload)


def update_schedule(rid: str, payload: dict) -> dict:
    """Update a schedule behavior_instance."""
    return _put("behavior_instance", rid, payload)


def delete_schedule(rid: str) -> dict:
    """Delete a schedule behavior_instance."""
    return _delete("behavior_instance", rid)


def recall_scene(scene_rid: str) -> dict:
    """Activate a scene immediately on its associated room/zone."""
    return _put("scene", scene_rid, {"recall": {"action": "active"}})
