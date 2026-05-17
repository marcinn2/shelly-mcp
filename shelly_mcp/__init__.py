"""
Shelly Smart Home MCP Server
=============================
MCP Server for Shelly Smart Home devices - energy measurement and monitoring.
Supports both Shelly Cloud API and local access via IP.

API Documentation:
- Cloud: https://shelly-api-docs.shelly.cloud/cloud-control-api/
- Local: https://shelly-api-docs.shelly.cloud/gen2/
"""

from .app import mcp, TOOL_METADATA, INTEGRATION_SCHEMA, HIGH_RISK_TOOLS
from . import tools, prompts, resources

__all__ = ["mcp", "TOOL_METADATA", "INTEGRATION_SCHEMA", "HIGH_RISK_TOOLS", "tools", "prompts", "resources"]
