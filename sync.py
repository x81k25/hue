"""Sync desired schedules to the Hue bridge."""

import yaml
import hue_client
from schedule_model import load_schedules, expand_to_bridge_rules, diff_schedules
from paths import CURRENT_STATE_PATH, FUTURE_STATE_PATH


def parse_bridge_instance(instance: dict, room_names: dict[str, str], scene_lookup: dict) -> dict | None:
    """Parse a bridge behavior_instance into a comparable dict."""
    config = instance.get("configuration", {})
    what = config.get("what", [{}])[0]
    where = config.get("where", [{}])[0]
    when = config.get("when_extended", {})

    room_rid = where.get("group", {}).get("rid", "")
    # reverse lookup room name
    rid_to_name = {v: k for k, v in room_names.items()}
    room_name = rid_to_name.get(room_rid, "")
    if not room_name:
        return None

    recall = what.get("recall", {})
    recall_rid = recall.get("rid", "")
    recall_rtype = recall.get("rtype", "")

    # resolve scene name from rid
    scene_name = scene_lookup.get(recall_rid, "")
    if not scene_name:
        # check recipes
        recipe_names = {v: k for k, v in hue_client.RECIPES.items()}
        scene_name = recipe_names.get(recall_rid, "unknown")

    time_point = when.get("start_at", {}).get("time_point", {}).get("time", {})
    transition = when.get("start_at", {}).get("transition", {})
    transition_minutes = 0
    if "duration" in transition:
        transition_minutes = transition["duration"] // (60 * 1000)
    elif "hours" in transition:
        transition_minutes = transition["hours"] * 60
    elif "minutes" in transition:
        transition_minutes = transition["minutes"]

    return {
        "name": instance["metadata"]["name"],
        "rid": instance["id"],
        "room": room_name,
        "hour": time_point.get("hour", 0),
        "minute": time_point.get("minute", 0),
        "scene": scene_name,
        "days": when.get("recurrence_days", []),
        "transition_minutes": transition_minutes,
        "enabled": instance.get("enabled", True),
    }


def get_current_bridge_rules() -> list[dict]:
    """Fetch and parse all schedule instances from the bridge."""
    room_names = hue_client.get_rooms()
    scenes = hue_client.get_scenes()
    # build rid -> name lookup for scenes
    scene_lookup = {s["id"]: s["metadata"]["name"] for s in scenes}

    instances = hue_client.get_schedule_instances()
    rules = []
    for inst in instances:
        parsed = parse_bridge_instance(inst, room_names, scene_lookup)
        if parsed:
            rules.append(parsed)
    return rules


def _flatten_state_to_rules(state: dict) -> list[dict]:
    """Flatten a state YAML (rooms -> days -> raw) into a deduplicated list of rules.

    Since raw entries are nested under each day, we collect all days a routine
    appears under and merge them into one rule with a combined days list.
    """
    # collect days per (name, room)
    rule_days: dict[tuple[str, str], list[str]] = {}
    rule_data: dict[tuple[str, str], dict] = {}

    for room, days in state.get("rooms", {}).items():
        for day, day_data in days.items():
            for r in day_data.get("raw", []):
                key = (r["name"], room)
                if key not in rule_data:
                    parts = r["time"].split(":")
                    rule_data[key] = {
                        "name": r["name"],
                        "room": room,
                        "hour": int(parts[0]),
                        "minute": int(parts[1]),
                        "scene": r["scene"],
                        "transition_minutes": r.get("transition_minutes", 0),
                        "enabled": r.get("enabled", True),
                    }
                    rule_days[key] = []
                if day not in rule_days[key]:
                    rule_days[key].append(day)

    rules = []
    for key, data in rule_data.items():
        data["days"] = rule_days[key]
        rules.append(data)
    return rules


def find_bridge_duplicates() -> list[dict]:
    """Find duplicate behavior_instances on the bridge.

    Groups rules by (name, room). For each group with >1 entry, keeps the first
    and returns the rest as rules to delete (with rid).
    """
    bridge_rules = get_current_bridge_rules()
    seen: dict[tuple[str, str], dict] = {}
    duplicates = []

    for rule in bridge_rules:
        key = (rule["name"], rule["room"])
        if key in seen:
            duplicates.append(rule)
        else:
            seen[key] = rule

    return duplicates


def preview_sync() -> dict:
    """Preview diff between future_state.yaml and current_state.yaml."""
    if not FUTURE_STATE_PATH.exists():
        return {"create": [], "update": [], "delete": []}

    with open(FUTURE_STATE_PATH) as f:
        future = yaml.safe_load(f)
    with open(CURRENT_STATE_PATH) as f:
        current = yaml.safe_load(f)

    desired = _flatten_state_to_rules(future)
    existing = _flatten_state_to_rules(current)

    # add rid from bridge for existing rules so deletes/updates can reference them
    bridge_rules = get_current_bridge_rules()
    bridge_by_name = {r["name"]: r for r in bridge_rules}
    for rule in existing:
        bridge_match = bridge_by_name.get(rule["name"])
        if bridge_match:
            rule["rid"] = bridge_match["rid"]

    return diff_schedules(desired, existing)


def apply_sync(diff: dict) -> dict:
    """Apply a diff to the bridge. Returns summary of actions taken."""
    room_names = hue_client.get_rooms()
    scenes_by_room = hue_client.get_scenes_by_room()
    results = {"created": [], "deleted": [], "updated": [], "errors": []}

    for rule in diff["delete"]:
        try:
            hue_client.delete_schedule(rule["rid"])
            results["deleted"].append(rule["name"])
        except Exception as e:
            results["errors"].append(f"delete {rule['name']}: {e}")

    for rule in diff["create"]:
        try:
            room_rid = room_names[rule["room"]]
            scene_ref = hue_client.resolve_scene_ref(room_rid, rule["scene"], scenes_by_room)
            hue_client.create_schedule(
                name=rule["name"],
                room_rid=room_rid,
                scene_ref=scene_ref,
                hour=rule["hour"],
                minute=rule["minute"],
                days=rule["days"],
                transition_minutes=rule["transition_minutes"],
                enabled=rule["enabled"],
            )
            results["created"].append(rule["name"])
        except Exception as e:
            results["errors"].append(f"create {rule['name']}: {e}")

    for rule in diff["update"]:
        try:
            room_rid = room_names[rule["room"]]
            scene_ref = hue_client.resolve_scene_ref(room_rid, rule["scene"], scenes_by_room)
            start_at = {
                "time_point": {
                    "time": {"hour": rule["hour"], "minute": rule["minute"]},
                    "type": "time",
                }
            }
            if rule["transition_minutes"] > 0:
                tm = rule["transition_minutes"]
                if tm >= 60 and tm % 60 == 0:
                    start_at["transition"] = {"hours": tm // 60}
                else:
                    start_at["transition"] = {"minutes": tm}
            payload = {
                "enabled": rule["enabled"],
                "configuration": {
                    "what": [{"group": {"rid": room_rid, "rtype": "room"}, "recall": scene_ref}],
                    "when_extended": {
                        "recurrence_days": rule["days"],
                        "start_at": start_at,
                    },
                    "where": [{"group": {"rid": room_rid, "rtype": "room"}}],
                },
                "metadata": {"name": rule["name"]},
            }
            hue_client.update_schedule(rule["rid"], payload)
            results["updated"].append(rule["name"])
        except Exception as e:
            results["errors"].append(f"update {rule['name']}: {e}")

    return results
