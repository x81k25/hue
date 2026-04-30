"""Multi-room timeline: gradient columns for all selected rooms, schedule charts below."""

import streamlit as st
import api_client

st.set_page_config(page_title="Multi Room", layout="wide")
st.title("Multi Room Timeline")

ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

_scenes_list = api_client.get_scenes_config()
SCENE_COLORS = {s["name"]: s["color"] for s in _scenes_list}
SCENE_NAME_TO_ABBR = {s["name"]: s["abbr"] for s in _scenes_list}

OFF_COLOR = SCENE_COLORS.get("Off", "#000000")
DEFAULT_COLOR = OFF_COLOR
TOTAL_MINUTES = 24 * 60
TOTAL_HEIGHT = 800


def scene_color(name: str) -> str:
    return SCENE_COLORS.get(name, DEFAULT_COLOR)


def parse_time(t: str) -> int:
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def build_spans(points: list[dict]) -> list[dict]:
    if not points:
        return [{"from_color": OFF_COLOR, "to_color": OFF_COLOR, "scene": "Off",
                 "from_scene": "Off", "start_min": 0, "end_min": TOTAL_MINUTES, "transition": False}]
    spans = []
    for i in range(len(points)):
        start_min = parse_time(points[i]["time"])
        from_scene = points[i]["scene"]
        from_color = scene_color(from_scene)
        if i + 1 < len(points):
            end_min = parse_time(points[i + 1]["time"])
            to_scene = points[i + 1]["scene"]
        else:
            end_min = TOTAL_MINUTES
            to_scene = from_scene
        if end_min <= start_min:
            continue
        to_color = scene_color(to_scene)
        spans.append({
            "from_color": from_color, "to_color": to_color,
            "scene": to_scene if from_scene != to_scene else from_scene,
            "from_scene": from_scene, "start_min": start_min, "end_min": end_min,
            "transition": from_scene != to_scene,
        })
    return spans


def render_multi_gradient(room_spans: dict[str, list[dict]]):
    room_names = list(room_spans.keys())

    hour_labels = ""
    for h in range(25):
        bottom_pct = (h * 60) / TOTAL_MINUTES * 100
        hour_labels += (
            f'<div style="position:absolute; bottom:{bottom_pct:.2f}%; right:4px; '
            f'font-size:11px; color:#aaa; transform:translateY(50%);">{h:02d}:00</div>'
        )

    room_columns = ""
    for room in room_names:
        spans_rev = list(reversed(room_spans[room]))
        cell_html = ""
        for span in spans_rev:
            duration = span["end_min"] - span["start_min"]
            height_pct = duration / TOTAL_MINUTES * 100
            if span["transition"]:
                bg = f"background:linear-gradient(to top, {span['from_color']}, {span['to_color']});"
            else:
                bg = f"background:{span['from_color']};"
            cell_html += f'<div style="width:100%; height:{height_pct:.3f}%; {bg} box-sizing:border-box;"></div>'

        gridlines = ""
        for h in range(1, 24):
            bottom_pct = (h * 60) / TOTAL_MINUTES * 100
            gridlines += (
                f'<div style="position:absolute; bottom:{bottom_pct:.2f}%; left:0; '
                f'width:100%; height:1px; background:#444; z-index:3;"></div>'
            )

        room_columns += f"""
        <div style="flex:1; min-width:40px;">
            <div style="margin-bottom:8px; font-weight:bold; font-size:13px; color:#ddd; text-align:center;">{room}</div>
            <div style="position:relative; height:{TOTAL_HEIGHT}px; background:#111; border-radius:6px; overflow:hidden;">
                <div style="position:relative; z-index:1; width:100%; height:100%; display:flex; flex-direction:column;">
                    {cell_html}
                </div>
                {gridlines}
            </div>
        </div>
        """

    html = f"""
    <div style="display:flex; gap:4px; font-family:monospace;">
        <div style="width:50px; position:relative; height:{TOTAL_HEIGHT}px; flex-shrink:0; margin-top:22px;">
            {hour_labels}
        </div>
        {room_columns}
    </div>
    """
    st.html(html)


def render_multi_schedules(room_raws: dict[str, list[dict]]):
    room_names = list(room_raws.keys())
    cols = st.columns(len(room_names))

    for idx, room in enumerate(room_names):
        raw = room_raws[room]
        with cols[idx]:
            st.markdown(f"**{room}**")
            if not raw:
                st.caption("No schedules")
                continue
            for r in raw:
                trans_min = r.get("transition_minutes", 0)
                trans_label = f"{trans_min}m" if trans_min > 0 else ""
                color = scene_color(r["scene"])
                st.markdown(
                    f'<div style="font-family:monospace; font-size:12px; margin-bottom:2px;">'
                    f'<span style="display:inline-block;width:8px;height:8px;background:{color};'
                    f'border-radius:2px;vertical-align:middle;margin-right:4px;"></span>'
                    f'<span style="color:#aaa;">{r["time"]}</span> '
                    f'<span style="color:#ddd;">{SCENE_NAME_TO_ABBR.get(r["scene"], r["scene"])}</span> '
                    f'<span style="color:#666;">{trans_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ── page UI ──
with st.sidebar:
    if st.button("Refresh from bridge"):
        api_client.refresh_current_state()
        st.rerun()

state_source = st.radio("State", ["Current", "Future"], horizontal=True)
state = api_client.get_future_state() if state_source == "Future" else api_client.get_current_state()
if not state.get("rooms"):
    api_client.refresh_current_state()
    state = api_client.get_current_state()

rooms_dict = api_client.get_rooms()
all_rooms = sorted(rooms_dict.keys())
if "selected_rooms" not in st.session_state:
    st.session_state.selected_rooms = all_rooms
selected_rooms = st.multiselect("Rooms", all_rooms, default=st.session_state.selected_rooms, key="selected_rooms")
day = st.selectbox("Day", ALL_DAYS, index=0)

if selected_rooms:
    room_spans = {}
    room_raws = {}
    for room in selected_rooms:
        day_data = state.get("rooms", {}).get(room, {}).get(day, {})
        resolved = day_data.get("resolved", [])
        raw = day_data.get("raw", [])
        room_spans[room] = build_spans(resolved)
        room_raws[room] = raw

    render_multi_gradient(room_spans)

    st.divider()
    render_multi_schedules(room_raws)
else:
    st.info("Select at least one room.")
