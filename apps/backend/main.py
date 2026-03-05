import os
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Dict
from grafi.common.models.mcp_connections import StreamableHttpConnection
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from utils.safe_mcp_tool import SafeMCPTool
from agents.orchestration_agent import OrchestrationAssistant
from agents.generate_contract_agent import GenerateContractAssistant
from agents.deployment_agent import DeploymentAssistant
from contextlib import asynccontextmanager
import logging
import uvicorn
import sys

# Register PostgreSQL event store (must happen before any assistant is created)
import event_store.postgres  # noqa: F401

# Suppress noisy grafi polling logs, but show topic condition failures
import loguru
loguru.logger.remove()

def _log_filter(record):
    msg = record["message"]
    if "waiting for new messages" in msg:
        return False
    if "No new messages" in msg:
        return False
    if "_is_quiescent_unlocked" in msg:
        return False
    if "Tracker:" in msg and "is_quiescent" in msg:
        return False
    if "invoke_parallel: tracker_id" in msg:
        return False
    if "init_workflow:" in msg:
        return False
    return True

loguru.logger.add(sys.stderr, level="DEBUG", filter=_log_filter)

from db.models import Base
from db.session import engine
from routers import chat, tools, contracts, transactions, approval, wallet, data
from grafi.common.containers.container import container, setup_tracing
from grafi.common.instrumentations.tracing import TracingOptions

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the postgres event store to initialize database connection
import event_store.postgres

load_dotenv()

try:
    tracer = setup_tracing(
                tracing_options=TracingOptions.PHOENIX,
                collector_endpoint="http://phoenix",
                collector_port=4317,
                project_name="grafi-trace",
            )
except Exception as e:
    print(f"Warning: Could not setup tracing: {e}")
    tracer = None

async def create_orchestration_assistant(generate_contract_assistant=None, deployment_assistant=None):
    """Create the Orchestration Assistant with MCP tools"""
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
        mcp_tool = await MCPTool.builder().connections(mcp_config).build()
        print("MCP tool built successfully")

        print("Building orchestration assistant...")
        builder = (OrchestrationAssistant.builder()
            .name("OrchestrationAgent")
            .model(os.getenv('ZAI_MODEL', 'zai'))
            .api_key(os.getenv("ZAI_API_KEY", ""))
            .function_call_tool(mcp_tool)
        )
        if generate_contract_assistant is not None:
            builder = builder.generate_contract_assistant(generate_contract_assistant)
        if deployment_assistant is not None:
            builder = builder.deployment_assistant(deployment_assistant)
        assistant = builder.build()
        print("Orchestration assistant built successfully")

        return assistant
    except Exception as e:
        print(f"Error building orchestration assistant: {e}")
        print(f"Error type: {type(e)}")
        print("Running in fallback mode - MCP tools will not be available")
        return None

async def create_generate_contract_assistant():
    """Create the Generate Contract Assistant with OpenZeppelin MCP tools"""
    oz_mcp_url = os.getenv('OZ_MCP_SERVER_URL', 'http://localhost:8083/mcp/')
    print(f"Connecting to OpenZeppelin MCP server at: {oz_mcp_url}")

    oz_config: Dict[str, StreamableHttpConnection] = {
        "openzeppelin-contracts": StreamableHttpConnection(
            url=oz_mcp_url,
            transport="http"
        )
    }

    try:
        print("Building OZ MCP tool for generate contract agent...")
        oz_mcp_tool = await SafeMCPTool.builder().connections(oz_config).build()
        print("OZ MCP tool built successfully for generate contract agent")

        print("Building generate contract assistant...")
        assistant = (GenerateContractAssistant.builder()
            .name("GenerateContractAgent")
            .model(os.getenv('ZAI_MODEL', 'zai'))
            .api_key(os.getenv("ZAI_API_KEY", ""))
            .oz_mcp_tool(oz_mcp_tool)
            .build()
        )
        print("Generate contract assistant built successfully")

        return assistant
    except Exception as e:
        print(f"Error building generate contract assistant: {e}")
        print(f"Error type: {type(e)}")
        print("Running in fallback mode - contract generation will not be available")
        return None


async def create_deployment_assistant():
    """Create the Deployment Assistant with MCP tools"""
    mcp_server_url = os.getenv('MCP_SERVER_URL', 'http://localhost:8081/mcp/')
    print(f"Connecting to MCP server for deployment agent at: {mcp_server_url}")

    mcp_config: Dict[str, StreamableHttpConnection] = {
        "smart-contract-server": StreamableHttpConnection(
            url=mcp_server_url,
            transport="http"
        )
    }

    try:
        print("Building MCP tool for deployment agent...")
        mcp_tool = await MCPTool.builder().connections(mcp_config).build()
        print("MCP tool built successfully for deployment agent")

        print("Building deployment assistant...")
        assistant = (DeploymentAssistant.builder()
            .name("DeploymentAgent")
            .model(os.getenv('ZAI_MODEL', 'zai'))
            .api_key(os.getenv("ZAI_API_KEY", ""))
            .function_call_tool(mcp_tool)
            .build()
        )
        print("Deployment assistant built successfully")

        return assistant
    except Exception as e:
        print(f"Error building deployment assistant: {e}")
        print(f"Error type: {type(e)}")
        print("Running in fallback mode - deployment will not be available")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Use FastAPI lifespan to init/teardown resources.
    Puts the assistant on app.state for access in routes.
    """
    app.state.assistant = None
    app.state.generate_contract_assistant = None
    app.state.deployment_assistant = None

    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        print("Backend API: Database tables created successfully")
    except Exception as e:
        print(f"Backend API: Failed to create database tables: {e}")

    # Build generate contract assistant first (used by ReAct agent via AgentCallingTool)
    generate_contract_assistant = None
    try:
        generate_contract_assistant = await create_generate_contract_assistant()
        app.state.generate_contract_assistant = generate_contract_assistant
        print("Backend API: generate contract assistant built successfully")
    except Exception as e:
        print(f"Backend API: Failed to initialize generate contract assistant: {e}")
        print("Backend API: Contract generation will not be available")

    # Build deployment assistant (used by orchestration agent via AgentCallingTool)
    deployment_assistant = None
    try:
        deployment_assistant = await create_deployment_assistant()
        app.state.deployment_assistant = deployment_assistant
        print("Backend API: deployment assistant built successfully")
    except Exception as e:
        print(f"Backend API: Failed to initialize deployment assistant: {e}")
        print("Backend API: Deployment delegation will not be available")

    # Build orchestration assistant, injecting sub-agents
    try:
        assistant = await create_orchestration_assistant(generate_contract_assistant, deployment_assistant)
        app.state.assistant = assistant
        print("Backend API: orchestration assistant built successfully")
    except Exception as e:
        print(f"Backend API: Failed to initialize orchestration assistant: {e}")
        print("Backend API: Running in fallback mode (assistant=None)")

    print("Backend API: Server ready on http://localhost:8000")

    # Hand control back to FastAPI
    try:
        yield
    finally:
        app.state.assistant = None
        app.state.generate_contract_assistant = None
        app.state.deployment_assistant = None
        print("Backend API: Lifespan shutdown complete")

app = FastAPI(title="Smart Contract Assistant API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://vergil-production.up.railway.app",
        "https://vergil-kappa.vercel.app",
    ],
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
app.include_router(data.router)

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
    port = int(os.getenv("PORT", 8000))
    print(f"PORT env var: {os.getenv('PORT')}")
    print(f"Using port: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
