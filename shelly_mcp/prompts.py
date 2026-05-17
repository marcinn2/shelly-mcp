from .app import mcp


@mcp.prompt(
    name="energy_report",
    description="Generate a full weekly energy report with charts and optimization analysis",
)
def prompt_energy_report() -> str:
    return """\
You are an energy analysis assistant. Generate a comprehensive energy report for this Shelly smart home installation.

## Steps

1. **Device overview** — call `shelly_list_devices` to see all devices, their rooms, types, and online status.

2. **Current power** — call `shelly_get_power` to get the live power draw and identify the biggest consumers.

3. **7-day history** — call `shelly_get_daily_consumption(days=7)` to collect daily totals per device.

4. **Hourly profile** — call `shelly_get_hourly_profile` for the grid meter to identify base load, peaks, and PV patterns.

5. **Analysis** — based on the data above, identify:
   - Unusually high days (>50 % above average)
   - High night-time base load (standby devices)
   - Phase imbalances
   - PV self-consumption rate (if solar device present)

6. **Cost estimate** — calculate 7-day cost and project monthly spend.

## Output format

```
# Energy Report — <today's date>

## Summary
- Total consumption (7 days): X kWh
- Daily average: X kWh
- PV feed-in: X kWh  (if applicable)
- Self-consumption rate: X %  (if applicable)
- Estimated cost (7 days): X EUR

## Device Status
| Device | Room | Status | Current Power |
| ...

## Daily Consumption
<table or list of day-by-day values>

## Anomalies
- <bullet list of anything unusual>

## Optimization Recommendations
- <concrete, actionable suggestions>
```

Use only real data returned by the tools. Do not invent values.
"""


@mcp.prompt(
    name="analyze_device",
    description="Deep-dive analysis of a single Shelly device",
)
def prompt_analyze_device(device: str) -> str:
    return f"""\
Perform a detailed analysis of the Shelly device **{device}**.

## Steps

1. Call `shelly_get_status(device="{device}")` for current status, uptime, and temperature.
2. Call `shelly_get_energy_live(device="{device}")` for live per-phase measurements.
3. Call `shelly_get_energy_history(device="{device}", period="week")` for the 7-day history.
4. Call `shelly_get_hourly_profile(device="{device}")` for today's hourly profile.

## Output format

```
# Device Analysis — {device}

## Current Status
- Online / Offline, uptime, temperature

## Live Measurements
- Per-phase voltage, current, power, power factor

## 7-Day History
- Daily consumption table
- Total and average

## Today's Profile
- Hourly chart (text)
- Peak hour, base load

## Assessment
- Is consumption normal for this device type?
- Any anomalies or warnings?
- Recommendations
```
"""


@mcp.prompt(
    name="daily_briefing",
    description="Quick morning energy briefing — current power, offline devices, and overnight consumption",
)
def prompt_daily_briefing() -> str:
    return """\
Give a concise morning energy briefing for this Shelly installation. Keep it short — 10 lines maximum.

## Steps

1. Call `shelly_get_power` for live power of all devices.
2. Call `shelly_list_devices` to check for any offline devices.
3. Call `shelly_get_daily_consumption(days=2)` to compare yesterday vs. the day before.

## Output format

```
⚡ Energy Briefing — <today>

Current load:   X W  (X devices online, Y offline)
Yesterday:      X kWh  (Δ +/- X % vs previous day)
Biggest draw:   <device name>  X W

Alerts:
- <only if something is wrong or unusual>
```

Be concise. Skip sections that have nothing notable to report.
"""


@mcp.prompt(
    name="find_savings",
    description="Identify energy waste and produce concrete saving recommendations",
)
def prompt_find_savings() -> str:
    return """\
Analyse this Shelly installation for energy waste and saving opportunities.

## Steps

1. Call `shelly_get_daily_consumption(days=14)` for a two-week baseline.
2. Call `shelly_get_hourly_profile` for each energy meter to find base load and peaks.
3. Call `shelly_get_consumption_summary` for current totals and costs.

## What to look for

- **Standby waste** — consumption between 00:00 and 06:00 that exceeds expected base load
- **Load peaks** — single hours with consumption > 2× the daily average per hour
- **PV mismatch** — high consumption hours that don't overlap with solar production hours
- **Phase imbalance** — one phase carrying significantly more load than others
- **Cost outliers** — devices or days with disproportionate cost contribution

## Output format

```
# Saving Opportunities

## Baseline
- 14-day average: X kWh/day  (~X EUR/month)

## Issues Found
| # | Issue | Device / Time | Potential saving |
|---|-------|---------------|-----------------|
| 1 | High standby | ... | X kWh/month |
| ...

## Recommendations
1. <specific, actionable step>
2. ...

## Estimated monthly saving: X EUR
```

Quantify every recommendation. Do not suggest actions if the data does not support them.
"""
