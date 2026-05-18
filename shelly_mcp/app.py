import os
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

def _transport_security() -> TransportSecuritySettings:
    raw = os.environ.get("SHELLY_MCP_ALLOWED_HOSTS", "").strip()
    if not raw:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    allowed = ["127.0.0.1:*", "localhost:*", "[::1]:*"] + [
        h.strip() for h in raw.split(",") if h.strip()
    ]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed,
    )

mcp = FastMCP("shelly", transport_security=_transport_security())

TOOL_METADATA: Dict[str, Any] = {
    "icon": "plug",
    "color": "#00b4d8",  # Shelly blue
}

INTEGRATION_SCHEMA: Dict[str, Any] = {
    "name": "Shelly Smart Home",
    "icon": "plug",
    "color": "#00b4d8",
    "config_key": "shelly",
    "auth_type": "hybrid",
    "beta": True,
    "description": "Shelly Energy Measurement and Smart Home Control (Cloud + Local)",
    "fields": [
        {"key": "cloud.server", "label": "Cloud Server", "type": "text", "required": False,
         "hint": "e.g. shelly-1-eu.shelly.cloud"},
        {"key": "cloud.auth_key", "label": "Cloud Auth Key", "type": "password", "required": False,
         "hint": "From Shelly App: User Settings > Authorization cloud key"},
        {"key": "devices", "label": "Local Devices", "type": "device_list", "required": False,
         "hint": "Optional: devices with IP for local access"},
    ],
    "test_tool": "shelly_list_devices",
    "docs_url": "https://shelly-api-docs.shelly.cloud/",
}

# Tools that return external/untrusted content (prompt injection risk)
HIGH_RISK_TOOLS = {
    "shelly_get_status",
    "shelly_get_energy_live",
}
