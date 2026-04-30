"""Single room timeline: gradient bar + schedule chart side by side."""

import streamlit as st
import api_client

st.set_page_config(page_title="Single Room", layout="wide")
st.title("Single Room Timeline")

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


def render_single_room(spans: list[dict], raw: list[dict], room: str):
    spans_rev = list(reversed(spans))

    hour_labels = ""
    for h in range(25):
        bottom_pct = (h * 60) / TOTAL_MINUTES * 100
        hour_labels += (
            f'<div style="position:absolute; bottom:{bottom_pct:.2f}%; right:4px; '
            f'font-size:11px; color:#aaa; transform:translateY(50%);">{h:02d}:00</div>'
        )

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

    markers = ""
    for r in raw:
        start_min = parse_time(r["time"])
        trans_min = r.get("transition_minutes", 0)
        bottom_pct = start_min / TOTAL_MINUTES * 100
        color = scene_color(r["scene"])

        if trans_min > 0:
            bar_h_pct = trans_min / TOTAL_MINUTES * 100
            trans_label = f"{trans_min}min fade"
        else:
            bar_h_pct = 0
            trans_label = "instant"

        markers += f'<div style="position:absolute; bottom:{bottom_pct:.2f}%; left:0; width:100%; z-index:2;">'

        if bar_h_pct > 0:
            markers += (
                f'<div style="position:absolute; bottom:0; left:0; width:8px; '
                f'height:{bar_h_pct / 100 * TOTAL_HEIGHT}px; '
                f'background:linear-gradient(to top, rgba(255,255,255,0.1), {color}); '
                f'border-radius:2px;"></div>'
            )

        markers += (
            f'<div style="position:absolute; bottom:-1px; left:16px; '
            f'white-space:nowrap; font-size:12px; line-height:1.4;">'
            f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
            f'border-radius:2px;vertical-align:middle;margin-right:6px;"></span>'
            f'<span style="color:#ddd;">{r["time"]}</span>'
            f'<span style="color:#888; margin:0 6px;">—</span>'
            f'<span style="color:#ddd; font-weight:bold;">{SCENE_NAME_TO_ABBR.get(r["scene"], r["scene"])}</span>'
            f'<span style="color:#666; margin-left:8px; font-size:11px;">{trans_label}</span>'
            f'</div>'
        )
        markers += '</div>'

    chart_gridlines = ""
    for h in range(1, 24):
        bottom_pct = (h * 60) / TOTAL_MINUTES * 100
        chart_gridlines += (
            f'<div style="position:absolute; bottom:{bottom_pct:.2f}%; left:0; '
            f'width:100%; height:1px; background:#444; z-index:3;"></div>'
        )

    html = f"""
    <div style="display:flex; gap:0; font-family:monospace;">
        <div style="width:50px; position:relative; height:{TOTAL_HEIGHT}px; flex-shrink:0;">
            {hour_labels}
        </div>
        <div style="width:80px; position:relative; flex-shrink:0;">
            <div style="margin-bottom:8px; font-weight:bold; font-size:14px; color:#ddd; text-align:center;">{room}</div>
            <div style="position:relative; height:{TOTAL_HEIGHT}px; background:#111; border-radius:6px; overflow:hidden;">
                <div style="position:relative; z-index:1; width:100%; height:100%; display:flex; flex-direction:column;">
                    {cell_html}
                </div>
                {gridlines}
            </div>
        </div>
        <div style="flex:1; position:relative; margin-left:12px;">
            <div style="margin-bottom:8px; font-weight:bold; font-size:14px; color:#ddd;">Schedule</div>
            <div style="position:relative; height:{TOTAL_HEIGHT}px;">
                {chart_gridlines}
                {markers}
            </div>
        </div>
    </div>
    """
    st.html(html)


# ── page UI ──
with st.sidebar:
    if st.button("Refresh from bridge"):
        api_client.refresh_current_state()
        st.rerun()

# state source toggle
state_source = st.radio("State", ["Current", "Future"], horizontal=True)
state = api_client.get_future_state() if state_source == "Future" else api_client.get_current_state()
if not state.get("rooms"):
    api_client.refresh_current_state()
    state = api_client.get_current_state()

rooms_dict = api_client.get_rooms()
rooms = sorted(rooms_dict.keys())
room = st.selectbox("Room", rooms, index=rooms.index("bed1") if "bed1" in rooms else 0)
day = st.selectbox("Day", ALL_DAYS, index=0)

day_data = state.get("rooms", {}).get(room, {}).get(day, {})
resolved = day_data.get("resolved", [])
raw = day_data.get("raw", [])

if resolved:
    spans = build_spans(resolved)
    render_single_room(spans, raw, room)
else:
    st.info(f"No schedules for **{room}** on **{day}**.")
