"""Edit schedule rules."""

import streamlit as st
import api_client
from app import fetch_rooms

st.set_page_config(page_title="Edit Schedules", layout="wide")
st.title("Edit Schedules")
st.caption("Each rule creates one bridge routine per selected room.")

ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

rooms = fetch_rooms()
room_names = sorted(rooms.keys())

# scene config — fetched from API
_scenes_cfg = api_client.get_scenes_config()
_scenes_by_cat: dict[str, list[str]] = {}
_scene_colors: dict[str, str] = {}
for s in _scenes_cfg:
    _scenes_by_cat.setdefault(s.get("category", "custom"), []).append(s["name"])
    _scene_colors[s["name"]] = s.get("color", "#888")

show_colorful = st.checkbox("Show colorful scenes", value=False)

_included_cats = ["standard", "special"]
if show_colorful:
    _included_cats.append("colorful")
available_scenes = sorted(
    name for cat in _included_cats for name in _scenes_by_cat.get(cat, [])
)


def _color_square(scene: str) -> str:
    color = _scene_colors.get(scene, "#888")
    return (f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
            f'border-radius:2px;vertical-align:middle;margin-right:6px;"></span>')


# ── add new rule ──
with st.expander("Add new rule", expanded=True):
    with st.form("new_rule", clear_on_submit=True):
        new_scene = st.selectbox("Scene", available_scenes, key="new_scene")
        new_time_str = st.text_input("Time (HHMM)", value="", key="new_time")
        new_trans_str = st.text_input("Transition (min)", value="", key="new_trans")

        new_rooms = st.multiselect("Rooms", room_names, key="new_rooms")
        new_days = st.multiselect("Days", ALL_DAYS, default=ALL_DAYS, key="new_days")

        if st.form_submit_button("Add rule"):
            errors = []
            if not new_rooms:
                errors.append("Select at least one room.")
            if not new_scene:
                errors.append("Select a scene.")
            new_hour = None
            new_minute = None
            t = new_time_str.strip()
            if not t:
                errors.append("Time is required.")
            elif not t.isdigit() or len(t) != 4:
                errors.append("Time must be 4 digits (HHMM).")
            else:
                new_hour = int(t[:2])
                new_minute = int(t[2:])
                if not 0 <= new_hour <= 23:
                    errors.append("Hour must be 00-23.")
                if not 0 <= new_minute <= 59:
                    errors.append("Minute must be 00-59.")
            new_transition = None
            if not new_trans_str.strip():
                errors.append("Transition is required.")
            else:
                try:
                    new_transition = int(new_trans_str)
                    if not 0 <= new_transition <= 120:
                        errors.append("Transition must be 0-120.")
                except ValueError:
                    errors.append("Transition must be a number.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                api_client.add_future_rule(
                    scene=new_scene,
                    hour=new_hour,
                    minute=new_minute,
                    rooms=new_rooms,
                    days=new_days,
                    transition_minutes=new_transition,
                )
                st.success(f"Added to future state: {new_scene} at {new_hour:02d}:{new_minute:02d}")
                st.rerun()


# reduce vertical spacing between rows
st.html('''<style>
[data-testid="stExpander"]:last-of-type [data-testid="stVerticalBlock"] > div:has(> [data-testid="stHorizontalBlock"]) { margin-top:-8px; }
[data-testid="stExpander"]:last-of-type [data-testid="stHorizontalBlock"] { gap:0 !important; }
[data-testid="stExpander"]:last-of-type [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
    flex:0 0 90px !important; max-width:90px !important;
}
[data-testid="stExpander"]:first-of-type [data-testid="stVerticalBlock"] > div { margin-top:initial !important; }
[data-testid="stExpander"]:first-of-type [data-testid="stHorizontalBlock"] { gap:initial !important; }
</style>''')

# ── delete routines ──
with st.expander("Delete routines"):
    delete_source = st.radio("Source", ["Bridge (current)", "Future state"],
                             horizontal=True, key="delete_source")

    if delete_source == "Bridge (current)":
        if st.button("Refresh", key="refresh_bridge"):
            st.cache_data.clear()

        bridge_rules = api_client.get_bridge_rules()

        if not bridge_rules:
            st.info("No routines on the bridge.")
        else:
            by_room: dict[str, list[dict]] = {}
            for rule in sorted(bridge_rules, key=lambda r: (r["room"], r["hour"], r["minute"])):
                by_room.setdefault(rule["room"], []).append(rule)

            if "delete_confirm" not in st.session_state:
                st.session_state.delete_confirm = set()

            deleted_any = False
            for room_name in sorted(by_room.keys()):
                st.markdown(f"**{room_name}**")
                for rule in by_room[room_name]:
                    rid = rule["rid"]
                    trans = f" ({rule['transition_minutes']}m)" if rule["transition_minutes"] else ""
                    sq = _color_square(rule["scene"])

                    col_btn, col_info = st.columns([1, 8], gap="small")
                    with col_btn:
                        if rid in st.session_state.delete_confirm:
                            if st.button("Confirm", key=f"conf_{rid}", type="primary"):
                                try:
                                    api_client.delete_bridge_rule(rid)
                                    st.toast(f"Deleted {rule['name']}")
                                    deleted_any = True
                                except Exception as e:
                                    st.error(f"Failed: {e}")
                                st.session_state.delete_confirm.discard(rid)
                        else:
                            if st.button("Delete", key=f"del_{rid}"):
                                st.session_state.delete_confirm.add(rid)
                                st.rerun()
                    with col_info:
                        st.html(
                            f'<div style="font-family:monospace;font-size:13px;padding-top:6px;">'
                            f'{sq}<span style="color:#ddd;">{rule["hour"]:02d}:{rule["minute"]:02d}</span>'
                            f'<span style="color:#888;margin:0 4px;">—</span>'
                            f'<span style="color:#ddd;font-weight:bold;">{rule["scene"]}</span>'
                            f'<span style="color:#666;margin-left:6px;">{trans}</span></div>'
                        )

            if deleted_any:
                st.cache_data.clear()
                st.rerun()

    else:  # Future state
        future_rules = api_client.list_future_rules()

        if not future_rules:
            st.info("No routines in future state.")
        else:
            by_room_f: dict[str, list[dict]] = {}
            for rule in future_rules:
                by_room_f.setdefault(rule["room"], []).append(rule)

            for room_name in sorted(by_room_f.keys()):
                st.markdown(f"**{room_name}**")
                for rule in by_room_f[room_name]:
                    trans = f" ({rule['transition_minutes']}m)" if rule["transition_minutes"] else ""
                    sq = _color_square(rule["scene"])

                    col_btn, col_info = st.columns([1, 8], gap="small")
                    with col_btn:
                        if st.button("Delete", key=f"fdel_{rule['name']}"):
                            api_client.delete_future_rule(rule["name"])
                            st.toast(f"Removed {rule['name']} from future state")
                            st.rerun()
                    with col_info:
                        st.html(
                            f'<div style="font-family:monospace;font-size:13px;padding-top:6px;">'
                            f'{sq}<span style="color:#ddd;">{rule["time"]}</span>'
                            f'<span style="color:#888;margin:0 4px;">—</span>'
                            f'<span style="color:#ddd;font-weight:bold;">{rule["scene"]}</span>'
                            f'<span style="color:#666;margin-left:6px;">{trans}</span></div>'
                        )
