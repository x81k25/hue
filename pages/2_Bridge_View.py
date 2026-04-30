"""View current bridge schedules."""

import streamlit as st
import pandas as pd
from app import fetch_bridge_rules

st.set_page_config(page_title="Bridge View", layout="wide")
st.title("Bridge View")

bridge_rules = fetch_bridge_rules()

if bridge_rules:
    df = pd.DataFrame(bridge_rules)
    df = df[["name", "room", "hour", "minute", "scene", "days", "enabled", "transition_minutes"]]
    df = df.sort_values(["room", "hour", "minute"]).reset_index(drop=True)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No schedule routines found on bridge.")
