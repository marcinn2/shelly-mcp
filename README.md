# Shelly MCP Server

MCP Server für Shelly Smart Home Geräte - Energiemessung und -monitoring.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- Aktuelle Leistung und Verbrauch aller Geräte
- Historische Energiedaten (Cloud API)
- 3-Phasen Messwerte (Spannung, Strom, Leistungsfaktor)
- Gerätesteuerung (ein/aus/toggle)
- Unterstützt lokalen Zugriff und Shelly Cloud

## Unterstützte Geräte

| Gerät | Typ | Beschreibung |
|-------|-----|--------------|
| Shelly Pro 3EM | `pro3em` | 3-Phasen Energiemessung, 60 Tage Historie |
| Shelly 3EM | `3em` | 3-Phasen Energiemessung (Gen1) |
| Shelly EM | `em` | 2-Kanal Energiemessung mit CT-Klemmen |
| Shelly Plus PM | `pm` | Einzelverbraucher-Messung |
| Shelly Plus 1PM | `1pm` | Schalter mit Leistungsmessung |

## Installation

### Als DeskAgent Plugin

```bash
cd /path/to/deskagent/plugins
git clone https://github.com/realvirtual/shelly
```

### Standalone (Claude Desktop, etc.)

```bash
git clone https://github.com/realvirtual/shelly
cd shelly
pip install mcp
```

## Konfiguration

Kopiere `config.example.json` zu `config.json` und passe die Werte an:

```json
{
  "shelly": {
    "enabled": true,
    "devices": [
      {"name": "Hausanschluss", "ip": "192.168.1.100", "type": "pro3em"},
      {"name": "Waermepumpe", "ip": "192.168.1.101", "type": "em"}
    ],
    "cloud": {
      "enabled": false,
      "server": "shelly-70-eu.shelly.cloud",
      "auth_key": "YOUR_AUTH_KEY"
    },
    "prefer_local": true,
    "price_per_kwh": 0.30
  }
}
```

### Shelly Cloud API (optional)

Für historische Daten wird die Shelly Cloud API benötigt:

1. **Auth Key erstellen**: Shelly App → User Settings → Authorization cloud key
2. **Server ermitteln**: Der Server steht im Auth Key oder in der App
3. **In config.json eintragen**

## Nutzung

### Mit Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shelly": {
      "command": "python",
      "args": ["mcp/__init__.py"],
      "cwd": "/path/to/shelly"
    }
  }
}
```

### Mit DeskAgent

Plugin wird automatisch erkannt wenn in `plugins/shelly/` installiert.

## Verfügbare Tools

| Tool | Beschreibung |
|------|--------------|
| `shelly_list_devices` | Listet alle Geräte mit Metadaten |
| `shelly_get_status` | Detaillierter Status eines Geräts |
| `shelly_get_power` | Aktuelle Leistung aller Geräte |
| `shelly_get_energy_live` | Echtzeit-Messwerte (3-Phasen) |
| `shelly_get_energy_history` | Historische Energiedaten |
| `shelly_get_daily_consumption` | Tagesverbrauch (7-30 Tage) |
| `shelly_get_hourly_profile` | 24h-Profil mit Analyse |
| `shelly_get_consumption_summary` | Verbrauchsübersicht mit Kosten |
| `shelly_switch_control` | Schalter steuern (on/off/toggle) |

### Beispiele

```
shelly_list_devices()
```

**Output:**
```
**Shelly-Geräte:**

### Cloud-Geräte

- **PV Einspeisung** 🟢
  ID: `c8f09e878b04`
  Typ: SPEM-003CEBEU (emeter) Gen2
  Raum: PV Erzeugung
  Leistung: -1.52 kW
```

```
shelly_get_power()
```

**Output:**
```
**Aktuelle Leistung:**

- **Hausanschluss**: 2.45 kW
- **Wärmepumpe**: 1.20 kW

**Gesamt: 3.65 kW**
```

```
shelly_get_energy_history(device="c8f09e878b04", period="week")
```

**Output:**
```
**Energieverlauf - PV Einspeisung**
Zeitraum: Diese Woche (täglich)

- 01-19: ☀️ 1206.7 kWh eingespeist | 0.3 kWh bezogen
- 01-20: ☀️ 52475.3 kWh eingespeist | 3.0 kWh bezogen

**Summe:**
- Einspeisung: 87664.0 kWh
- Bezug: 6.1 kWh
```

## API-Referenz

### Lokale API (Gen2+)

Shelly Gen2+ Geräte verwenden RPC über HTTP:

```bash
# Geräte-Status
curl http://192.168.1.100/rpc/Shelly.GetStatus

# Energie-Meter Status
curl http://192.168.1.100/rpc/EM.GetStatus?id=0
```

### Cloud API Endpoints

| Endpoint | Beschreibung |
|----------|--------------|
| `device/all_status` | Status aller Geräte (Echtzeit) |
| `interface/device/list` | Geräte-Metadaten (Name, Raum, IP) |
| `v2/statistics/power-consumption/em-3p` | Historische Energiedaten |

**Rate Limit:** 1 Request pro Sekunde

## Troubleshooting

### Gerät nicht erreichbar

1. Prüfe IP-Adresse (Shelly App → Gerät → Device Information)
2. Prüfe ob Gerät im gleichen Netzwerk ist
3. Prüfe Firewall-Einstellungen

### Keine historischen Daten

- Pro 3EM speichert 60 Tage in 1-Minuten-Intervallen
- Andere Geräte haben begrenzte Historie
- Alternative: Shelly Cloud API aktivieren

## Energie-Report Agent

Der mitgelieferte Agent `agents/energy_report.md` erstellt einen vollständigen Energie-Report mit:

- Charts (Tagesverbrauch, PV-Bilanz, Verbraucher-Verteilung)
- 7-Tage-Analyse mit historischen Daten
- Auffälligkeiten (hohe Verbräuche, Schwankungen)
- Optimierungspotentiale (Lastverschiebung, PV-Nutzung)

## Links

- [Shelly Gen2+ API Dokumentation](https://shelly-api-docs.shelly.cloud/gen2/)
- [Shelly Cloud API](https://shelly-api-docs.shelly.cloud/cloud-control-api/)
- [EnergyMeter Component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/EM/)

## License

MIT License - siehe [LICENSE](LICENSE)
