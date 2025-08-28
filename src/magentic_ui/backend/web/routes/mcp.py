from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio

from magentic_ui.tools.mcp import AggregateMcpWorkbench, NamedMcpServerParams

router = APIRouter()


class TestMCPRequest(BaseModel):
    server_config: Dict[str, Any]  # NamedMCPServerConfig


class TestMCPResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


async def test_mcp_server_connection(server_config: Dict[str, Any]) -> Dict[str, Any]:
    """Test MCP server using existing AggregateMcpWorkbench."""

    try:
        # Convert to NamedMcpServerParams
        named_params = NamedMcpServerParams(
            server_name=server_config["server_name"],
            server_params=server_config["server_params"],
        )

        # Use existing workbench for testing
        workbench = AggregateMcpWorkbench([named_params])

        async with workbench:
            # Test by listing tools with timeout (this validates connection)
            try:
                # Set a reasonable timeout for the connection test (30 seconds)
                tools = await asyncio.wait_for(workbench.list_tools(), timeout=30.0)

                return {
                    "success": True,
                    "message": "Server connection successful",
                    "details": {
                        "server_type": server_config["server_params"]["type"],
                        "server_name": server_config["server_name"],
                        "tools_found": len(tools),
                    },
                }
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "message": "Server connection timed out",
                    "error": "Connection test timed out after 30 seconds. The server may be unreachable or taking too long to respond.",
                }

    except ValueError as e:
        # Configuration validation error
        return {
            "success": False,
            "message": "Invalid server configuration",
            "error": str(e),
        }
    except Exception as e:
        # Connection or protocol error
        return {
            "success": False,
            "message": "Server connection failed",
            "error": str(e),
        }


@router.post("/test-mcp-server", response_model=TestMCPResponse)
async def test_mcp_server(request: TestMCPRequest):
    """Test MCP server connection using existing workbench."""

    try:
        result = await test_mcp_server_connection(request.server_config)
        return TestMCPResponse(**result)
    except Exception as e:
        return TestMCPResponse(success=False, message="Test failed", error=str(e))
