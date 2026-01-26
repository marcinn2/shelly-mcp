# Shelly Plugin for DeskAgent

[![DeskAgent](https://img.shields.io/badge/DeskAgent-Plugin-blue)](https://deskagent.de)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **This is a plugin for [DeskAgent](https://deskagent.de)** - the AI-powered desktop assistant.
> It provides Shelly smart home device integration for energy monitoring and automation.

## Features

- Real-time power consumption monitoring
- Historical energy data (Cloud API)
- 3-phase measurements (voltage, current, power factor)
- Device control (on/off/toggle)
- Local and Cloud API support

## Supported Devices

| Device | Type | Description |
|--------|------|-------------|
| Shelly Pro 3EM | `pro3em` | 3-phase energy measurement, 60 days history |
| Shelly 3EM | `3em` | 3-phase energy measurement (Gen1) |
| Shelly EM | `em` | 2-channel energy measurement with CT clamps |
| Shelly Plus PM | `pm` | Single consumer measurement |
| Shelly Plus 1PM | `1pm` | Switch with power measurement |

## Installation

Clone directly into your DeskAgent plugins folder:

```bash
cd /path/to/deskagent/plugins
git clone https://github.com/game4automation/shelly
```

Restart DeskAgent - the plugin is automatically discovered.

## Configuration

Add to your `config/apis.json`:

```json
{
  "shelly": {
    "enabled": true,
    "devices": [
      {"name": "Main", "ip": "192.168.1.100", "type": "pro3em"}
    ],
    "cloud": {
      "enabled": true,
      "server": "shelly-70-eu.shelly.cloud",
      "auth_key": "YOUR_AUTH_KEY"
    },
    "prefer_local": true,
    "price_per_kwh": 0.30
  }
}
```

### Shelly Cloud API (optional)

For historical data, enable Shelly Cloud API:

1. **Create Auth Key**: Shelly App → User Settings → Authorization cloud key
2. **Find Server**: Server is shown in Auth Key or App settings
3. **Add to config**

## Available Tools

| Tool | Description |
|------|-------------|
| `shelly_list_devices` | List all devices with metadata |
| `shelly_get_status` | Detailed device status |
| `shelly_get_power` | Current power of all devices |
| `shelly_get_energy_live` | Real-time measurements (3-phase) |
| `shelly_get_energy_history` | Historical energy data |
| `shelly_get_daily_consumption` | Daily consumption (7-30 days) |
| `shelly_get_hourly_profile` | 24h profile with analysis |
| `shelly_get_consumption_summary` | Consumption overview with costs |
| `shelly_switch_control` | Control switches (on/off/toggle) |

## Energy Report Agent

The included agent `agents/energy_report.md` creates a complete energy report with:

- Charts (daily consumption, PV balance, consumer distribution)
- 7-day analysis with historical data
- Anomaly detection (high consumption, fluctuations)
- Optimization suggestions (load shifting, PV usage)

## About DeskAgent

[DeskAgent](https://deskagent.de) is an AI-powered desktop assistant that automates your daily workflows - emails, invoices, document management and more.

## Links

- [Shelly Gen2+ API Documentation](https://shelly-api-docs.shelly.cloud/gen2/)
- [Shelly Cloud API](https://shelly-api-docs.shelly.cloud/cloud-control-api/)

## License

MIT License - see [LICENSE](LICENSE)
