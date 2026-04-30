"""Sync schedules to bridge."""

import streamlit as st
import pandas as pd
from collections import defaultdict
import api_client

st.set_page_config(page_title="Sync", layout="wide")
st.title("Sync Schedules to Bridge")

# --- Step 1: Reload current state ---
if st.button("Reload current state"):
    api_client.refresh_current_state()
    st.session_state.pop("sync_diff", None)
    st.session_state.pop("dup_diff", None)

    dups = api_client.get_bridge_duplicates()
    if dups:
        st.session_state.dup_diff = {"create": [], "update": [], "delete": dups}
        api_client.dedupe_future_state()
        st.success("Reloaded current state.")
        st.warning(
            f"Found **{len(dups)}** duplicate routines on the bridge. "
            f"Deduped future state saved."
        )
    else:
        st.success("Reloaded — no duplicates found.")

if st.button("Copy current state → future state"):
    api_client.copy_current_to_future()
    st.session_state.pop("sync_diff", None)
    st.success("Copied current state to future state.")

st.divider()

# --- Step 2: Show and apply duplicate cleanup ---
if "dup_diff" in st.session_state:
    diff = st.session_state.dup_diff

    st.subheader("Duplicate Cleanup")
    st.metric("Duplicates to delete", len(diff["delete"]))

    dup_rows = defaultdict(list)
    for r in diff["delete"]:
        dup_rows[r["room"]].append(r["name"])

    if dup_rows:
        table_data = []
        for room in sorted(dup_rows.keys()):
            for i, name in enumerate(dup_rows[room]):
                table_data.append({
                    "Room": room if i == 0 else "",
                    "Duplicate to delete": name,
                })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    if st.button("Delete duplicates from bridge", type="primary"):
        results = api_client.cleanup_duplicates()
        st.cache_data.clear()
        if results.get("errors"):
            st.error(f"Errors: {results['errors']}")
        st.success(f"Deleted {len(results.get('deleted', []))} duplicate routines.")
        del st.session_state.dup_diff

    st.divider()

# --- Step 3: Normal future-state sync ---
if st.button("Preview diff"):
    diff = api_client.sync_preview()
    st.session_state.sync_diff = diff

if "sync_diff" in st.session_state:
    diff = st.session_state.sync_diff

    col_c, col_u, col_d = st.columns(3)
    with col_c:
        st.metric("Create", len(diff["create"]))
    with col_u:
        st.metric("Update", len(diff["update"]))
    with col_d:
        st.metric("Delete", len(diff["delete"]))

    rows = defaultdict(lambda: {"Create": [], "Update": [], "Delete": []})
    for r in diff["create"]:
        rows[r["room"]]["Create"].append(r["name"])
    for r in diff["update"]:
        rows[r["room"]]["Update"].append(r["name"])
    for r in diff["delete"]:
        rows[r["room"]]["Delete"].append(r["name"])

    if rows:
        table_data = []
        for room in sorted(rows.keys()):
            max_len = max(
                len(rows[room]["Create"]),
                len(rows[room]["Update"]),
                len(rows[room]["Delete"]),
                1,
            )
            for i in range(max_len):
                table_data.append({
                    "Room": room if i == 0 else "",
                    "Create": rows[room]["Create"][i] if i < len(rows[room]["Create"]) else "",
                    "Update": rows[room]["Update"][i] if i < len(rows[room]["Update"]) else "",
                    "Delete": rows[room]["Delete"][i] if i < len(rows[room]["Delete"]) else "",
                })
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    if diff["create"] or diff["update"] or diff["delete"]:
        if st.button("Apply to bridge", type="primary", key="apply_sync"):
            results = api_client.sync_apply()
            st.cache_data.clear()
            if results.get("errors"):
                st.error(f"Errors: {results['errors']}")
            st.success(
                f"Created: {len(results.get('created', []))}, "
                f"Updated: {len(results.get('updated', []))}, "
                f"Deleted: {len(results.get('deleted', []))}"
            )
            del st.session_state.sync_diff
    else:
        st.success("Bridge is in sync with YAML.")
