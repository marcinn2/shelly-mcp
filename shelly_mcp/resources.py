import json

from .app import mcp, INTEGRATION_SCHEMA
from .config import get_config, is_configured


@mcp.resource(
    "shelly://config",
    name="shelly_config",
    description="Current Shelly server configuration (auth keys redacted)",
    mime_type="application/json",
)
def resource_config() -> str:
    if not is_configured():
        return json.dumps({"error": "Shelly not configured"})

    config = get_config()
    cloud = config.get("cloud", {})

    return json.dumps({
        "configured": True,
        "prefer_local": config.get("prefer_local", False),
        "price_per_kwh": config.get("price_per_kwh", 0.30),
        "cloud": {
            "enabled": bool(cloud.get("auth_key")),
            "server": cloud.get("server", ""),
            "auth_key": "***" if cloud.get("auth_key") else None,
        },
        "local_devices": [
            {"name": d.get("name"), "ip": d.get("ip"), "type": d.get("type")}
            for d in config.get("devices", [])
        ],
    }, indent=2)


@mcp.resource(
    "shelly://devices",
    name="shelly_devices",
    description="Local devices defined in config (name, IP, type)",
    mime_type="application/json",
)
def resource_devices() -> str:
    if not is_configured():
        return json.dumps([])

    devices = get_config().get("devices", [])
    return json.dumps(
        [{"name": d.get("name"), "ip": d.get("ip"), "type": d.get("type")} for d in devices],
        indent=2,
    )


@mcp.resource(
    "shelly://integration",
    name="shelly_integration",
    description="Integration schema — field definitions for settings UIs",
    mime_type="application/json",
)
def resource_integration() -> str:
    return json.dumps(INTEGRATION_SCHEMA, indent=2)
