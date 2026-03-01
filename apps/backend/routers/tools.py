"""
Tools router for MCP tool management and exploration
"""
import sys
import os

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any
from deps.assistant import get_assistant

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(prefix="/api/tools", tags=["tools"])

@router.get("/")
async def list_tools(assistant = Depends(get_assistant)):
    try:
        if not assistant:
            return {
                "success": True,
                "tools": [],
                "message": "Assistant not connected to MCP server",
                "status": "fallback_mode"
            }
        
        # Get function specs from the MCP tool
        function_call_tool = assistant.function_call_tool
        if hasattr(function_call_tool, 'function_specs'):
            tools = [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters.dict() if spec.parameters else {}
                }
                for spec in function_call_tool.function_specs
            ]
            
            return {
                "success": True,
                "tools": tools,
                "count": len(tools),
                "status": "connected"
            }
        else:
            return {
                "success": True, 
                "tools": [],
                "message": "No tools available",
                "status": "connected_no_tools"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/{tool_name}")
async def get_tool_info(tool_name: str, assistant = Depends(get_assistant)):
    """Get detailed information about a specific tool"""
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        if not assistant:
            raise HTTPException(status_code=503, detail="Assistant not connected to MCP server")
        
        function_call_tool = assistant.function_call_tool
        if hasattr(function_call_tool, 'function_specs'):
            for spec in function_call_tool.function_specs:
                if spec.name == tool_name:
                    return {
                        "success": True,
                        "tool": {
                            "name": spec.name,
                            "description": spec.description,
                            "parameters": spec.parameters.dict() if spec.parameters else {},
                            "required_params": spec.parameters.required if spec.parameters else []
                        }
                    }
        
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/{tool_name}/invoke")
async def invoke_tool(tool_name: str, parameters: Dict[str, Any], assistant = Depends(get_assistant)):
    try:
        if not assistant:
            raise HTTPException(status_code=503, detail="Assistant not connected to MCP server")

        return {
            "success": True,
            "message": f"Tool '{tool_name}' invocation not yet implemented",
            "tool_name": tool_name,
            "parameters": parameters
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/status/mcp")
async def mcp_status(assistant = Depends(get_assistant)):
    return {
        "mcp_connected": assistant is not None,
        "server_url": "http://localhost:8081/mcp/",
        "status": "connected" if assistant else "disconnected",
        "tools_available": len(assistant.function_call_tool.function_specs) if assistant and hasattr(assistant.function_call_tool, 'function_specs') else 0
    }