"""Schedule model: YAML/JSON <-> bridge sync logic."""

import yaml
from dataclasses import dataclass, field, asdict
from paths import SCHEDULE_FILE

DAYS_PRESETS = {
    "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "weekends": ["saturday", "sunday"],
    "daily": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
}

ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@dataclass
class ScheduleEntry:
    """One schedule rule: a scene applied to rooms at a time on certain days."""
    name: str
    hour: int
    minute: int
    scene: str
    rooms: list[str]
    days: list[str] = field(default_factory=lambda: list(DAYS_PRESETS["daily"]))
    transition_minutes: int = 0
    enabled: bool = True


def load_schedules() -> list[ScheduleEntry]:
    """Load schedule entries from YAML."""
    if not SCHEDULE_FILE.exists():
        return []
    with open(SCHEDULE_FILE) as f:
        data = yaml.safe_load(f) or {}
    entries = []
    for item in data.get("schedules", []):
        # expand day presets
        days = item.get("days", "daily")
        if isinstance(days, str) and days in DAYS_PRESETS:
            days = list(DAYS_PRESETS[days])
        elif isinstance(days, str):
            days = [days]
        entries.append(ScheduleEntry(
            name=item["name"],
            hour=item["hour"],
            minute=item["minute"],
            scene=item["scene"],
            rooms=item["rooms"],
            days=days,
            transition_minutes=item.get("transition_minutes", 0),
            enabled=item.get("enabled", True),
        ))
    return entries


def save_schedules(entries: list[ScheduleEntry]) -> None:
    """Save schedule entries to YAML."""
    data = {"schedules": []}
    for e in entries:
        item = {
            "name": e.name,
            "hour": e.hour,
            "minute": e.minute,
            "scene": e.scene,
            "rooms": e.rooms,
            "days": e.days,
            "transition_minutes": e.transition_minutes,
            "enabled": e.enabled,
        }
        data["schedules"].append(item)
    with open(SCHEDULE_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def expand_to_bridge_rules(entries: list[ScheduleEntry]) -> list[dict]:
    """Expand entries into per-room bridge rules (one behavior_instance per room per entry)."""
    rules = []
    for entry in entries:
        for room in entry.rooms:
            rule_name = f"{room}-{entry.hour:02d}{entry.minute:02d}-{entry.scene.lower().replace(' ', '-')}"
            rules.append({
                "name": rule_name,
                "room": room,
                "hour": entry.hour,
                "minute": entry.minute,
                "scene": entry.scene,
                "days": entry.days,
                "transition_minutes": entry.transition_minutes,
                "enabled": entry.enabled,
            })
    return rules


def diff_schedules(desired: list[dict], current: list[dict]) -> dict:
    """Diff desired vs current bridge rules.

    Returns {"create": [...], "delete": [...], "update": [...]}.
    current items are dicts with keys: name, rid, room, hour, minute, scene, days, enabled.
    """
    desired_by_name = {r["name"]: r for r in desired}
    current_by_name = {r["name"]: r for r in current}

    to_create = []
    to_delete = []
    to_update = []

    for name, rule in desired_by_name.items():
        if name not in current_by_name:
            to_create.append(rule)
        else:
            cur = current_by_name[name]
            # check if anything changed
            changed = (
                rule["hour"] != cur["hour"]
                or rule["minute"] != cur["minute"]
                or rule["scene"] != cur["scene"]
                or sorted(rule["days"]) != sorted(cur["days"])
                or rule["enabled"] != cur["enabled"]
                or rule["transition_minutes"] != cur.get("transition_minutes", 0)
            )
            if changed:
                to_update.append({**rule, "rid": cur["rid"]})

    for name, cur in current_by_name.items():
        if name not in desired_by_name:
            to_delete.append(cur)

    return {"create": to_create, "delete": to_delete, "update": to_update}
