from typing import Dict, Optional


def format_power(watts: float) -> str:
    """Formats power value into a human-readable unit."""
    if watts is None:
        return "N/A"
    if abs(watts) >= 1000:
        return f"{watts / 1000:.2f} kW"
    return f"{watts:.1f} W"


def format_energy(wh: float) -> str:
    """Formats energy value into a human-readable unit."""
    if wh is None:
        return "N/A"
    if abs(wh) >= 1_000_000:
        return f"{wh / 1_000_000:.2f} MWh"
    if abs(wh) >= 1000:
        return f"{wh / 1000:.2f} kWh"
    return f"{wh:.1f} Wh"


def is_energy_meter(meta: Dict) -> bool:
    """Checks if a device is an energy meter.

    Detects various Shelly energy meters based on:
    - category: "emeter"
    - type: contains "EM", "3EM", "SHEM", "SPEM"
    """
    if meta.get("category", "").lower() == "emeter":
        return True
    device_type = meta.get("type", "").upper()
    return any(t in device_type for t in ["EM", "3EM", "SHEM", "SPEM", "PM"])


def is_device_online(status: Dict) -> bool:
    """Checks if a device is online based on various API response formats."""
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
    return bool(status.get("emeters") or status.get("meters") or status.get("em:0"))


def extract_power(status: Dict) -> float:
    """Extracts total active power from a device status dict (Gen1 or Gen2+)."""
    em0 = status.get("em:0", {})
    if em0 and isinstance(em0, dict):
        return em0.get("total_act_power", 0)
    emeters = status.get("emeters", [])
    if emeters:
        return sum(em.get("power", 0) for em in emeters)
    meters = status.get("meters", [])
    if meters:
        return sum(m.get("power", 0) for m in meters)
    return 0
