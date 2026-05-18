from datetime import timedelta
from typing import Optional

from .app import mcp
from .config import get_config
from .cloud import cloud_get_device_list, cloud_post, cloud_request
from .local import device_request, device_request_gen1, get_local_device, is_gen1
from .utils import format_power, format_energy, is_energy_meter, is_device_online, extract_power


# =============================================================================
# Device Management
# =============================================================================

@mcp.tool()
def shelly_list_devices() -> str:
    """Lists all Shelly devices (Cloud + Local) with metadata.

    Returns:
        List of devices with identifier, name, room, type, IP, and online status.
        Use the identifier value with other tools (shelly_get_status, shelly_switch_control, etc.)
    """
    lines = ["**Shelly Devices:**\n"]
    config = get_config()

    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        device_metadata = cloud_get_device_list()
        result = cloud_post("device/all_status")

        if "error" not in result:
            devices = result.get("data", {}).get("devices_status", {})
            if devices:
                lines.append("### Cloud Devices\n")
                for device_id, status in devices.items():
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

                    lines.append(f"- **{name}** {'🟢' if online else '🔴'}")
                    lines.append(f"  ID: `{device_id}`")

                    type_info = dev_type
                    if category:
                        type_info += f" ({category})"
                    if gen:
                        type_info += f" Gen{gen}"
                    lines.append(f"  Type: {type_info}")

                    if room:
                        lines.append(f"  Room: {room}")
                    if ip_addr:
                        lines.append(f"  IP: {ip_addr}")
                    if pv_usage:
                        lines.append(f"  Usage: {'☀️ Solar' if pv_usage == 'solar' else '⚡ Grid'}")

                    if online:
                        power = extract_power(status)
                        if power:
                            lines.append(f"  Power: {format_power(power)}")

                    lines.append("")
        else:
            lines.append(f"Cloud error: {result['error']}\n")

    local_devices = config.get("devices", [])
    if local_devices:
        lines.append("### Local Devices\n")
        for device in local_devices:
            name = device.get("name", "Unnamed")
            ip = device.get("ip", "")
            dev_type = device.get("type", "unknown")

            t = config.get("timeout", 5)
            if is_gen1(device):
                status = device_request_gen1(device, "status", timeout=t)
            else:
                status = device_request(device, "Shelly.GetStatus", timeout=t)
            online = "error" not in status

            if is_gen1(device):
                mac = status.get("mac", "")
            else:
                mac = status.get("sys", {}).get("mac", "")

            lines.append(f"- **{name}** {'🟢' if online else '🔴'}")
            lines.append(f"  Identifier: `{name}`")
            if mac:
                lines.append(f"  Device ID: `{mac}`")
            lines.append(f"  IP: `{ip}`")
            lines.append(f"  Type: {dev_type}")

            if online:
                if is_gen1(device):
                    power = sum(e.get("power", 0) for e in status.get("emeters", [])
                                or status.get("meters", []))
                    if power:
                        lines.append(f"  Power: {format_power(power)}")
                else:
                    for key in ["em:0", "pm1:0", "switch:0"]:
                        if key in status:
                            power = status[key].get("apower", status[key].get("power", 0))
                            if power:
                                lines.append(f"  Power: {format_power(power)}")
                            break
            else:
                lines.append(f"  Error: {status.get('error', 'unknown')}")

            lines.append("")

    if len(lines) == 1:
        return "No devices configured."

    return "\n".join(lines)


@mcp.tool()
def shelly_get_status_all_devices() -> str:
    """Gets detailed status for every configured Shelly device.

    Returns:
        Uptime, temperature, power and energy for all local and cloud devices
    """
    config = get_config()
    lines = ["**Shelly Status — All Devices:**\n"]

    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        device_metadata = cloud_get_device_list()
        result = cloud_post("device/all_status")
        if "error" not in result:
            devices = result.get("data", {}).get("devices_status", {})
            if devices:
                lines.append("### Cloud Devices\n")
                for device_id, status in devices.items():
                    meta = device_metadata.get(device_id, {})
                    dev_info = status.get("_dev_info", {})
                    name = meta.get("name") or dev_info.get("name", device_id)
                    online = is_device_online(status)
                    lines.append(f"#### {name} {'🟢' if online else '🔴'}")
                    lines.append(f"- ID: `{device_id}`")
                    if online:
                        em0 = status.get("em:0", {})
                        emeters = status.get("emeters", [])
                        if em0 and isinstance(em0, dict):
                            lines.append(f"- Power: {format_power(em0.get('total_act_power', 0))}")
                        elif emeters:
                            lines.append(f"- Power: {format_power(sum(e.get('power', 0) for e in emeters))}")
                    lines.append("")
        else:
            lines.append(f"Cloud error: {result['error']}\n")

    local_devices = config.get("devices", [])
    if local_devices:
        lines.append("### Local Devices\n")
        for device in local_devices:
            name = device.get("name", "Unnamed")
            dev_type = device.get("type", "unknown")
            t = config.get("timeout", 5)

            if is_gen1(device):
                status = device_request_gen1(device, "status", timeout=t)
            else:
                status = device_request(device, "Shelly.GetStatus", timeout=t)

            online = "error" not in status
            mac = status.get("mac") or status.get("sys", {}).get("mac", "") if online else ""

            lines.append(f"#### {name} {'🟢' if online else '🔴'}")
            lines.append(f"- Identifier: `{name}`")
            if mac:
                lines.append(f"- Device ID: `{mac}`")
            lines.append(f"- Type: {dev_type}")

            if not online:
                lines.append(f"- Error: {status.get('error', 'unknown')}")
            elif is_gen1(device):
                uptime = status.get("uptime")
                if uptime is not None:
                    lines.append(f"- Uptime: {str(timedelta(seconds=uptime))}")
                temp = status.get("temperature")
                if temp:
                    lines.append(f"- Temperature: {temp}°C")
                emeters = status.get("emeters", []) or status.get("meters", [])
                for i, em in enumerate(emeters):
                    label = f"Phase {i + 1}" if len(emeters) > 1 else "Power"
                    lines.append(f"- {label}: {format_power(em.get('power', 0))} | {format_energy(em.get('total', 0))}")
            else:
                sys_info = status.get("sys", {})
                if sys_info:
                    uptime = sys_info.get("uptime", 0)
                    lines.append(f"- Uptime: {str(timedelta(seconds=uptime))}")
                    temp = sys_info.get("temperature", {}).get("tC")
                    if temp:
                        lines.append(f"- Temperature: {temp}°C")
                for key in ["em:0", "pm1:0", "switch:0"]:
                    if key in status:
                        power = status[key].get("apower", status[key].get("power", 0))
                        energy = status[key].get("aenergy", {}).get("total", 0)
                        lines.append(f"- Power: {format_power(power)}")
                        lines.append(f"- Energy: {format_energy(energy)}")
                        break

            lines.append("")

    if len(lines) == 1:
        return "No devices configured."

    return "\n".join(lines)


@mcp.tool()
def shelly_get_status(device: str) -> str:
    """Gets comprehensive status for a single Shelly device.

    Includes: uptime, temperature, WiFi (SSID, RSSI, AP), cloud, MQTT,
    Bluetooth, input states, output states, and power/energy readings.

    Args:
        device: Device name (local config) or device ID (Cloud)

    Returns:
        Full device status grouped by category
    """
    config = get_config()

    local_dev = get_local_device(device)
    if local_dev:
        if is_gen1(local_dev):
            status = device_request_gen1(local_dev, "status")
        else:
            status = device_request(local_dev, "Shelly.GetStatus")

        if "error" in status:
            return f"Error: {status['error']}"

        lines = [f"## {device} 🟢\n"]

        # ── System ────────────────────────────────────────────────────────────
        lines.append("**System**")
        if is_gen1(local_dev):
            mac = status.get("mac", "")
            uptime = status.get("uptime")
            temp = status.get("temperature")
            fw = status.get("update", {}).get("old_version", "") or status.get("fw", "")
            has_update = status.get("update", {}).get("has_update", False)
        else:
            sys_info = status.get("sys", {})
            mac = sys_info.get("mac", "")
            uptime = sys_info.get("uptime")
            temp = sys_info.get("temperature", {}).get("tC")
            fw = sys_info.get("available_updates", {})
            has_update = bool(fw)

        if mac:
            lines.append(f"- Device ID: `{mac}`")
        if uptime is not None:
            lines.append(f"- Uptime: {str(timedelta(seconds=uptime))}")
        if temp:
            lines.append(f"- Temperature: {temp}°C")
        if has_update:
            lines.append("- ⚠️ Firmware update available")

        # ── WiFi ──────────────────────────────────────────────────────────────
        lines.append("\n**WiFi**")
        if is_gen1(local_dev):
            sta = status.get("wifi_sta", {})
            ap  = status.get("wifi_ap", {})
        else:
            sys_info = status.get("sys", {})
            sta = sys_info.get("wifi_sta", {}) or status.get("wifi", {})
            ap  = sys_info.get("wifi_ap", {})

        if sta:
            connected = sta.get("connected", sta.get("status") == "got ip")
            ssid  = sta.get("ssid", "")
            rssi  = sta.get("rssi")
            ip    = sta.get("ip") or sta.get("sta_ip", "")
            rssi_bar = ""
            if rssi is not None:
                strength = "▂▄▆█" if rssi > -55 else "▂▄▆_" if rssi > -70 else "▂▄__" if rssi > -80 else "▂___"
                rssi_bar = f" {strength}"
            lines.append(f"- Station: {'connected' if connected else 'disconnected'}")
            if ssid:
                lines.append(f"- SSID: {ssid}")
            if rssi is not None:
                lines.append(f"- Signal: {rssi} dBm{rssi_bar}")
            if ip:
                lines.append(f"- IP: {ip}")

        if ap:
            ap_enabled = ap.get("enabled", ap.get("is_open") is not None)
            lines.append(f"- AP: {'enabled' if ap_enabled else 'disabled'}"
                         + (f" ({ap.get('ssid', '')})" if ap_enabled and ap.get("ssid") else ""))

        # ── Connectivity ──────────────────────────────────────────────────────
        lines.append("\n**Connectivity**")
        cloud_s = status.get("cloud", {})
        mqtt_s  = status.get("mqtt", {})
        ble_s   = status.get("ble", {})

        cloud_ok = cloud_s.get("connected", False)
        cloud_en = cloud_s.get("enabled", cloud_ok)
        lines.append(f"- Cloud: {'🟢 connected' if cloud_ok else ('enabled, disconnected' if cloud_en else '⭕ disabled')}")

        mqtt_ok = mqtt_s.get("connected", False)
        mqtt_en = mqtt_s.get("enable", mqtt_ok)
        lines.append(f"- MQTT: {'🟢 connected' if mqtt_ok else ('enabled, disconnected' if mqtt_en else '⭕ disabled')}")

        if ble_s or "ble" in status:
            ble_en = ble_s.get("enable", False) if isinstance(ble_s, dict) else False
            lines.append(f"- Bluetooth: {'enabled' if ble_en else '⭕ disabled'}")

        # ── Inputs ────────────────────────────────────────────────────────────
        if is_gen1(local_dev):
            inputs = status.get("inputs", [])
            relays = status.get("relays", [])
            inputs_combined = [{"state": r.get("input", False)} for r in relays] if not inputs else inputs
        else:
            inputs_combined = [v for k, v in status.items() if k.startswith("input:")]

        if inputs_combined:
            lines.append("\n**Inputs**")
            for i, inp in enumerate(inputs_combined):
                state = inp.get("state", inp.get("input", False))
                lines.append(f"- Input {i}: {'ON' if state else 'off'}")

        # ── Outputs ───────────────────────────────────────────────────────────
        if is_gen1(local_dev):
            relays = status.get("relays", [])
            rollers = status.get("rollers", [])
            if relays:
                lines.append("\n**Outputs**")
                for i, r in enumerate(relays):
                    lines.append(f"- Relay {i}: {'🟢 ON' if r.get('ison') else '⭕ off'}")
            if rollers:
                lines.append("\n**Roller**")
                r = rollers[0]
                lines.append(f"- State: {r.get('state', 'unknown')}")
                if r.get("current_pos") is not None:
                    lines.append(f"- Position: {r['current_pos']}%")
        else:
            switches = [(k, v) for k, v in status.items() if k.startswith("switch:")]
            covers   = [(k, v) for k, v in status.items() if k.startswith("cover:")]
            if switches:
                lines.append("\n**Outputs**")
                for k, sw in switches:
                    lines.append(f"- {k}: {'🟢 ON' if sw.get('output') else '⭕ off'}")
            if covers:
                lines.append("\n**Cover**")
                for k, cv in covers:
                    lines.append(f"- State: {cv.get('state', 'unknown')}")
                    if cv.get("current_pos") is not None:
                        lines.append(f"- Position: {cv['current_pos']}%")

        # ── Power / Energy ────────────────────────────────────────────────────
        if is_gen1(local_dev):
            emeters = status.get("emeters", []) or status.get("meters", [])
            if emeters:
                lines.append("\n**Power**")
                for i, em in enumerate(emeters):
                    label = f"Phase {i + 1}" if len(emeters) > 1 else "Channel"
                    lines.append(f"- {label}: {format_power(em.get('power', 0))} | {format_energy(em.get('total', 0))}")
        else:
            energy_keys = [k for k in ["em:0", "pm1:0", "switch:0"] if k in status]
            if energy_keys:
                lines.append("\n**Power**")
                for k in energy_keys:
                    d = status[k]
                    lines.append(f"- Power: {format_power(d.get('apower', d.get('power', 0)))}")
                    lines.append(f"- Energy: {format_energy(d.get('aenergy', {}).get('total', 0))}")

        return "\n".join(lines)

    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        result = cloud_post("device/status", {"id": device})
        if "error" not in result:
            data = result.get("data", {}).get("device_status", {})
            if data:
                online = is_device_online(data)
                lines = [f"## {device} {'🟢' if online else '🔴'}\n"]
                if online:
                    em0 = data.get("em:0", {})
                    emeters = data.get("emeters", [])
                    cloud_s = data.get("cloud", {})
                    wifi = data.get("wifi", {}) or data.get("wifi_sta", {})

                    if wifi:
                        lines.append("**WiFi**")
                        lines.append(f"- SSID: {wifi.get('ssid', '')}")
                        if wifi.get("rssi"):
                            lines.append(f"- Signal: {wifi['rssi']} dBm")

                    lines.append("\n**Connectivity**")
                    lines.append(f"- Cloud: {'🟢 connected' if cloud_s.get('connected') else 'disconnected'}")

                    if em0 and isinstance(em0, dict):
                        lines.append("\n**Power**")
                        for phase, label in [("a", "L1"), ("b", "L2"), ("c", "L3")]:
                            p = em0.get(f"{phase}_act_power", 0)
                            if p:
                                lines.append(f"- {label}: {format_power(p)}")
                        lines.append(f"- Total: {format_power(em0.get('total_act_power', 0))}")
                    elif emeters:
                        lines.append("\n**Power**")
                        for i, em in enumerate(emeters):
                            lines.append(f"- Phase {i + 1}: {format_power(em.get('power', 0))}")
                return "\n".join(lines)

    return f"Device '{device}' not found."


# =============================================================================
# Energy Monitoring
# =============================================================================

@mcp.tool()
def shelly_get_power() -> str:
    """Gets the current power (W) of all devices.

    Returns:
        Current power per device and total power
    """
    config = get_config()
    lines = ["**Current Power:**\n"]
    total_power = 0.0

    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        device_metadata = cloud_get_device_list()
        result = cloud_post("device/all_status")

        if "error" not in result:
            devices = result.get("data", {}).get("devices_status", {})
            for dev_id, status in devices.items():
                meta = device_metadata.get(dev_id, {})
                dev_info = status.get("_dev_info", {})
                name = meta.get("name") or dev_info.get("name") or dev_id
                room = meta.get("room", "")
                if room:
                    name = f"{name} ({room})"

                if not is_device_online(status):
                    lines.append(f"- **{name}**: 🔴 Offline")
                    continue

                power = extract_power(status)
                total_power += power
                lines.append(f"- **{name}**: {format_power(power)}")

    local_devices = config.get("devices", [])
    if config.get("prefer_local", False) and local_devices:
        for device in local_devices:
            name = device.get("name", "Unnamed")
            dev_type = device.get("type", "").lower()

            if is_gen1(device):
                status = device_request_gen1(device, "status")
            elif dev_type == "pro3em":
                status = device_request(device, "EM.GetStatus", {"id": 0})
            else:
                status = device_request(device, "Shelly.GetStatus")

            if "error" in status:
                lines.append(f"- **{name}**: ⚠️ Offline")
                continue

            if is_gen1(device):
                power = sum(e.get("power", 0) for e in status.get("emeters", [])
                            or status.get("meters", []))
            else:
                power = (
                    status.get("total_act_power")
                    or status.get("apower")
                    or next(
                        (status[k].get("apower", status[k].get("power", 0))
                         for k in ["em:0", "pm1:0", "switch:0"] if k in status),
                        0,
                    )
                )
            total_power += power
            lines.append(f"- **{name}**: {format_power(power)}")

    lines.append("")
    lines.append(f"**Total: {format_power(total_power)}**")
    return "\n".join(lines)


@mcp.tool()
def shelly_get_energy_live(device: str) -> str:
    """Gets real-time energy data for a device (voltage, current, power per phase).

    Args:
        device: Device name (local) or ID (Cloud)

    Returns:
        Detailed real-time measurements
    """
    config = get_config()

    local_dev = get_local_device(device)
    if local_dev:
        dev_type = local_dev.get("type", "").lower()
        lines = [f"**Live Measurements - {device}:**\n"]

        if is_gen1(local_dev):
            status = device_request_gen1(local_dev, "status")
            if "error" in status:
                return f"Error: {status['error']}"

            emeters = status.get("emeters", []) or status.get("meters", [])
            phase_names = ["L1", "L2", "L3"]
            for i, em in enumerate(emeters):
                label = phase_names[i] if i < len(phase_names) else f"Phase {i + 1}"
                lines.append(f"**{label}:**")
                lines.append(f"  - Voltage: {em.get('voltage', 0):.1f} V")
                lines.append(f"  - Current: {em.get('current', 0):.2f} A")
                lines.append(f"  - Power: {format_power(em.get('power', 0))}")
                lines.append(f"  - Power Factor: {em.get('pf', 0):.2f}")
                lines.append(f"  - Energy: {format_energy(em.get('total', 0))}")
                lines.append("")
            if emeters:
                lines.append("**Total:**")
                lines.append(f"  - Power: {format_power(sum(e.get('power', 0) for e in emeters))}")
        elif dev_type == "pro3em":
            status = device_request(local_dev, "EM.GetStatus", {"id": 0})
            if "error" in status:
                return f"Error: {status['error']}"

            for phase, label in zip(["a", "b", "c"], ["L1", "L2", "L3"]):
                lines.append(f"**{label}:**")
                lines.append(f"  - Voltage: {status.get(f'{phase}_voltage', 0):.1f} V")
                lines.append(f"  - Current: {status.get(f'{phase}_current', 0):.2f} A")
                lines.append(f"  - Power: {format_power(status.get(f'{phase}_act_power', 0))}")
                lines.append(f"  - Power Factor: {status.get(f'{phase}_pf', 0):.2f}")
                lines.append("")

            lines.append("**Total:**")
            lines.append(f"  - Power: {format_power(status.get('total_act_power', 0))}")
        else:
            status = device_request(local_dev, "Shelly.GetStatus")
            if "error" in status:
                return f"Error: {status['error']}"

            for key in ["em:0", "pm1:0", "switch:0"]:
                if key in status:
                    data = status[key]
                    lines.append(f"- Voltage: {data.get('voltage', 0):.1f} V")
                    lines.append(f"- Current: {data.get('current', 0):.2f} A")
                    lines.append(f"- Power: {format_power(data.get('apower', 0))}")
                    lines.append(f"- Energy: {format_energy(data.get('aenergy', {}).get('total', 0))}")
                    break

        return "\n".join(lines)

    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        result = cloud_post("device/status", {"id": device})
        if "error" in result:
            return f"Error: {result['error']}"

        status = result.get("data", {}).get("device_status", {})
        if not status:
            return f"No data for device {device}"

        name = status.get("_dev_info", {}).get("name", device)
        if not is_device_online(status):
            return f"Device **{name}** is offline."

        lines = [f"**Live Measurements - {name}:**\n"]

        em0 = status.get("em:0", {})
        if em0 and isinstance(em0, dict):
            for phase_key, phase_name in [("a", "L1"), ("b", "L2"), ("c", "L3")]:
                lines.append(f"**{phase_name}:**")
                lines.append(f"  - Voltage: {em0.get(f'{phase_key}_voltage', 0):.1f} V")
                lines.append(f"  - Current: {em0.get(f'{phase_key}_current', 0):.2f} A")
                lines.append(f"  - Power: {format_power(em0.get(f'{phase_key}_act_power', 0))}")
                lines.append(f"  - Power Factor: {em0.get(f'{phase_key}_pf', 0):.2f}")
                lines.append("")
            lines.append("**Total:**")
            lines.append(f"  - Power: {format_power(em0.get('total_act_power', 0))}")
        else:
            emeters = status.get("emeters", [])
            if emeters:
                phase_names = ["L1", "L2", "L3"]
                for i, em in enumerate(emeters):
                    phase = phase_names[i] if i < len(phase_names) else f"Phase {i + 1}"
                    lines.append(f"**{phase}:**")
                    lines.append(f"  - Voltage: {em.get('voltage', 0):.1f} V")
                    lines.append(f"  - Current: {em.get('current', 0):.2f} A")
                    lines.append(f"  - Power: {format_power(em.get('power', 0))}")
                    lines.append(f"  - Energy: {format_energy(em.get('total', 0))}")
                    lines.append("")
                lines.append("**Total:**")
                lines.append(f"  - Power: {format_power(sum(em.get('power', 0) for em in emeters))}")
            else:
                for m in status.get("meters", []):
                    lines.append(f"- Power: {format_power(m.get('power', 0))}")
                    lines.append(f"- Energy: {format_energy(m.get('total', 0))}")

        return "\n".join(lines)

    return f"Device '{device}' not found."


@mcp.tool()
def shelly_get_consumption_summary() -> str:
    """Gets a consumption summary for all devices.

    Returns:
        Consumption overview with costs
    """
    config = get_config()
    price_per_kwh = config.get("price_per_kwh", 0.30)

    lines = ["**Consumption Summary:**\n"]
    total_power = 0.0
    total_energy = 0.0

    cloud = config.get("cloud", {})
    if cloud.get("auth_key"):
        device_metadata = cloud_get_device_list()
        result = cloud_post("device/all_status")

        if "error" not in result:
            devices = result.get("data", {}).get("devices_status", {})
            for dev_id, status in devices.items():
                meta = device_metadata.get(dev_id, {})
                dev_info = status.get("_dev_info", {})
                name = meta.get("name") or dev_info.get("name") or dev_id
                room = meta.get("room", "")
                if room:
                    name = f"{name} ({room})"

                if not is_device_online(status):
                    lines.append(f"- **{name}**: 🔴 Offline")
                    continue

                power = 0
                energy = 0
                em0 = status.get("em:0", {})
                if em0 and isinstance(em0, dict):
                    power = em0.get("total_act_power", 0)
                    emdata = status.get("emdata:0", {})
                    if emdata and isinstance(emdata, dict):
                        energy = emdata.get("total_act", 0)
                else:
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
                lines.append(f"- **{name}**: {format_power(power)} | {energy / 1000:.2f} kWh")

    local_devices = config.get("devices", [])
    if config.get("prefer_local", False) and local_devices:
        for device in local_devices:
            name = device.get("name", "Unnamed")
            if is_gen1(device):
                status = device_request_gen1(device, "status")
            else:
                status = device_request(device, "Shelly.GetStatus")

            if "error" in status:
                lines.append(f"- **{name}**: ⚠️ Offline")
                continue

            power = energy = 0
            if is_gen1(device):
                emeters = status.get("emeters", []) or status.get("meters", [])
                power = sum(e.get("power", 0) for e in emeters)
                energy = sum(e.get("total", 0) for e in emeters)
            else:
                for key in ["em:0", "pm1:0", "switch:0"]:
                    if key in status:
                        power = status[key].get("apower", status[key].get("power", 0))
                        energy = status[key].get("aenergy", {}).get("total", 0)
                        break

            total_power += power
            total_energy += energy
            lines.append(f"- **{name}**: {format_power(power)} | {energy / 1000:.2f} kWh")

    total_kwh = total_energy / 1000
    lines.append("")
    lines.append(f"**Total Power: {format_power(total_power)}**")
    lines.append(f"**Total Energy: {total_kwh:.2f} kWh**")

    if price_per_kwh > 0 and total_kwh > 0:
        lines.append(f"**Cost: {total_kwh * price_per_kwh:.2f} EUR** (at {price_per_kwh:.2f} EUR/kWh)")

    return "\n".join(lines)


# =============================================================================
# Device Control
# =============================================================================

def _cover_state_line(state: str, current_pos, target_pos, power) -> list:
    state_icons = {
        "open": "🔼", "closed": "🔽", "opening": "⬆️", "closing": "⬇️", "stopped": "⏹️",
    }
    lines = [f"State: {state_icons.get(state, '❓')} **{state}**"]
    if current_pos is not None:
        bar = "█" * (current_pos // 10) + "░" * (10 - current_pos // 10)
        lines.append(f"Position: [{bar}] {current_pos}%")
    if target_pos is not None and target_pos != current_pos:
        lines.append(f"Moving to: {target_pos}%")
    if power:
        lines.append(f"Motor power: {format_power(power)}")
    return lines


@mcp.tool()
def shelly_cover_control(device: str, action: str, position: Optional[int] = None) -> str:
    """Controls a roller/blind — Shelly 2.5 Gen1 (roller mode) or Shelly 2PM Gen2.

    Requires the device to be configured in roller mode via its web UI or app.
    Position-based control requires completed calibration.

    Args:
        device: Device name (local config)
        action: "open", "close", "stop", or "position"
        position: Target position 0–100 (0 = fully closed, 100 = fully open).
                  Required when action is "position", ignored otherwise.

    Returns:
        Current cover state and position after the command
    """
    local_dev = get_local_device(device)
    if not local_dev:
        return f"Device '{device}' not found in local config. Cover control requires a local device."

    action = action.lower()
    if action not in ("open", "close", "stop", "position"):
        return f"Invalid action '{action}'. Allowed: open, close, stop, position"

    if action == "position":
        if position is None:
            return "Action 'position' requires a position value (0–100)."
        if not (0 <= position <= 100):
            return f"Position {position} out of range. Must be 0–100."

    if is_gen1(local_dev):
        if action == "position":
            result = device_request_gen1(local_dev, "roller/0", {"go": "to_pos", "roller_pos": position})
        else:
            result = device_request_gen1(local_dev, "roller/0", {"go": action})
        if "error" in result:
            return f"Error: {result['error']}"
        full_status = device_request_gen1(local_dev, "status")
        if "error" in full_status:
            return f"Command sent. Could not read back status: {full_status['error']}"
        roller = (full_status.get("rollers") or [{}])[0]
        state = roller.get("state", "unknown")
        current_pos = roller.get("current_pos")
        power = roller.get("power", 0)
        lines = [f"**{device}** — cover {action} command sent."]
        lines += _cover_state_line(state, current_pos, None, power)
    else:
        if action == "position":
            result = device_request(local_dev, "Cover.GoToPosition", {"id": 0, "pos": position})
        elif action == "open":
            result = device_request(local_dev, "Cover.Open", {"id": 0})
        elif action == "close":
            result = device_request(local_dev, "Cover.Close", {"id": 0})
        else:
            result = device_request(local_dev, "Cover.Stop", {"id": 0})
        if "error" in result:
            return f"Error: {result['error']}"
        status = device_request(local_dev, "Cover.GetStatus", {"id": 0})
        if "error" in status:
            return f"Command sent. Could not read back status: {status['error']}"
        lines = [f"**{device}** — cover {action} command sent."]
        lines += _cover_state_line(
            status.get("state", "unknown"),
            status.get("current_pos"),
            status.get("target_pos"),
            status.get("apower", 0),
        )
    return "\n".join(lines)


@mcp.tool()
def shelly_cover_status(device: str) -> str:
    """Gets the current status of a roller/blind — Shelly 2.5 Gen1 or Shelly 2PM Gen2.

    Args:
        device: Device name (local config)

    Returns:
        Cover state, position, and motor power
    """
    local_dev = get_local_device(device)
    if not local_dev:
        return f"Device '{device}' not found in local config."

    if is_gen1(local_dev):
        full_status = device_request_gen1(local_dev, "status")
        if "error" in full_status:
            return f"Error: {full_status['error']}"
        roller = (full_status.get("rollers") or [{}])[0]
        state = roller.get("state", "unknown")
        current_pos = roller.get("current_pos")
        power = roller.get("power", 0)
        lines = [f"**{device}** — Cover Status\n"]
        lines += _cover_state_line(state, current_pos, None, power)
    else:
        status = device_request(local_dev, "Cover.GetStatus", {"id": 0})
        if "error" in status:
            return f"Error: {status['error']}"
        state = status.get("state", "unknown")
        current_pos = status.get("current_pos")
        target_pos = status.get("target_pos")
        power = status.get("apower", 0)
        voltage = status.get("voltage", 0)
        current = status.get("current", 0)
        energy_total = status.get("aenergy", {}).get("total", 0)
        lines = [f"**{device}** — Cover Status\n"]
        lines += _cover_state_line(state, current_pos, target_pos, power)
        if voltage:
            lines.append(f"Voltage: {voltage:.1f} V")
        if current:
            lines.append(f"Current: {current:.2f} A")
        if energy_total:
            lines.append(f"Energy (motor): {format_energy(energy_total)}")

    return "\n".join(lines)


@mcp.tool()
def shelly_switch_control(device: str, action: str = "toggle", channel: int = 0) -> str:
    """Switches a Shelly device on or off.

    Args:
        device: Device name (local) or ID (Cloud)
        action: "on", "off", or "toggle"
        channel: Channel (0 for most devices)

    Returns:
        Confirmation of the action
    """
    action = action.lower()
    if action not in ["on", "off", "toggle"]:
        return f"Invalid action '{action}'. Allowed: on, off, toggle"

    local_dev = get_local_device(device)
    if local_dev:
        if is_gen1(local_dev):
            result = device_request_gen1(local_dev, f"relay/{channel}", {"turn": action})
        elif action == "toggle":
            result = device_request(local_dev, "Switch.Toggle", {"id": channel})
        else:
            result = device_request(local_dev, "Switch.Set", {"id": channel, "on": action == "on"})

        if "error" in result:
            return f"Error: {result['error']}"

        state_label = {"on": "turned on", "off": "turned off", "toggle": "toggled"}[action]
        return f"**{device}** {state_label}."

    cloud = get_config().get("cloud", {})
    if cloud.get("auth_key"):
        result = cloud_post("device/relay/control", {"id": device, "channel": channel, "turn": action})
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Device `{device}` turned {action}."

    return f"Device '{device}' not found."


# =============================================================================
# History / Statistics
# =============================================================================

@mcp.tool()
def shelly_get_energy_history(device: str, period: str = "day") -> str:
    """Gets historical energy data for a device.

    Args:
        device: Device ID (e.g. c8f09e878b04)
        period: Time range - "day" (hours), "week" (days), "month" (days), "year" (months)

    Returns:
        Historical consumption and feed-in data
    """
    config = get_config()
    cloud = config.get("cloud", {})

    if not cloud.get("auth_key"):
        return "Cloud API not configured. History requires cloud access."

    valid_periods = ["day", "week", "month", "year"]
    if period not in valid_periods:
        return f"Invalid period '{period}'. Allowed: {', '.join(valid_periods)}"

    result = cloud_request("v2/statistics/power-consumption/em-3p", {
        "id": device, "channel": 0, "date_range": period,
    })

    if "error" in result:
        return f"Error: {result['error']}"

    sum_data = result.get("sum", [])
    if not sum_data:
        return f"No historical data for device {device}"

    meta = cloud_get_device_list().get(device, {})
    name = meta.get("name", device)
    is_solar = meta.get("pv_usage", "") == "solar"
    interval = result.get("interval", "hour")

    period_labels = {
        "day": "Today (hourly)", "week": "This week (daily)",
        "month": "This month (daily)", "year": "This year (monthly)",
    }

    lines = [f"**Energy History - {name}**",
             f"Period: {period_labels.get(period, period)}",
             f"Interval: {interval}", ""]

    total_consumption = total_reversed = 0.0

    for entry in sum_data:
        dt = entry.get("datetime", "")
        consumption = entry.get("consumption", 0)
        reversed_energy = entry.get("reversed", 0)
        total_consumption += consumption
        total_reversed += reversed_energy

        if interval == "hour":
            time_str = dt[11:16] if len(dt) > 11 else dt
        elif interval == "day":
            time_str = dt[5:10] if len(dt) > 5 else dt
        else:
            time_str = dt[:10] if len(dt) > 10 else dt

        if is_solar:
            lines.append(f"- {time_str}: ☀️ {reversed_energy:.1f} kWh fed in | {consumption:.1f} kWh drawn")
        else:
            lines.append(f"- {time_str}: {consumption:.1f} kWh consumed")

    lines.append("")
    lines.append("**Total:**")
    if is_solar:
        lines.append(f"- Feed-in: {total_reversed:.2f} kWh")
        lines.append(f"- Draw: {total_consumption:.2f} kWh")
        lines.append(f"- Balance: {total_reversed - total_consumption:.2f} kWh (positive = surplus)")
    else:
        lines.append(f"- Consumption: {total_consumption:.2f} kWh")

    price_per_kwh = config.get("price_per_kwh", 0.30)
    if price_per_kwh > 0:
        lines.append(f"- Cost: {total_consumption * price_per_kwh:.2f} EUR (at {price_per_kwh:.2f} EUR/kWh)")

    return "\n".join(lines)


@mcp.tool()
def shelly_get_daily_consumption(days: int = 7) -> str:
    """Gets daily energy consumption for all devices.

    Args:
        days: Number of days (max 30)

    Returns:
        Daily consumption per device
    """
    config = get_config()
    cloud = config.get("cloud", {})

    if not cloud.get("auth_key"):
        return "Cloud API not configured. History requires cloud access."

    days = min(days, 30)
    device_metadata = cloud_get_device_list()
    emeter_devices = {
        dev_id: meta for dev_id, meta in device_metadata.items()
        if is_energy_meter(meta)
    }

    if not emeter_devices:
        return "No energy meter devices (emeter) found."

    lines = [f"**Daily Energy Consumption (last {days} days)**\n"]

    for dev_id, meta in emeter_devices.items():
        name = meta.get("name", dev_id)
        is_solar = meta.get("pv_usage", "") == "solar"

        result = cloud_request("v2/statistics/power-consumption/em-3p", {
            "id": dev_id, "channel": 0,
            "date_range": "week" if days <= 7 else "month",
        })

        if "error" in result:
            lines.append(f"### {name}")
            lines.append(f"⚠️ Error: {result['error']}")
            lines.append("")
            continue

        sum_data = result.get("sum", [])[-days:]
        if not sum_data:
            continue

        lines.append(f"### {name}")
        total_consumption = total_reversed = 0.0

        for entry in sum_data:
            dt = entry.get("datetime", "")[:10]
            consumption = entry.get("consumption", 0)
            reversed_energy = entry.get("reversed", 0)
            total_consumption += consumption
            total_reversed += reversed_energy

            if is_solar:
                lines.append(f"  {dt}: ☀️ {reversed_energy:.1f} kWh | ⚡ {consumption:.1f} kWh")
            else:
                lines.append(f"  {dt}: {consumption:.1f} kWh")

        lines.append(f"  **Total: {total_consumption:.1f} kWh**")
        if is_solar:
            lines.append(f"  **Feed-in: {total_reversed:.1f} kWh**")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def shelly_get_hourly_profile(device: str) -> str:
    """Gets the hourly daily profile of a device (smart home analysis).

    Shows consumption and feed-in per hour for the last 24h.
    Ideal for analyzing load peaks, base load, and PV usage.

    Args:
        device: Device ID (e.g. c8f09e878b04)

    Returns:
        Hourly consumption and feed-in data with analysis
    """
    config = get_config()
    cloud = config.get("cloud", {})

    if not cloud.get("auth_key"):
        return "Cloud API not configured."

    result = cloud_request("v2/statistics/power-consumption/em-3p", {
        "id": device, "channel": 0, "date_range": "day",
    })

    if "error" in result:
        return f"Error: {result['error']}"

    sum_data = result.get("sum", [])
    if not sum_data:
        return f"No data for device {device}"

    meta = cloud_get_device_list().get(device, {})
    name = meta.get("name", device)

    lines = [f"**Hourly Profile - {name}**", "Last 24 hours\n"]

    max_consumption = {"value": 0, "hour": ""}
    max_feedin = {"value": 0, "hour": ""}
    night_consumption = day_consumption = 0.0
    night_hours = day_hours = 0

    for entry in sum_data:
        if entry.get("missing"):
            continue

        dt = entry.get("datetime", "")
        hour = dt[11:13] if len(dt) > 13 else "??"
        hour_int = int(hour) if hour.isdigit() else -1
        consumption = entry.get("consumption", 0)
        reversed_energy = entry.get("reversed", 0)

        if consumption > max_consumption["value"]:
            max_consumption = {"value": consumption, "hour": f"{hour}:00"}
        if reversed_energy > max_feedin["value"]:
            max_feedin = {"value": reversed_energy, "hour": f"{hour}:00"}

        if 0 <= hour_int < 6:
            night_consumption += consumption
            night_hours += 1
        elif 6 <= hour_int < 22:
            day_consumption += consumption
            day_hours += 1

        bar = "█" * min(int(consumption / 100), 10)
        lines.append(f"{hour}:00  {consumption:6.0f} Wh {bar}")
        if reversed_energy > 0:
            bar_fi = "▓" * min(int(reversed_energy / 100), 10)
            lines.append(f"       ⚡{reversed_energy:5.0f} Wh {bar_fi} (feed-in)")

    lines.append("")
    lines.append("**Analysis:**")

    if night_hours > 0:
        avg_night = night_consumption / night_hours
        lines.append(f"- Base load (00-06h): Ø {avg_night:.0f} Wh/h")

    lines.append(f"- Peak load: {max_consumption['value']:.0f} Wh at {max_consumption['hour']}")

    if max_feedin["value"] > 0:
        lines.append(f"- Max feed-in: {max_feedin['value']:.0f} Wh at {max_feedin['hour']}")

    total = night_consumption + day_consumption
    if total > 0:
        lines.append(f"- Night consumption: {night_consumption / total * 100:.0f}% of day total")

    lines.append("")
    lines.append("**Optimization potential:**")

    if night_hours > 0:
        avg_night = night_consumption / night_hours
        if avg_night > 300:
            lines.append(f"- ⚠️ High base load at night ({avg_night:.0f} Wh/h) - check standby devices")

    if max_consumption["value"] > 1000:
        lines.append(f"- ⚠️ High load peak at {max_consumption['hour']} - possible to shift to off-peak?")

    if max_feedin["value"] > 500 and max_consumption["value"] > 500:
        lines.append("- 💡 Shifting loads to PV hours could increase self-consumption")

    return "\n".join(lines)
