import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Dict

from .config import get_config

# Cache for device list to avoid rate-limiting
_device_list_cache: Dict = {
    "data": {},
    "timestamp": None,
    "ttl_seconds": 60,
}


def _cloud_api(endpoint: str, data: Dict = None, method: str = "GET", timeout: int = 10) -> Dict:
    """Executes a Cloud API request (GET or POST)."""
    config = get_config()
    cloud = config["cloud"]

    server = cloud.get("server", "shelly-1-eu.shelly.cloud")
    auth_key = cloud.get("auth_key", "")

    if not auth_key:
        return {"error": "No auth key configured"}

    url = f"https://{server}/{endpoint}"

    if method == "GET":
        params = data or {}
        params["auth_key"] = auth_key
        url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    else:
        post_data = data or {}
        post_data["auth_key"] = auth_key
        body = urllib.parse.urlencode(post_data).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            if not result.get("isok", True):
                return {"error": f"API error: {result.get('errors', {})}"}
            return result
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def cloud_request(endpoint: str, params: Dict = None, timeout: int = 10) -> Dict:
    """Executes a Cloud API GET request."""
    return _cloud_api(endpoint, params, method="GET", timeout=timeout)


def cloud_post(endpoint: str, data: Dict = None, timeout: int = 10) -> Dict:
    """Executes a Cloud API POST request."""
    return _cloud_api(endpoint, data, method="POST", timeout=timeout)


def cloud_get_rooms() -> Dict[int, str]:
    """Fetches room names from the Cloud API.

    Returns:
        Dict with room_id -> room_name mapping
    """
    result = cloud_request("interface/room/list")
    if "error" in result:
        return {}
    rooms = {}
    for room_id, room_data in result.get("data", {}).get("rooms", {}).items():
        rooms[int(room_id)] = room_data.get("name", f"Room {room_id}")
    return rooms


def cloud_get_device_list() -> Dict[str, Dict]:
    """Fetches device metadata (name, room, IP, etc.) from the Cloud API.

    Uses a 60-second cache to avoid rate-limiting issues.

    Returns:
        Dict with device_id -> metadata mapping
    """
    if _device_list_cache["timestamp"]:
        age = (datetime.now() - _device_list_cache["timestamp"]).total_seconds()
        if age < _device_list_cache["ttl_seconds"] and _device_list_cache["data"]:
            return _device_list_cache["data"]

    rooms = cloud_get_rooms()
    result = cloud_request("interface/device/list")

    if "error" in result:
        return _device_list_cache["data"] or {}

    data = result.get("data", {})
    device_list = data.get("devices", {})
    if isinstance(device_list, dict):
        device_list = list(device_list.values())

    devices = {}
    for dev in device_list:
        dev_id = dev.get("id", "")
        if not dev_id:
            continue
        room_id = dev.get("room_id")
        devices[dev_id] = {
            "name": dev.get("name", ""),
            "room": rooms.get(room_id, "") if room_id else "",
            "room_id": room_id,
            "type": dev.get("type", ""),
            "category": dev.get("category", ""),  # emeter, relay, etc.
            "gen": dev.get("gen", 0),              # Generation 1 or 2
            "ip": dev.get("ip", ""),
            "ssid": dev.get("ssid", ""),
            "online": dev.get("cloud_online", False),
            "pv_usage": dev.get("pv_usage", ""),   # solar, grid
            "channel": dev.get("channel", 0),
            "channels_count": dev.get("channels_count", 1),
        }

    if devices:
        _device_list_cache["data"] = devices
        _device_list_cache["timestamp"] = datetime.now()

    return devices
