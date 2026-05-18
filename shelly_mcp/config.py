import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Config loader: DeskAgent paths.load_config() via Environment Variable
_scripts_dir = os.environ.get("DESKAGENT_SCRIPTS_DIR")
if _scripts_dir:
    sys.path.insert(0, _scripts_dir)
    from paths import load_config  # type: ignore[import-not-found]
else:
    # Standalone fallback: local config.json
    def load_config() -> dict:
        local_config = Path(__file__).parent.parent / "config.json"
        if local_config.exists():
            return json.loads(local_config.read_text(encoding="utf-8"))
        raise ValueError("config.json not found. Copy config.example.json to config.json")


def get_config() -> Dict[str, Any]:
    """Loads Shelly configuration from apis.json."""
    config = load_config()
    shelly = config.get("shelly", {})

    if not shelly.get("enabled", True):
        raise ValueError("Shelly integration is disabled.")

    cloud = shelly.get("cloud", {})
    devices = shelly.get("devices", [])

    # Either cloud or local devices must be configured
    has_cloud = cloud.get("enabled", False) or cloud.get("auth_key")
    has_local = len(devices) > 0

    if not has_cloud and not has_local:
        raise ValueError("Shelly not configured. Either Cloud Auth Key or local devices required.")

    cloud_enabled = cloud.get("enabled") is not False and bool(cloud.get("auth_key"))

    return {
        "devices": devices,
        "cloud": cloud if cloud_enabled else {},
        "prefer_local": shelly.get("prefer_local", False),
        "timeout": shelly.get("timeout", 10),
        "price_per_kwh": shelly.get("price_per_kwh", 0.30),
    }


def is_configured() -> bool:
    """Checks if Shelly API is configured and enabled."""
    try:
        config = load_config()
        shelly = config.get("shelly", {})
        if shelly.get("enabled") is False:
            return False
        cloud = shelly.get("cloud", {})
        devices = shelly.get("devices", [])
        return bool(cloud.get("auth_key")) or len(devices) > 0
    except Exception:
        return False


def use_cloud() -> bool:
    """Checks if Cloud API is available and preferred."""
    try:
        config = get_config()
        cloud = config.get("cloud", {})
        has_cloud = bool(cloud.get("auth_key"))
        has_local = len(config.get("devices", [])) > 0
        if config.get("prefer_local", False) and has_local:
            return False
        return has_cloud
    except Exception:
        return False
