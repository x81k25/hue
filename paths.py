"""Path resolution for config and state files.

CONFIG_DIR can be overridden via HUE_CONFIG_DIR env var (used in container
deployments where state lives on a mounted volume).

If HUE_SEED_DIR is set and CONFIG_DIR is missing seed files, they are
copied in on import so a fresh persistent volume gets bootstrapped from
files baked into the image.
"""

import os
import shutil
from pathlib import Path

_DEFAULT = Path(__file__).parent / "config"
CONFIG_DIR = Path(os.environ.get("HUE_CONFIG_DIR", str(_DEFAULT)))
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

_SEED_DIR = os.environ.get("HUE_SEED_DIR")
if _SEED_DIR:
    seed_path = Path(_SEED_DIR)
    if seed_path.is_dir():
        for src in seed_path.iterdir():
            dst = CONFIG_DIR / src.name
            if not dst.exists():
                shutil.copy2(src, dst)

ROOMS_PATH = CONFIG_DIR / "rooms.yaml"
SCENES_PATH = CONFIG_DIR / "scenes.yaml"
CURRENT_STATE_PATH = CONFIG_DIR / "current_state.yaml"
FUTURE_STATE_PATH = CONFIG_DIR / "future_state.yaml"
DIFF_PATH = CONFIG_DIR / "diff.yaml"
SCHEDULE_FILE = CONFIG_DIR / "schedules.yaml"
