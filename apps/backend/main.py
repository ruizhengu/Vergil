import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from grafi.common.models.mcp_connections import StreamableHttpConnection
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from agents.react_agent import TrueReActAssistant
from contextlib import asynccontextmanager
from tools.mock_tool import SimpleMockTool

import uvicorn
import sys
import os

from routers import chat, tools, contracts, transactions, approval, wallet
from grafi.common.containers.container import container, setup_tracing
from grafi.common.instrumentations.tracing import TracingOptions

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

tracer = setup_tracing(
                tracing_options=TracingOptions.PHOENIX,
                collector_endpoint="phoenix",
                collector_port=4317,
                project_name="grafi-trace",
            )

# tool = SimpleMockTool()

# assistant = (TrueReActAssistant.builder()
#             .name("TrueReActSmartContractAgent")
#             .model(os.getenv('OPENAI_MODEL', 'gpt-4'))
#             .api_key(os.getenv("OPENAI_API_KEY", ""))
#             .function_call_tool(tool)
#             .build()
#         )

async def create_react_assistant():
    """Create the True ReAct Assistant with MCP tools"""
    mcp_server_url = os.getenv('MCP_SERVER_URL', 'http://localhost:8081/mcp/')
    print(f"Connecting to MCP server at: {mcp_server_url}")
    
    mcp_config: Dict[str, StreamableHttpConnection] = {
        "smart-contract-server": StreamableHttpConnection(
            url=mcp_server_url,
            transport="http"
        )
    }

    try:
        print("Building MCP tool...")
        mcp_tool = await MCPTool.builder().connections(mcp_config).a_build()
        print("MCP tool built successfully")
        
        print("Building assistant...")
        assistant = (TrueReActAssistant.builder()
            .name("TrueReActSmartContractAgent")
            .model(os.getenv('OPENAI_MODEL', 'gpt-4o'))
            .api_key(os.getenv("OPENAI_API_KEY", ""))
            .function_call_tool(mcp_tool)
            .build()
        )
        print("Assistant built successfully")
        
        return assistant
    except Exception as e:
        print(f"Error building MCP tool or assistant: {e}")
        print(f"Error type: {type(e)}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Use FastAPI lifespan to init/teardown resources.
    Puts the assistant on app.state for access in routes.
    """
    app.state.assistant = None
    try:
        assistant = await create_react_assistant()
        app.state.assistant = assistant
        print("Backend API: react assistant built successfully")
        print("Backend API: Server ready on http://localhost:8000")
    except Exception as e:
        # Keep running in fallback mode
        print(f"Backend API: Failed to initialize assistant: {e}")
        print("Backend API: Running in fallback mode (assistant=None)")

    # Hand control back to FastAPI
    try:
        yield
    finally:
        # Shutdown
        # If your assistant holds network conns, close them here.
        app.state.assistant = None
        print("Backend API: Lifespan shutdown complete")

app = FastAPI(title="Smart Contract Assistant API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(tools.router)
app.include_router(contracts.router)
app.include_router(transactions.router)
app.include_router(approval.router)
app.include_router(wallet.router)

@app.get("/")
async def root():
    assistant_ready = getattr(app.state, "assistant", None) is not None
    return {
        "message": "Smart Contract Assistant Backend API", 
        "status": "running",
        "architecture": "Separated Backend API with FastAPI Routers",
        "mcp_status": "connected" if assistant_ready else "fallback_mode",
        "available_endpoints": [
            "/api/chat/",
            "/api/tools/", 
            "/api/contracts/erc20/generate",
            "/api/contracts/templates/erc20",
            "/health",
            "/docs"
        ]
    }

@app.get("/health")
async def health_check():
    assistant_ready = getattr(app.state, "assistant", None) is not None
    return {
        "status": "healthy",
        "assistant_ready": assistant_ready is not None,
        "timestamp": datetime.now().isoformat(),
        "components": {
            "backend_api": "running",
            "mcp_connection": "connected" if assistant_ready else "disconnected",
            "frontend_cors": "enabled"
        }
    }

if __name__ == "__main__":
    print("Starting Backend API Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")