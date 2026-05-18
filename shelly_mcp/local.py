import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Optional

from .config import get_config

# Device types that use the Gen1 REST API (http://{ip}/status etc.)
# All other types are assumed Gen2+ and use the RPC API (http://{ip}/rpc/Method)
GEN1_TYPES: set = {"3em", "em", "25", "2.5", "1", "1l", "plug", "plugs"}


def is_gen1(device: Dict) -> bool:
    return device.get("type", "").lower() in GEN1_TYPES


def local_request_gen1(
    ip: str,
    endpoint: str,
    params: Dict = None,
    timeout: int = 5,
    username: str = None,
    password: str = None,
) -> Dict:
    """GET request to a Gen1 Shelly device using its REST API."""
    url = f"http://{ip}/{endpoint}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")

    try:
        if username and password:
            pwd_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            pwd_mgr.add_password(None, url, username, password)
            opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(pwd_mgr))
            response_ctx = opener.open(req, timeout=timeout)
        else:
            response_ctx = urllib.request.urlopen(req, timeout=timeout)

        with response_ctx as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {"error": "HTTP 401: Unauthorized — set username/password in device config"}
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def device_request_gen1(device: Dict, endpoint: str, params: Dict = None, timeout: int = 5) -> Dict:
    """Gen1 REST request using credentials from the device config dict."""
    return local_request_gen1(
        device.get("ip", ""),
        endpoint,
        params,
        timeout,
        username=device.get("username"),
        password=device.get("password"),
    )


def local_request(
    ip: str,
    method: str,
    params: Dict = None,
    timeout: int = 5,
    username: str = None,
    password: str = None,
) -> Dict:
    """Executes a local RPC request against a Shelly device.

    Supports HTTP Basic Auth (Gen1) and HTTP Digest Auth (Gen2+) when
    username and password are provided. urllib negotiates the scheme
    automatically based on the WWW-Authenticate challenge from the device.
    """
    url = f"http://{ip}/rpc/{method}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")

    try:
        if username and password:
            pwd_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            pwd_mgr.add_password(None, url, username, password)
            opener = urllib.request.build_opener(
                urllib.request.HTTPBasicAuthHandler(pwd_mgr),
                urllib.request.HTTPDigestAuthHandler(pwd_mgr),
            )
            response_ctx = opener.open(req, timeout=timeout)
        else:
            response_ctx = urllib.request.urlopen(req, timeout=timeout)

        with response_ctx as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {"error": "HTTP 401: Unauthorized — set username/password in device config"}
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def device_request(device: Dict, method: str, params: Dict = None, timeout: int = 5) -> Dict:
    """Calls local_request using ip and credentials from a device config dict."""
    return local_request(
        device.get("ip", ""),
        method,
        params,
        timeout,
        username=device.get("username"),
        password=device.get("password"),
    )


def get_local_device(identifier: str) -> Optional[Dict]:
    """Finds a local device by name or Device ID (MAC address).

    Name match is tried first (fast). If nothing matches and the input looks
    like a MAC address (12 hex chars, optionally separated by : or -), each
    device is queried and its reported MAC is compared.
    """
    config = get_config()
    devices = config.get("devices", [])

    # Fast path: match by name (case-insensitive)
    for device in devices:
        if device.get("name", "").lower() == identifier.lower():
            return device

    # Slow path: match by Device ID / MAC
    clean = identifier.upper().replace(":", "").replace("-", "")
    if len(clean) == 12 and all(c in "0123456789ABCDEF" for c in clean):
        for device in devices:
            if is_gen1(device):
                status = local_request_gen1(
                    device.get("ip", ""), "status", timeout=3,
                    username=device.get("username"), password=device.get("password"),
                )
                mac = status.get("mac", "")
            else:
                status = local_request(
                    device.get("ip", ""), "Shelly.GetStatus", timeout=3,
                    username=device.get("username"), password=device.get("password"),
                )
                mac = status.get("sys", {}).get("mac", "")
            if mac.upper().replace(":", "").replace("-", "") == clean:
                return device

    return None
