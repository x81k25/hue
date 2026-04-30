"""Export resolved bridge state to current_state.yaml with explicit point values."""

import yaml
from pathlib import Path
from sync import get_current_bridge_rules
from schedule_model import ALL_DAYS
from paths import CURRENT_STATE_PATH as STATE_FILE, FUTURE_STATE_PATH as FUTURE_STATE_FILE


def _min_to_time(m: int) -> str:
    m = min(m, 24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def resolve_points(rules: list[dict]) -> list[dict]:
    """Convert schedule rules into explicit point values.

    For each rule we emit:
      - If transition > 0: a "from" point at start (previous scene) and a "to" point at end (new scene)
      - If transition == 0: a single point at start (new scene)

    When a new rule starts before a previous transition finishes,
    the previous transition is truncated — the "from" scene for the new rule
    is the TARGET of the previous rule (what it was transitioning toward).
    """
    if not rules:
        return [{"time": "00:00", "scene": "Off"}]

    sorted_rules = sorted(rules, key=lambda r: (r["hour"], r["minute"]))

    raw_points: list[tuple[int, str]] = []  # (minute, scene)

    # always start with Off at 00:00
    first = sorted_rules[0]
    if first["hour"] != 0 or first["minute"] != 0:
        raw_points.append((0, "Off"))

    # walk rules in order, tracking the scene that is fully settled
    settled_scene = "Off"

    for rule in sorted_rules:
        start_min = rule["hour"] * 60 + rule["minute"]
        trans_min = rule.get("transition_minutes", 0)
        new_scene = rule["scene"]

        if trans_min > 0:
            # "from" point: the settled scene at the moment this transition starts
            raw_points.append((start_min, settled_scene))
            # "to" point: the new scene once transition completes
            end_min = min(start_min + trans_min, 24 * 60)
            raw_points.append((end_min, new_scene))
        else:
            raw_points.append((start_min, new_scene))

        # after this rule, the new scene becomes the settled scene
        settled_scene = new_scene

    # sort by time, then deduplicate
    raw_points.sort(key=lambda p: p[0])

    # deduplicate: if same time appears twice, keep only the last one
    # (later rule at same time wins), unless scenes differ (transition boundary)
    deduped: list[tuple[int, str]] = []
    for minute, scene in raw_points:
        if deduped and deduped[-1][0] == minute:
            if deduped[-1][1] == scene:
                continue  # exact duplicate
            # same time, different scene — the later one is the transition endpoint
            # keep both only if they represent a real from->to at that instant
            # but if previous point is the "from" and this is the "to", collapse
            deduped[-1] = (minute, scene)
        else:
            deduped.append((minute, scene))

    return [{"time": _min_to_time(m), "scene": s} for m, s in deduped]


def export_current_state() -> dict:
    """Build full state for all rooms, all days.

    Includes both raw bridge rules and resolved point values.
    """
    bridge_rules = get_current_bridge_rules()

    # collect unique rooms
    all_rooms = sorted(set(r["room"] for r in bridge_rules))

    state = {"rooms": {}}

    for room in all_rooms:
        state["rooms"][room] = {}
        for day in ALL_DAYS:
            day_rules = sorted(
                [r for r in bridge_rules if r["room"] == room and day in r["days"]],
                key=lambda r: (r["hour"], r["minute"]),
            )
            raw = []
            for r in day_rules:
                raw.append({
                    "name": r["name"],
                    "time": f"{r['hour']:02d}:{r['minute']:02d}",
                    "scene": r["scene"],
                    "transition_minutes": r.get("transition_minutes", 0),
                })
            points = resolve_points(day_rules)
            state["rooms"][room][day] = {
                "raw": raw,
                "resolved": points,
            }

    return state


def save_current_state() -> Path:
    """Export and save to config/current_state.yaml."""
    state = export_current_state()
    with open(STATE_FILE, "w") as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)
    return STATE_FILE


def save_deduped_future_state() -> Path:
    """Read current_state.yaml, remove duplicate raw entries, save as future_state.yaml."""
    with open(STATE_FILE) as f:
        state = yaml.safe_load(f)

    for room, days in state.get("rooms", {}).items():
        for day, day_data in days.items():
            raw = day_data.get("raw", [])
            seen = set()
            deduped = []
            for entry in raw:
                key = (entry["name"], entry["time"], entry["scene"],
                       entry.get("transition_minutes", 0))
                if key not in seen:
                    seen.add(key)
                    deduped.append(entry)
            day_data["raw"] = deduped

    with open(FUTURE_STATE_FILE, "w") as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)
    return FUTURE_STATE_FILE


if __name__ == "__main__":
    path = save_current_state()
    print(f"Saved to {path}")
