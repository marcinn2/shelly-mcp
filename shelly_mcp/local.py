import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Optional

from .config import get_config


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


def get_local_device(name: str) -> Optional[Dict]:
    """Finds a local device by name."""
    config = get_config()
    for device in config.get("devices", []):
        if device.get("name", "").lower() == name.lower():
            return device
    return None
