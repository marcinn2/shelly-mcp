# Shelly MCP Server

[![DeskAgent](https://img.shields.io/badge/DeskAgent-Plugin-blue)](https://deskagent.de)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

MCP server for Shelly Smart Home devices — energy monitoring, real-time measurements, and device control. Works with any MCP-compatible client: [Claude Desktop](https://claude.ai/download), [Claude Code](https://claude.ai/code), [Cursor](https://cursor.com), [Windsurf](https://codeium.com/windsurf), [DeskAgent](https://deskagent.de), and more.

## Features

- Real-time power and energy monitoring (all devices)
- 3-phase measurements — voltage, current, power factor per phase
- Historical energy data with daily and hourly profiles
- PV / solar feed-in tracking and self-consumption analysis
- Device control — on/off/toggle via local or cloud API
- Dual transport — SSE and Streamable HTTP served simultaneously
- Local authentication — HTTP Basic (Gen1) and HTTP Digest (Gen2+)

## Supported Devices

| Device | Type | Notes |
|--------|------|-------|
| Shelly Pro 3EM | `pro3em` | 3-phase, 60-day history |
| Shelly 3EM | `3em` | 3-phase Gen1 |
| Shelly EM | `em` | 2-channel with CT clamps |
| Shelly Plus PM | `pm` | Single consumer measurement |
| Shelly Plus 1PM | `1pm` | Switch with power measurement |
| Shelly 2PM | `2pm` | Roller/blind control + power measurement |

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/game4automation/shelly
cd shelly
uv sync
```

Connect the server to your MCP client using the [configuration examples](#mcp-client-configuration) below.

### As a DeskAgent plugin

Clone directly into the DeskAgent plugins directory — no manual configuration needed:

```bash
cd /path/to/deskagent/plugins
git clone https://github.com/game4automation/shelly
```

Restart DeskAgent — the plugin is auto-discovered.

## Configuration

Copy the example config and fill in your values:

```bash
cp config.example.json config.json
chmod 600 config.json   # restrict access — file contains credentials
```

**DeskAgent** — add the `shelly` block to your `config/apis.json`:

```json
{
  "shelly": {
    "enabled": true,
    "devices": [
      {"name": "MainConnection", "ip": "192.168.1.100", "type": "pro3em", "username": "admin", "password": ""},
      {"name": "HeatPump",       "ip": "192.168.1.101", "type": "em",     "username": "admin", "password": ""}
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

| Key | Default | Description |
|-----|---------|-------------|
| `devices` | `[]` | Local devices with IP address |
| `devices[].username` | — | Device login username (optional) |
| `devices[].password` | — | Device login password (optional) |
| `cloud.server` | — | Cloud server hostname from the Shelly app |
| `cloud.auth_key` | — | Cloud auth key (User Settings → Authorization cloud key) |
| `prefer_local` | `false` | Use local API even when cloud is available |
| `price_per_kwh` | `0.30` | Electricity price in EUR for cost calculations |

At least one of `devices` or `cloud.auth_key` must be set. Local and cloud sources can be used together.

### Local device authentication

Shelly devices support password protection which is off by default. If you have set a password in the device's web UI, add `username` and `password` to the device entry in config. The server negotiates the auth scheme automatically:

| Generation | Auth scheme | Notes |
|------------|-------------|-------|
| Gen1 (1EM, 3EM) | HTTP Basic Auth | Username is typically `admin` |
| Gen2+ (Pro 3EM, Plus PM, …) | HTTP Digest Auth | Username is always `admin` |

Omitting `username`/`password` (or leaving `password` as `""`) means unauthenticated access, which works fine for devices with no password set. A `401 Unauthorized` error in tool output means the device has a password but none was configured here.

## Docker

```bash
# Build
docker build -t shelly-mcp .

# Run (mounts your local config.json read-only)
docker run -p 8000:8000 -v $(pwd)/config.json:/app/config.json:ro shelly-mcp
```

Or with Docker Compose (see [`docs/docker-compose.yml`](docs/docker-compose.yml)):

```bash
cp config.example.json config.json   # fill in your values
docker compose -f docs/docker-compose.yml up
```

The container starts with `--server` by default (both SSE and Streamable HTTP on port 8000). Override the command to change transport or port:

```bash
# SSE only on port 9000
docker run -p 9000:9000 -v $(pwd)/config.json:/app/config.json:ro \
  shelly-mcp python -m shelly_mcp --sse --host 0.0.0.0 --port 9000
```

The `config.json` must be mounted — the container has no config of its own.

## Kubernetes

A ready-to-use manifest is provided at [`docs/kubernetes.yml`](docs/kubernetes.yml). It creates a `shelly-mcp` namespace with a Deployment, Service, and optional Ingress.

**1. Create the config secret** with both `config.json` and the Bearer token:

```bash
# Generate a strong token
TOKEN=$(openssl rand -hex 32)

kubectl create secret generic shelly-mcp-config \
  --from-file=config.json=/path/to/your/config.json \
  --from-literal=mcp-token=$TOKEN \
  -n shelly-mcp

echo "Bearer token: $TOKEN"   # save this — you'll need it in your MCP client
```

**2. Apply the manifest:**

```bash
kubectl apply -f docs/kubernetes.yml
```

The Ingress is pre-configured for an nginx ingress controller with long timeouts (required for SSE). Edit `shelly-mcp.example.com` and the optional `tls` block to match your cluster. Remove the Ingress resource entirely if you only need in-cluster access.

> **Security:** Kubernetes Secrets are base64-encoded, not encrypted. To protect credentials at rest, enable [etcd encryption](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/) in your cluster, or use an external secrets manager such as [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) or [Vault](https://developer.hashicorp.com/vault/docs/platform/k8s).

## Running

### stdio (default)

Without any flags the server uses **stdio** — the standard transport for most MCP clients:

```bash
uv run python -m shelly_mcp
# or after uv sync:
shelly-mcp
```

### MCP client configuration

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "shelly": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/shelly-mcp", "python", "-m", "shelly_mcp"]
    }
  }
}
```

#### Claude Code (CLI)

```bash
claude mcp add shelly -- uv run --directory /path/to/shelly-mcp python -m shelly_mcp
```

Or add manually to `~/.claude/claude_mcp_servers.json`:

```json
{
  "shelly": {
    "command": "uv",
    "args": ["run", "--directory", "/path/to/shelly-mcp", "python", "-m", "shelly_mcp"]
  }
}
```

#### Cursor

Add to `.cursor/mcp.json` in your project root, or to `~/.cursor/mcp.json` for global access:

```json
{
  "mcpServers": {
    "shelly": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/shelly-mcp", "python", "-m", "shelly_mcp"]
    }
  }
}
```

#### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "shelly": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/shelly-mcp", "python", "-m", "shelly_mcp"]
    }
  }
}
```

#### DeskAgent

Add the `shelly` block to your `config/apis.json` as shown in the [Configuration](#configuration) section. DeskAgent auto-discovers the plugin without a separate stdio entry.

#### Generic MCP client

Any client that follows the [MCP specification](https://spec.modelcontextprotocol.io/) and supports stdio transport can connect by running:

```
command: uv
args:    ["run", "--directory", "/path/to/shelly-mcp", "python", "-m", "shelly_mcp"]
```

For HTTP-based clients use the `--sse` or `--http` flags (see [HTTP transports](#http-transports) below) and point the client at `http://localhost:8000`.

### HTTP transports

| Flag | Endpoints | Use case |
|------|-----------|----------|
| `--sse` | `/sse`, `/messages` | Clients that use Server-Sent Events |
| `--http` | `/mcp` | Clients that use Streamable HTTP |
| `--server` | `/sse`, `/messages`, `/mcp` | Both transports on one port |
| `--sse --http` | same as `--server` | |

```bash
# SSE only
shelly-mcp --sse

# Streamable HTTP only
shelly-mcp --http

# Both transports (recommended for maximum compatibility)
shelly-mcp --server --host 0.0.0.0 --port 8000
```

All HTTP flags accept `--host` (default `127.0.0.1`) and `--port` (default `8000`).

### Bearer token authentication

Set the `SHELLY_MCP_TOKEN` environment variable to enable Bearer token authentication on all HTTP endpoints. When set, every request must include the token in the `Authorization` header:

```bash
# Start server with auth enabled
export SHELLY_MCP_TOKEN=mysecrettoken
shelly-mcp --server --host 0.0.0.0 --port 8000

# Connect from a client
curl -H "Authorization: Bearer mysecrettoken" http://localhost:8000/mcp
```

If `SHELLY_MCP_TOKEN` is not set (or empty), authentication is disabled — suitable for localhost-only use. Generate a strong token with:

```bash
openssl rand -hex 32
```

Configure your MCP client to send the token. In Claude Desktop / Claude Code add an `env` block to the server entry:

```json
{
  "mcpServers": {
    "shelly": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/shelly-mcp", "python", "-m", "shelly_mcp"],
      "env": {
        "SHELLY_MCP_TOKEN": "mysecrettoken"
      }
    }
  }
}
```

> **Note:** Bearer auth only applies to HTTP transports (`--sse`, `--http`, `--server`). stdio mode has no network exposure and does not use this variable.

## Available Tools

| Tool | Description |
|------|-------------|
| `shelly_list_devices` | List all devices with status, type, room, and current power |
| `shelly_get_status` | Detailed status for one device or all devices |
| `shelly_get_power` | Current power draw of all devices |
| `shelly_get_energy_live` | Real-time measurements per phase (voltage, current, PF) |
| `shelly_get_consumption_summary` | Power and energy overview with cost estimate |
| `shelly_get_energy_history` | Historical data for a device (day / week / month / year) |
| `shelly_get_daily_consumption` | Daily totals for all energy meters (up to 30 days) |
| `shelly_get_hourly_profile` | 24 h profile with base load and peak analysis |
| `shelly_switch_control` | Turn a device on, off, or toggle |
| `shelly_cover_status` | Get cover state and position for a 2PM in roller mode |
| `shelly_cover_control` | Open, close, stop, or move a cover to a specific position (0–100%) |

> **Cover tools** work with **local devices only** — the Shelly Cloud API has no cover RPC. The device must be configured in **roller mode** via its web UI or the Shelly app (if it is in switch mode the API returns an error). Position-based control (`action: position`) additionally requires completed calibration.

## Prompts

Pre-built prompts usable from any MCP client that supports them.

| Prompt | Arguments | Description |
|--------|-----------|-------------|
| `energy_report` | — | Full weekly report with charts and optimization analysis |
| `analyze_device` | `device` | Deep-dive into a single device (status, live data, history, profile) |
| `daily_briefing` | — | Quick morning summary — current load, offline devices, yesterday vs today |
| `find_savings` | — | Identify energy waste and produce quantified saving recommendations |

## Resources

Read-only data sources exposed over MCP.

| URI | MIME type | Description |
|-----|-----------|-------------|
| `shelly://config` | `application/json` | Server configuration (auth keys redacted) |
| `shelly://devices` | `application/json` | Local device list from config (name, IP, type) |
| `shelly://integration` | `application/json` | Integration schema for settings UIs |

## Energy Report Agent

`agents/energy_report.md` is a pre-built agent prompt that generates a complete energy report including:

- 7-day daily consumption chart
- PV feed-in vs. grid draw (stacked area)
- Self-consumption rate gauge
- Load profile heatmap (hour × weekday)
- Consumer distribution pie chart
- Anomaly detection and optimization suggestions

Load it in DeskAgent or any MCP client that supports agent prompts.

## Project Structure

```
shelly_mcp/
├── __init__.py     # package entry, registers tools / prompts / resources
├── __main__.py     # CLI — transport selection (stdio / SSE / HTTP)
├── app.py          # FastMCP instance and metadata constants
├── config.py       # configuration loading (DeskAgent + standalone)
├── cloud.py        # Shelly Cloud API (GET/POST, device list, rooms)
├── local.py        # local RPC API with Basic/Digest auth support
├── utils.py        # format helpers, device-type detection
├── tools.py        # 11 MCP tool definitions
├── prompts.py      # 4 MCP prompts (energy_report, analyze_device, …)
└── resources.py    # 3 MCP resources (shelly://config, devices, integration)
docs/
├── docker-compose.yml  # Docker Compose deployment
└── kubernetes.yml      # Kubernetes manifests (Namespace, Deployment, Service, Ingress)
```

## Links

- [Shelly Gen2+ API](https://shelly-api-docs.shelly.cloud/gen2/)
- [Shelly Cloud API](https://shelly-api-docs.shelly.cloud/cloud-control-api/)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [DeskAgent](https://deskagent.de)

## License

MIT — see [LICENSE](LICENSE)

## Disclaimer

This plugin is not affiliated with or endorsed by Shelly Group AD. Use at your own risk.
This plugin is a personal project that I maintain in my free time.
- Refer to the licence for more information.

### EU GDPR — Commercial Use

**This software is not intended for commercial deployments without prior modifications and a legal review.** In its current form it is designed for personal household use, where the [household exemption (Art. 2(2)(c) GDPR)](https://gdpr-info.eu/art-2-gdpr/) applies.

Commercial or business deployments (property management, smart home services, building operators, etc.) must address the following before going live:

- **Network identifiers** — device IP addresses and WiFi SSIDs are collected and constitute personal data under GDPR Art. 4(1).
- **Third-party cloud services** — energy data is transmitted to Shelly Group AD's cloud servers. A Data Processing Agreement (Art. 28) with Shelly Group AD must be in place.
- **Credentials at rest** — `config.json` and Kubernetes Secrets store credentials in plaintext / base64. Encryption at rest must be implemented (Art. 32).
- **HTTP endpoint authentication** — the `--sse`, `--http`, and `--server` modes include optional Bearer token authentication via the `SHELLY_MCP_TOKEN` environment variable. **It is strongly recommended to enable it** whenever the server is reachable beyond localhost. Without it, anyone with network access can read device data and trigger switch/cover commands. See [Bearer token authentication](#bearer-token-authentication).
- **Lawful basis** — a documented lawful basis (Art. 6) and Records of Processing Activities must be established before processing personal data of residents or tenants.

The authors accept no liability for GDPR non-compliance arising from use of this software outside its intended personal/household context.