"""Hue Schedule Manager — Streamlit multipage app entry point.

Thin UI layer; all state and bridge interactions go through the FastAPI
service via api_client.
"""

import streamlit as st
import api_client

st.set_page_config(page_title="Hue Schedules", layout="wide")


@st.cache_data(ttl=30)
def fetch_rooms() -> dict[str, str]:
    return api_client.get_rooms()


@st.cache_data(ttl=30)
def fetch_scenes_by_room() -> dict[str, dict[str, str]]:
    return api_client.get_scenes_by_room()


@st.cache_data(ttl=30)
def fetch_bridge_rules() -> list[dict]:
    return api_client.get_bridge_rules()


@st.cache_data(ttl=300)
def fetch_bridge_ip() -> str:
    return api_client.bridge_ip()


# ── sidebar: bridge status (shared across all pages) ──
with st.sidebar:
    st.header("Bridge Status")
    try:
        rooms = fetch_rooms()
        bridge_rules = fetch_bridge_rules()
        st.text(f"IP: {fetch_bridge_ip()}")
        st.text(f"Rooms: {len(rooms)}")
        st.text(f"Active schedules: {len(bridge_rules)}")
    except Exception as e:
        st.error(f"API unreachable: {e}")
    if st.button("Refresh bridge data"):
        st.cache_data.clear()
        st.rerun()

# ── home page ──
st.title("Hue Schedule Manager")
st.markdown(
    "Use the sidebar to navigate between pages:\n"
    "- **Edit Schedules** — create and modify schedule rules\n"
    "- **Bridge View** — see what's currently on the bridge\n"
    "- **Sync** — preview and apply changes to the bridge"
)
