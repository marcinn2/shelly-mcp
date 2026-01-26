#!/usr/bin/env python3
"""
Shelly Smart Home MCP Server
=============================
MCP Server für Shelly Smart Home Geräte - Energiemessung und -monitoring.
Unterstützt sowohl Shelly Cloud API als auch lokalen Zugriff via IP.

API Dokumentation:
- Cloud: https://shelly-api-docs.shelly.cloud/cloud-control-api/
- Local: https://shelly-api-docs.shelly.cloud/gen2/
"""

import json
import os
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP

# Config loader: DeskAgent überschreibt Plugin-Config
def load_config() -> dict:
    """Lädt Config: DeskAgent apis.json überschreibt lokale config.json."""
    # 1. DeskAgent config/apis.json (höchste Priorität - überschreibt Plugin-Config)
    deskagent_config = Path(__file__).parent.parent.parent.parent / "config" / "apis.json"
    if deskagent_config.exists():
        return json.loads(deskagent_config.read_text(encoding="utf-8"))

    # 2. Lokale config.json im Plugin-Ordner (Fallback für Standalone)
    local_config = Path(__file__).parent.parent / "config.json"
    if local_config.exists():
        return json.loads(local_config.read_text(encoding="utf-8"))

    raise ValueError("config.json nicht gefunden. Kopiere config.example.json zu config.json")

mcp = FastMCP("shelly")

# Tool metadata for dynamic icon/color in WebUI
TOOL_METADATA = {
    "icon": "plug",
    "color": "#00b4d8"  # Shelly blue
}

# Cache for device list to avoid rate-limiting
_device_list_cache: Dict[str, Any] = {
    "data": {},
    "timestamp": None,
    "ttl_seconds": 60  # Cache for 60 seconds
}

# Integration schema for Settings UI
INTEGRATION_SCHEMA = {
    "name": "Shelly Smart Home",
    "icon": "plug",
    "color": "#00b4d8",
    "config_key": "shelly",
    "auth_type": "hybrid",
    "beta": True,
    "description": "Shelly Energiemessung und Smart Home Steuerung (Cloud + Lokal)",
    "fields": [
        {"key": "cloud.server", "label": "Cloud Server", "type": "text", "required": False,
         "hint": "z.B. shelly-1-eu.shelly.cloud"},
        {"key": "cloud.auth_key", "label": "Cloud Auth Key", "type": "password", "required": False,
         "hint": "Aus Shelly App: User Settings > Authorization cloud key"},
        {"key": "devices", "label": "Lokale Geräte", "type": "device_list", "required": False,
         "hint": "Optional: Geräte mit IP für lokalen Zugriff"},
    ],
    "test_tool": "shelly_list_devices",
    "docs_url": "https://shelly-api-docs.shelly.cloud/",
}

# Tools that return external/untrusted content (prompt injection risk)
HIGH_RISK_TOOLS = {
    "shelly_get_status",
    "shelly_get_energy_live",
}


def get_config() -> Dict[str, Any]:
    """Lädt Shelly-Konfiguration aus apis.json."""
    config = load_config()
    shelly = config.get("shelly", {})

    if not shelly.get("enabled", True):
        raise ValueError("Shelly Integration ist deaktiviert.")

    cloud = shelly.get("cloud", {})
    devices = shelly.get("devices", [])

    # Either cloud or local devices must be configured
    has_cloud = cloud.get("enabled", False) or cloud.get("auth_key")
    has_local = len(devices) > 0

    if not has_cloud and not has_local:
        raise ValueError(
            "Shelly nicht konfiguriert. Entweder Cloud Auth Key oder lokale Geräte benötigt."
        )

    return {
        "devices": devices,
        "cloud": cloud,
        "prefer_local": shelly.get("prefer_local", False),
        "timeout": shelly.get("timeout", 10),
        "price_per_kwh": shelly.get("price_per_kwh", 0.30)
    }


def is_configured() -> bool:
    """Prüft ob Shelly API konfiguriert und aktiviert ist."""
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
    """Prüft ob Cloud API verfügbar und bevorzugt ist."""
    try:
        config = get_config()
        cloud = config.get("cloud", {})
        prefer_local = config.get("prefer_local", False)

        has_cloud = bool(cloud.get("auth_key"))
        has_local = len(config.get("devices", [])) > 0

        if prefer_local and has_local:
            return False
        return has_cloud
    except Exception:
        return False


# =============================================================================
# Cloud API Functions
# =============================================================================

def cloud_request(endpoint: str, params: Dict = None, timeout: int = 10) -> Dict:
    """Führt Cloud API GET Request aus."""
    config = get_config()
    cloud = config["cloud"]

    server = cloud.get("server", "shelly-1-eu.shelly.cloud")
    auth_key = cloud.get("auth_key", "")

    if not auth_key:
        return {"error": "Kein Auth Key konfiguriert"}

    url = f"https://{server}/{endpoint}"

    if params is None:
        params = {}
    params["auth_key"] = auth_key

    query = urllib.parse.urlencode(params)
    url = f"{url}?{query}"

    headers = {"Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            if not result.get("isok", True):
                return {"error": f"API Fehler: {result.get('errors', {})}"}
            return result
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Verbindungsfehler: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def cloud_post(endpoint: str, data: Dict = None, timeout: int = 10) -> Dict:
    """Führt Cloud API POST Request aus."""
    config = get_config()
    cloud = config["cloud"]

    server = cloud.get("server", "shelly-1-eu.shelly.cloud")
    auth_key = cloud.get("auth_key", "")

    if not auth_key:
        return {"error": "Kein Auth Key konfiguriert"}

    url = f"https://{server}/{endpoint}"

    if data is None:
        data = {}
    data["auth_key"] = auth_key

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            if not result.get("isok", True):
                return {"error": f"API Fehler: {result.get('errors', {})}"}
            return result
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Verbindungsfehler: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def cloud_get_rooms() -> Dict[int, str]:
    """Holt Raum-Namen von der Cloud API.

    Returns:
        Dict mit room_id -> room_name mapping
    """
    result = cloud_request("interface/room/list")

    if "error" in result:
        return {}

    rooms = {}
    data = result.get("data", {}).get("rooms", {})

    for room_id, room_data in data.items():
        rooms[int(room_id)] = room_data.get("name", f"Raum {room_id}")

    return rooms


def cloud_get_device_list() -> Dict[str, Dict]:
    """Holt Geräte-Metadaten (Name, Raum, IP, etc.) von der Cloud API.

    Uses a 60-second cache to avoid rate-limiting issues.

    Returns:
        Dict mit device_id -> metadata mapping
    """
    global _device_list_cache

    # Check cache first
    if _device_list_cache["timestamp"]:
        age = (datetime.now() - _device_list_cache["timestamp"]).total_seconds()
        if age < _device_list_cache["ttl_seconds"] and _device_list_cache["data"]:
            return _device_list_cache["data"]

    # Fetch rooms first for name lookup
    rooms = cloud_get_rooms()

    result = cloud_request("interface/device/list")

    if "error" in result:
        # Return cached data if available, otherwise empty dict
        if _device_list_cache["data"]:
            return _device_list_cache["data"]
        return {}

    devices = {}
    data = result.get("data", {})

    # Parse device list - can be dict or list
    device_list = data.get("devices", {})
    if isinstance(device_list, dict):
        device_list = list(device_list.values())

    for dev in device_list:
        dev_id = dev.get("id", "")
        if dev_id:
            room_id = dev.get("room_id")
            room_name = rooms.get(room_id, "") if room_id else ""

            devices[dev_id] = {
                "name": dev.get("name", ""),
                "room": room_name,
                "room_id": room_id,
                "type": dev.get("type", ""),
                "category": dev.get("category", ""),  # emeter, relay, etc.
                "gen": dev.get("gen", 0),  # Generation 1 or 2
                "ip": dev.get("ip", ""),
                "ssid": dev.get("ssid", ""),
                "online": dev.get("cloud_online", False),
                "pv_usage": dev.get("pv_usage", ""),  # solar, grid
                "channel": dev.get("channel", 0),
                "channels_count": dev.get("channels_count", 1),
            }

    # Update cache
    if devices:
        _device_list_cache["data"] = devices
        _device_list_cache["timestamp"] = datetime.now()

    return devices


# =============================================================================
# Local API Functions
# =============================================================================

def local_request(ip: str, method: str, params: Dict = None, timeout: int = 5) -> Dict:
    """Führt lokalen RPC-Request gegen Shelly-Gerät aus."""
    url = f"http://{ip}/rpc/{method}"

    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"

    headers = {"Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Verbindungsfehler: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def get_local_device(name: str) -> Optional[Dict]:
    """Findet ein lokales Gerät anhand des Namens."""
    config = get_config()
    for device in config.get("devices", []):
        if device.get("name", "").lower() == name.lower():
            return device
    return None


# =============================================================================
# Helper Functions
# =============================================================================

def format_power(watts: float) -> str:
    """Formatiert Leistung in lesbare Einheit."""
    if watts is None:
        return "N/A"
    if abs(watts) >= 1000:
        return f"{watts/1000:.2f} kW"
    return f"{watts:.1f} W"


def format_energy(wh: float) -> str:
    """Formatiert Energie in lesbare Einheit."""
    if wh is None:
        return "N/A"
    if abs(wh) >= 1000000:
        return f"{wh/1000000:.2f} MWh"
    if abs(wh) >= 1000:
        return f"{wh/1000:.2f} kWh"
    return f"{wh:.1f} Wh"


def is_energy_meter(meta: Dict) -> bool:
    """Prüft ob ein Gerät ein Energiemessgerät ist.

    Erkennt verschiedene Shelly Energiemessgeräte anhand von:
    - category: "emeter"
    - type: enthält "EM", "3EM", "SHEM", "SPEM"
    """
    category = meta.get("category", "").lower()
    device_type = meta.get("type", "").upper()

    # Bekannte Kategorie
    if category == "emeter":
        return True

    # Gerätetypen die auf Energiemessung hinweisen
    em_types = ["EM", "3EM", "SHEM", "SPEM", "PM"]
    for em_type in em_types:
        if em_type in device_type:
            return True

    return False


def is_device_online(status: Dict) -> bool:
    """Prüft ob ein Gerät online ist basierend auf verschiedenen API-Formaten."""
    # Gen2+ format: cloud.connected
    cloud = status.get("cloud", {})
    if isinstance(cloud, dict) and cloud.get("connected"):
        return True
    # Gen1 format or alternative
    if status.get("_online"):
        return True
    # Check wifi connection
    wifi = status.get("wifi", status.get("wifi_sta", {}))
    if isinstance(wifi, dict) and wifi.get("connected"):
        return True
    # If we have any power data, device is online
    if status.get("emeters") or status.get("meters") or status.get("em:0"):
        return True
    return False


# =============================================================================
# Device Management
# =============================================================================

@mcp.tool()
def shelly_list_devices() -> str:
    """Listet alle Shelly-Geräte (Cloud + Lokal) mit Metadaten.

    Returns:
        Liste der Geräte mit Name, Raum, Typ, IP, Firmware und Online-Status
    """
    lines = ["**Shelly-Geräte:**\n"]
    config = get_config()

    # Cloud devices
    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        # Fetch device metadata (name, room, IP, firmware)
        device_metadata = cloud_get_device_list()

        # Fetch device status (power, online)
        result = cloud_post("device/all_status")

        if "error" not in result:
            devices = result.get("data", {}).get("devices_status", {})

            if devices:
                lines.append("### Cloud-Geräte\n")

                for device_id, status in devices.items():
                    # Merge metadata from device list
                    meta = device_metadata.get(device_id, {})

                    dev_info = status.get("_dev_info", {})
                    name = meta.get("name") or dev_info.get("name", device_id)
                    room = meta.get("room", "")
                    dev_type = meta.get("type") or status.get("code", dev_info.get("type", "unknown"))
                    category = meta.get("category", "")  # emeter, relay
                    gen = meta.get("gen", 0)
                    ip_addr = meta.get("ip", "")
                    pv_usage = meta.get("pv_usage", "")  # solar, grid
                    online = is_device_online(status)

                    status_icon = "🟢" if online else "🔴"
                    lines.append(f"- **{name}** {status_icon}")
                    lines.append(f"  ID: `{device_id}`")

                    # Type with category and generation
                    type_info = dev_type
                    if category:
                        type_info += f" ({category})"
                    if gen:
                        type_info += f" Gen{gen}"
                    lines.append(f"  Typ: {type_info}")

                    if room:
                        lines.append(f"  Raum: {room}")
                    if ip_addr:
                        lines.append(f"  IP: {ip_addr}")
                    if pv_usage:
                        usage_label = "☀️ Solar" if pv_usage == "solar" else "⚡ Netz"
                        lines.append(f"  Nutzung: {usage_label}")

                    if online:
                        power = 0
                        # Gen2+ format: em:0 with total_act_power
                        em0 = status.get("em:0", {})
                        if em0 and isinstance(em0, dict):
                            power = em0.get("total_act_power", 0)
                        else:
                            # Gen1 format: emeters or meters array
                            emeters = status.get("emeters", [])
                            meters = status.get("meters", [])
                            if emeters:
                                power = sum(em.get("power", 0) for em in emeters)
                            elif meters:
                                power = sum(m.get("power", 0) for m in meters)
                        if power:
                            lines.append(f"  Leistung: {format_power(power)}")

                    lines.append("")
        else:
            lines.append(f"Cloud-Fehler: {result['error']}\n")

    # Local devices
    local_devices = config.get("devices", [])
    if local_devices:
        lines.append("### Lokale Geräte\n")

        for device in local_devices:
            name = device.get("name", "Unbenannt")
            ip = device.get("ip", "")
            dev_type = device.get("type", "unknown")

            status = local_request(ip, "Shelly.GetStatus", timeout=2)
            online = "error" not in status
            status_icon = "🟢" if online else "🔴"

            lines.append(f"- **{name}** {status_icon}")
            lines.append(f"  IP: `{ip}`")
            lines.append(f"  Typ: {dev_type}")

            if online:
                # Check for power
                for key in ["em:0", "pm1:0", "switch:0"]:
                    if key in status:
                        power = status[key].get("apower", status[key].get("power", 0))
                        if power:
                            lines.append(f"  Leistung: {format_power(power)}")
                        break

            lines.append("")

    if len(lines) == 1:
        return "Keine Geräte konfiguriert."

    return "\n".join(lines)


@mcp.tool()
def shelly_get_status(device: Optional[str] = None) -> str:
    """Holt den Status eines oder aller Shelly-Geräte.

    Args:
        device: Geräte-Name oder ID (optional, sonst alle)

    Returns:
        Geräte-Status (Online, Leistung, Energie, etc.)
    """
    config = get_config()
    lines = ["**Shelly Status:**\n"]

    if device:
        # Check if it's a local device name
        local_dev = get_local_device(device)
        if local_dev:
            ip = local_dev.get("ip", "")
            status = local_request(ip, "Shelly.GetStatus")

            if "error" in status:
                return f"Fehler: {status['error']}"

            lines.append(f"### {device} 🟢\n")

            # System info
            sys_info = status.get("sys", {})
            if sys_info:
                uptime = sys_info.get("uptime", 0)
                lines.append(f"- Uptime: {str(timedelta(seconds=uptime))}")
                temp = sys_info.get("temperature", {}).get("tC")
                if temp:
                    lines.append(f"- Temperatur: {temp}°C")

            # Power
            for key in ["em:0", "pm1:0", "switch:0"]:
                if key in status:
                    power = status[key].get("apower", status[key].get("power", 0))
                    energy = status[key].get("aenergy", {}).get("total", 0)
                    lines.append(f"- Leistung: {format_power(power)}")
                    lines.append(f"- Energie: {format_energy(energy)}")
                    break

            return "\n".join(lines)

        # Try cloud by ID
        if cloud.get("auth_key") if (cloud := config.get("cloud", {})) else False:
            result = cloud_post("device/status", {"id": device})

            if "error" not in result:
                data = result.get("data", {}).get("device_status", {})
                if data:
                    online = is_device_online(data)
                    lines.append(f"### {device} {'🟢' if online else '🔴'}\n")

                    if online:
                        emeters = data.get("emeters", [])
                        for i, em in enumerate(emeters):
                            lines.append(f"**Phase {i+1}:**")
                            lines.append(f"  - Spannung: {em.get('voltage', 0):.1f} V")
                            lines.append(f"  - Strom: {em.get('current', 0):.2f} A")
                            lines.append(f"  - Leistung: {format_power(em.get('power', 0))}")

                    return "\n".join(lines)

        return f"Gerät '{device}' nicht gefunden."

    # Get all devices status
    return shelly_list_devices()


# =============================================================================
# Energy Monitoring
# =============================================================================

@mcp.tool()
def shelly_get_power() -> str:
    """Holt die aktuelle Leistung (W) aller Geräte.

    Returns:
        Aktuelle Leistung pro Gerät und Gesamtleistung
    """
    config = get_config()
    lines = ["**Aktuelle Leistung:**\n"]
    total_power = 0.0

    # Cloud devices
    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        # Fetch device metadata first (names, rooms, etc.)
        device_metadata = cloud_get_device_list()

        result = cloud_post("device/all_status")

        if "error" not in result:
            devices = result.get("data", {}).get("devices_status", {})

            for dev_id, status in devices.items():
                # Get name from metadata (more complete) or fallback to status
                meta = device_metadata.get(dev_id, {})
                dev_info = status.get("_dev_info", {})
                name = meta.get("name") or dev_info.get("name") or dev_id
                room = meta.get("room", "")
                if room:
                    name = f"{name} ({room})"
                online = is_device_online(status)

                if not online:
                    lines.append(f"- **{name}**: 🔴 Offline")
                    continue

                power = 0
                # Gen2+ format: em:0 with total_act_power
                em0 = status.get("em:0", {})
                if em0 and isinstance(em0, dict):
                    power = em0.get("total_act_power", 0)
                else:
                    # Gen1 format: emeters or meters array
                    emeters = status.get("emeters", [])
                    meters = status.get("meters", [])
                    if emeters:
                        power = sum(em.get("power", 0) for em in emeters)
                    elif meters:
                        power = sum(m.get("power", 0) for m in meters)

                total_power += power
                lines.append(f"- **{name}**: {format_power(power)}")

    # Local devices (if not using cloud or in addition)
    local_devices = config.get("devices", [])
    prefer_local = config.get("prefer_local", False)

    if prefer_local and local_devices:
        for device in local_devices:
            name = device.get("name", "Unbenannt")
            ip = device.get("ip", "")
            dev_type = device.get("type", "").lower()

            if dev_type in ["pro3em", "3em"]:
                status = local_request(ip, "EM.GetStatus", {"id": 0})
            else:
                status = local_request(ip, "Shelly.GetStatus")

            if "error" in status:
                lines.append(f"- **{name}**: ⚠️ Offline")
                continue

            power = 0
            if "total_act_power" in status:
                power = status["total_act_power"]
            elif "apower" in status:
                power = status["apower"]
            else:
                for key in ["em:0", "pm1:0", "switch:0"]:
                    if key in status:
                        power = status[key].get("apower", status[key].get("power", 0))
                        break

            total_power += power
            lines.append(f"- **{name}**: {format_power(power)}")

    lines.append("")
    lines.append(f"**Gesamt: {format_power(total_power)}**")

    return "\n".join(lines)


@mcp.tool()
def shelly_get_energy_live(device: str) -> str:
    """Holt Echtzeit-Energiedaten eines Geräts (Spannung, Strom, Leistung pro Phase).

    Args:
        device: Geräte-Name (lokal) oder ID (Cloud)

    Returns:
        Detaillierte Echtzeit-Messwerte
    """
    config = get_config()

    # Try local device first
    local_dev = get_local_device(device)
    if local_dev:
        ip = local_dev.get("ip", "")
        dev_type = local_dev.get("type", "").lower()

        lines = [f"**Echtzeit-Messwerte - {device}:**\n"]

        if dev_type in ["pro3em", "3em"]:
            status = local_request(ip, "EM.GetStatus", {"id": 0})

            if "error" in status:
                return f"Fehler: {status['error']}"

            phases = ["a", "b", "c"]
            phase_names = ["L1", "L2", "L3"]

            for phase, name in zip(phases, phase_names):
                voltage = status.get(f"{phase}_voltage", 0)
                current = status.get(f"{phase}_current", 0)
                power = status.get(f"{phase}_act_power", 0)
                pf = status.get(f"{phase}_pf", 0)

                lines.append(f"**{name}:**")
                lines.append(f"  - Spannung: {voltage:.1f} V")
                lines.append(f"  - Strom: {current:.2f} A")
                lines.append(f"  - Leistung: {format_power(power)}")
                lines.append(f"  - Leistungsfaktor: {pf:.2f}")
                lines.append("")

            total_power = status.get("total_act_power", 0)
            lines.append("**Gesamt:**")
            lines.append(f"  - Leistung: {format_power(total_power)}")

        else:
            status = local_request(ip, "Shelly.GetStatus")

            if "error" in status:
                return f"Fehler: {status['error']}"

            for key in ["em:0", "pm1:0", "switch:0"]:
                if key in status:
                    data = status[key]
                    lines.append(f"- Spannung: {data.get('voltage', 0):.1f} V")
                    lines.append(f"- Strom: {data.get('current', 0):.2f} A")
                    lines.append(f"- Leistung: {format_power(data.get('apower', 0))}")
                    lines.append(f"- Energie: {format_energy(data.get('aenergy', {}).get('total', 0))}")
                    break

        return "\n".join(lines)

    # Try cloud
    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        result = cloud_post("device/status", {"id": device})

        if "error" in result:
            return f"Fehler: {result['error']}"

        status = result.get("data", {}).get("device_status", {})
        if not status:
            return f"Keine Daten für Gerät {device}"

        dev_info = status.get("_dev_info", {})
        name = dev_info.get("name", device)

        if not is_device_online(status):
            return f"Gerät **{name}** ist offline."

        lines = [f"**Echtzeit-Messwerte - {name}:**\n"]

        # Gen2+ format: em:0 with per-phase data
        em0 = status.get("em:0", {})
        if em0 and isinstance(em0, dict):
            phases = [("a", "L1"), ("b", "L2"), ("c", "L3")]
            for phase_key, phase_name in phases:
                voltage = em0.get(f"{phase_key}_voltage", 0)
                current = em0.get(f"{phase_key}_current", 0)
                power = em0.get(f"{phase_key}_act_power", 0)
                pf = em0.get(f"{phase_key}_pf", 0)

                lines.append(f"**{phase_name}:**")
                lines.append(f"  - Spannung: {voltage:.1f} V")
                lines.append(f"  - Strom: {current:.2f} A")
                lines.append(f"  - Leistung: {format_power(power)}")
                lines.append(f"  - Leistungsfaktor: {pf:.2f}")
                lines.append("")

            total_power = em0.get("total_act_power", 0)
            lines.append("**Gesamt:**")
            lines.append(f"  - Leistung: {format_power(total_power)}")
        else:
            # Gen1 format: emeters or meters array
            emeters = status.get("emeters", [])
            if emeters:
                phase_names = ["L1", "L2", "L3"]
                for i, em in enumerate(emeters):
                    phase = phase_names[i] if i < len(phase_names) else f"Phase {i+1}"
                    lines.append(f"**{phase}:**")
                    lines.append(f"  - Spannung: {em.get('voltage', 0):.1f} V")
                    lines.append(f"  - Strom: {em.get('current', 0):.2f} A")
                    lines.append(f"  - Leistung: {format_power(em.get('power', 0))}")
                    lines.append(f"  - Energie: {format_energy(em.get('total', 0))}")
                    lines.append("")

                total_power = sum(em.get("power", 0) for em in emeters)
                lines.append("**Gesamt:**")
                lines.append(f"  - Leistung: {format_power(total_power)}")
            else:
                meters = status.get("meters", [])
                for m in meters:
                    lines.append(f"- Leistung: {format_power(m.get('power', 0))}")
                    lines.append(f"- Energie: {format_energy(m.get('total', 0))}")

        return "\n".join(lines)

    return f"Gerät '{device}' nicht gefunden."


@mcp.tool()
def shelly_get_consumption_summary() -> str:
    """Holt eine Verbrauchsübersicht aller Geräte.

    Returns:
        Verbrauchsübersicht mit Kosten
    """
    config = get_config()
    price_per_kwh = config.get("price_per_kwh", 0.30)

    lines = ["**Verbrauchsübersicht:**\n"]
    total_power = 0.0
    total_energy = 0.0

    # Cloud devices
    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        # Fetch device metadata first (names, rooms, etc.)
        device_metadata = cloud_get_device_list()

        result = cloud_post("device/all_status")

        if "error" not in result:
            devices = result.get("data", {}).get("devices_status", {})

            for dev_id, status in devices.items():
                # Get name from metadata (more complete) or fallback to status
                meta = device_metadata.get(dev_id, {})
                dev_info = status.get("_dev_info", {})
                name = meta.get("name") or dev_info.get("name") or dev_id
                room = meta.get("room", "")
                if room:
                    name = f"{name} ({room})"
                online = is_device_online(status)

                if not online:
                    lines.append(f"- **{name}**: 🔴 Offline")
                    continue

                power = 0
                energy = 0

                # Gen2+ format: em:0 with total_act_power
                em0 = status.get("em:0", {})
                if em0 and isinstance(em0, dict):
                    power = em0.get("total_act_power", 0)
                    # Gen2+ stores energy in emdata:0
                    emdata = status.get("emdata:0", {})
                    if emdata and isinstance(emdata, dict):
                        energy = emdata.get("total_act", 0)
                else:
                    # Gen1 format: emeters or meters array
                    emeters = status.get("emeters", [])
                    meters = status.get("meters", [])
                    if emeters:
                        power = sum(em.get("power", 0) for em in emeters)
                        energy = sum(em.get("total", 0) for em in emeters)
                    elif meters:
                        power = sum(m.get("power", 0) for m in meters)
                        energy = sum(m.get("total", 0) for m in meters)

                total_power += power
                total_energy += energy

                kwh = energy / 1000 if energy else 0
                lines.append(f"- **{name}**: {format_power(power)} | {kwh:.2f} kWh")

    # Local devices (if prefer_local)
    local_devices = config.get("devices", [])
    if config.get("prefer_local", False) and local_devices:
        for device in local_devices:
            name = device.get("name", "Unbenannt")
            ip = device.get("ip", "")

            status = local_request(ip, "Shelly.GetStatus")

            if "error" in status:
                lines.append(f"- **{name}**: ⚠️ Offline")
                continue

            power = 0
            energy = 0

            for key in ["em:0", "pm1:0", "switch:0"]:
                if key in status:
                    power = status[key].get("apower", status[key].get("power", 0))
                    energy = status[key].get("aenergy", {}).get("total", 0)
                    break

            total_power += power
            total_energy += energy

            kwh = energy / 1000 if energy else 0
            lines.append(f"- **{name}**: {format_power(power)} | {kwh:.2f} kWh")

    lines.append("")
    lines.append(f"**Aktuelle Gesamtleistung: {format_power(total_power)}**")

    total_kwh = total_energy / 1000 if total_energy else 0
    lines.append(f"**Gesamtenergie: {total_kwh:.2f} kWh**")

    if price_per_kwh > 0 and total_kwh > 0:
        cost = total_kwh * price_per_kwh
        lines.append(f"**Kosten: {cost:.2f} EUR** (bei {price_per_kwh:.2f} EUR/kWh)")

    return "\n".join(lines)


# =============================================================================
# Device Control
# =============================================================================

@mcp.tool()
def shelly_switch_control(device: str, action: str = "toggle", channel: int = 0) -> str:
    """Schaltet ein Shelly-Gerät ein oder aus.

    Args:
        device: Geräte-Name (lokal) oder ID (Cloud)
        action: "on", "off", oder "toggle"
        channel: Kanal (0 für die meisten Geräte)

    Returns:
        Bestätigung der Aktion
    """
    config = get_config()
    action = action.lower()

    if action not in ["on", "off", "toggle"]:
        return f"Ungültige Aktion '{action}'. Erlaubt: on, off, toggle"

    # Try local device first
    local_dev = get_local_device(device)
    if local_dev:
        ip = local_dev.get("ip", "")

        if action == "toggle":
            result = local_request(ip, "Switch.Toggle", {"id": channel})
        else:
            result = local_request(ip, "Switch.Set", {"id": channel, "on": action == "on"})

        if "error" in result:
            return f"Fehler: {result['error']}"

        new_state = "umgeschaltet" if action == "toggle" else ("eingeschaltet" if action == "on" else "ausgeschaltet")
        return f"**{device}** wurde {new_state}."

    # Try cloud
    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        result = cloud_post("device/relay/control", {
            "id": device,
            "channel": channel,
            "turn": action
        })

        if "error" in result:
            return f"Fehler: {result['error']}"

        return f"Gerät `{device}` wurde {action}."

    return f"Gerät '{device}' nicht gefunden."


# =============================================================================
# History / Statistics
# =============================================================================

@mcp.tool()
def shelly_get_energy_history(
    device: str,
    period: str = "day"
) -> str:
    """Holt historische Energiedaten eines Geräts.

    Args:
        device: Geräte-ID (z.B. c8f09e878b04)
        period: Zeitraum - "day" (Stunden), "week" (Tage), "month" (Tage), "year" (Monate)

    Returns:
        Historische Verbrauchs- und Einspeisedaten
    """
    config = get_config()
    cloud = config.get("cloud", {})

    if not cloud.get("auth_key"):
        return "Cloud API nicht konfiguriert. History benötigt Cloud-Zugang."

    valid_periods = ["day", "week", "month", "year"]
    if period not in valid_periods:
        return f"Ungültiger Zeitraum '{period}'. Erlaubt: {', '.join(valid_periods)}"

    # Try em-3p endpoint (3-phase meters)
    result = cloud_request("v2/statistics/power-consumption/em-3p", {
        "id": device,
        "channel": 0,
        "date_range": period
    })

    if "error" in result:
        return f"Fehler: {result['error']}"

    interval = result.get("interval", "hour")
    timezone = result.get("timezone", "UTC")
    sum_data = result.get("sum", [])

    if not sum_data:
        return f"Keine historischen Daten für Gerät {device}"

    # Get device name from metadata
    device_metadata = cloud_get_device_list()
    meta = device_metadata.get(device, {})
    name = meta.get("name", device)
    pv_usage = meta.get("pv_usage", "")

    period_labels = {
        "day": "Heute (stündlich)",
        "week": "Diese Woche (täglich)",
        "month": "Dieser Monat (täglich)",
        "year": "Dieses Jahr (monatlich)"
    }

    lines = [f"**Energieverlauf - {name}**"]
    lines.append(f"Zeitraum: {period_labels.get(period, period)}")
    lines.append(f"Intervall: {interval}")
    lines.append("")

    # Determine if this is a solar/grid device
    is_solar = pv_usage == "solar"

    total_consumption = 0.0
    total_reversed = 0.0

    for entry in sum_data:
        dt = entry.get("datetime", "")
        consumption = entry.get("consumption", 0)
        reversed_energy = entry.get("reversed", 0)

        total_consumption += consumption
        total_reversed += reversed_energy

        # Format datetime based on interval
        if interval == "hour":
            time_str = dt[11:16] if len(dt) > 11 else dt  # HH:MM
        elif interval == "day":
            time_str = dt[5:10] if len(dt) > 5 else dt  # MM-DD
        else:
            time_str = dt[:10] if len(dt) > 10 else dt  # YYYY-MM-DD

        if is_solar:
            # Solar device: show feed-in (reversed) prominently
            lines.append(f"- {time_str}: ☀️ {reversed_energy:.1f} kWh eingespeist | {consumption:.1f} kWh bezogen")
        else:
            lines.append(f"- {time_str}: {consumption:.1f} kWh verbraucht")

    lines.append("")
    lines.append("**Summe:**")
    if is_solar:
        lines.append(f"- Einspeisung: {total_reversed:.2f} kWh")
        lines.append(f"- Bezug: {total_consumption:.2f} kWh")
        lines.append(f"- Bilanz: {total_reversed - total_consumption:.2f} kWh (positiv = Überschuss)")
    else:
        lines.append(f"- Verbrauch: {total_consumption:.2f} kWh")

    price_per_kwh = config.get("price_per_kwh", 0.30)
    if price_per_kwh > 0:
        cost = total_consumption * price_per_kwh
        lines.append(f"- Kosten: {cost:.2f} EUR (bei {price_per_kwh:.2f} EUR/kWh)")

    return "\n".join(lines)


@mcp.tool()
def shelly_get_daily_consumption(days: int = 7) -> str:
    """Holt den täglichen Energieverbrauch aller Geräte.

    Args:
        days: Anzahl der Tage (max 30)

    Returns:
        Täglicher Verbrauch pro Gerät
    """
    config = get_config()
    cloud = config.get("cloud", {})

    if not cloud.get("auth_key"):
        return "Cloud API nicht konfiguriert. History benötigt Cloud-Zugang."

    days = min(days, 30)

    # Get device list first
    device_metadata = cloud_get_device_list()

    # Filter to emeter devices only (using robust detection)
    emeter_devices = {
        dev_id: meta for dev_id, meta in device_metadata.items()
        if is_energy_meter(meta)
    }

    if not emeter_devices:
        return "Keine Energiemessgeräte (emeter) gefunden."

    lines = [f"**Täglicher Energieverbrauch (letzte {days} Tage)**\n"]

    for dev_id, meta in emeter_devices.items():
        name = meta.get("name", dev_id)
        pv_usage = meta.get("pv_usage", "")

        result = cloud_request("v2/statistics/power-consumption/em-3p", {
            "id": dev_id,
            "channel": 0,
            "date_range": "week" if days <= 7 else "month"
        })

        if "error" in result:
            lines.append(f"### {name}")
            lines.append(f"⚠️ Fehler: {result['error']}")
            lines.append("")
            continue

        sum_data = result.get("sum", [])
        if not sum_data:
            continue

        # Limit to requested days
        sum_data = sum_data[-days:]

        lines.append(f"### {name}")

        total_consumption = 0.0
        total_reversed = 0.0

        for entry in sum_data:
            dt = entry.get("datetime", "")[:10]  # YYYY-MM-DD
            consumption = entry.get("consumption", 0)
            reversed_energy = entry.get("reversed", 0)

            total_consumption += consumption
            total_reversed += reversed_energy

            if pv_usage == "solar":
                lines.append(f"  {dt}: ☀️ {reversed_energy:.1f} kWh | ⚡ {consumption:.1f} kWh")
            else:
                lines.append(f"  {dt}: {consumption:.1f} kWh")

        lines.append(f"  **Summe: {total_consumption:.1f} kWh**")
        if pv_usage == "solar":
            lines.append(f"  **Einspeisung: {total_reversed:.1f} kWh**")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def shelly_get_hourly_profile(device: str) -> str:
    """Holt das stündliche Tagesprofil eines Geräts (Smart Home Analyse).

    Zeigt Verbrauch und Einspeisung pro Stunde für die letzten 24h.
    Ideal zur Analyse von Lastspitzen, Grundlast und PV-Nutzung.

    Args:
        device: Geräte-ID (z.B. c8f09e878b04)

    Returns:
        Stündliche Verbrauchs- und Einspeisedaten mit Analyse
    """
    config = get_config()
    cloud = config.get("cloud", {})

    if not cloud.get("auth_key"):
        return "Cloud API nicht konfiguriert."

    result = cloud_request("v2/statistics/power-consumption/em-3p", {
        "id": device,
        "channel": 0,
        "date_range": "day"
    })

    if "error" in result:
        return f"Fehler: {result['error']}"

    sum_data = result.get("sum", [])
    if not sum_data:
        return f"Keine Daten für Gerät {device}"

    # Get device name
    device_metadata = cloud_get_device_list()
    meta = device_metadata.get(device, {})
    name = meta.get("name", device)
    pv_usage = meta.get("pv_usage", "")
    is_solar = pv_usage == "solar"

    lines = [f"**Stündliches Tagesprofil - {name}**"]
    lines.append("Letzte 24 Stunden\n")

    # Collect data for analysis
    hourly_data = []
    max_consumption = {"value": 0, "hour": ""}
    max_feedin = {"value": 0, "hour": ""}
    night_consumption = 0  # 00:00-06:00
    day_consumption = 0    # 06:00-22:00
    night_hours = 0
    day_hours = 0

    for entry in sum_data:
        if entry.get("missing"):
            continue

        dt = entry.get("datetime", "")
        hour = dt[11:13] if len(dt) > 13 else "??"
        hour_int = int(hour) if hour.isdigit() else -1

        consumption = entry.get("consumption", 0)
        reversed_energy = entry.get("reversed", 0)
        min_v = entry.get("min_voltage", 0)
        max_v = entry.get("max_voltage", 0)

        hourly_data.append({
            "hour": hour,
            "consumption": consumption,
            "reversed": reversed_energy
        })

        # Track max values
        if consumption > max_consumption["value"]:
            max_consumption = {"value": consumption, "hour": f"{hour}:00"}
        if reversed_energy > max_feedin["value"]:
            max_feedin = {"value": reversed_energy, "hour": f"{hour}:00"}

        # Night vs day consumption
        if 0 <= hour_int < 6:
            night_consumption += consumption
            night_hours += 1
        elif 6 <= hour_int < 22:
            day_consumption += consumption
            day_hours += 1

        # Format output line
        bar_consumption = "█" * min(int(consumption / 100), 10)
        bar_feedin = "▓" * min(int(reversed_energy / 100), 10)

        if is_solar or reversed_energy > 0:
            lines.append(f"{hour}:00  {consumption:6.0f} Wh {bar_consumption}")
            if reversed_energy > 0:
                lines.append(f"       ⚡{reversed_energy:5.0f} Wh {bar_feedin} (Einspeisung)")
        else:
            lines.append(f"{hour}:00  {consumption:6.0f} Wh {bar_consumption}")

    lines.append("")
    lines.append("**Analyse:**")

    # Average base load
    if night_hours > 0:
        avg_night = night_consumption / night_hours
        lines.append(f"- Grundlast (00-06h): Ø {avg_night:.0f} Wh/h")

    # Peak consumption
    lines.append(f"- Lastspitze: {max_consumption['value']:.0f} Wh um {max_consumption['hour']}")

    # Peak feed-in (for solar devices)
    if max_feedin["value"] > 0:
        lines.append(f"- Max. Einspeisung: {max_feedin['value']:.0f} Wh um {max_feedin['hour']}")

    # Day vs night ratio
    total = night_consumption + day_consumption
    if total > 0:
        night_pct = (night_consumption / total) * 100
        lines.append(f"- Nachtverbrauch: {night_pct:.0f}% des Tages")

    # Optimization hints
    lines.append("")
    lines.append("**Optimierungspotential:**")

    if night_hours > 0:
        avg_night = night_consumption / night_hours
        if avg_night > 300:
            lines.append(f"- ⚠️ Hohe Grundlast nachts ({avg_night:.0f} Wh/h) - Stand-by Geräte prüfen")

    if max_consumption["value"] > 1000:
        lines.append(f"- ⚠️ Hohe Lastspitze um {max_consumption['hour']} - Zeitliche Verschiebung möglich?")

    if max_feedin["value"] > 500 and max_consumption["value"] > 500:
        lines.append("- 💡 Lastverschiebung in PV-Zeiten könnte Eigenverbrauch erhöhen")

    return "\n".join(lines)


# =============================================================================
# Server entrypoint
# =============================================================================

if __name__ == "__main__":
    mcp.run()
