"""Path resolution for config and state files.

CONFIG_DIR can be overridden via HUE_CONFIG_DIR env var (used in container
deployments where state lives on a mounted volume).
"""

import os
from pathlib import Path

_DEFAULT = Path(__file__).parent / "config"
CONFIG_DIR = Path(os.environ.get("HUE_CONFIG_DIR", str(_DEFAULT)))
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

ROOMS_PATH = CONFIG_DIR / "rooms.yaml"
SCENES_PATH = CONFIG_DIR / "scenes.yaml"
CURRENT_STATE_PATH = CONFIG_DIR / "current_state.yaml"
FUTURE_STATE_PATH = CONFIG_DIR / "future_state.yaml"
DIFF_PATH = CONFIG_DIR / "diff.yaml"
SCHEDULE_FILE = CONFIG_DIR / "schedules.yaml"
