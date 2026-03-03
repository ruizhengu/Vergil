# Vergil - Smart Contract Assistant

## Project Overview

AI-powered smart contract development platform. Users describe contracts in natural language, the system generates Solidity code, compiles it, and deploys to Ethereum (Sepolia testnet) with wallet signing approval.

Built on the **Graphite (grafi)** event-driven AI agent framework.

## Architecture

```
Frontend (Next.js :3000) → Backend API (FastAPI :8000) → Orchestration Agent
                                                              ↓
                                                    ┌─────────┴──────────┐
                                                    ↓                    ↓
                                          Generate Contract Agent   Compile/Deploy Nodes
                                                    ↓                    ↓
                                              MCP Server (:8081)   MCP Server (:8081)
                                              (generate tools)     (compile/deploy tools)
                                                    ↓
                                              PostgreSQL (event store)
```

### Multi-Agent System

**Orchestration Agent** (`orchestration_agent.py`) - Main entry point. Reasoning node routes requests:
- `requires_contract_generation=true` → Contract Generation Agent (via AgentCallingTool)
- `requires_compile=true` → Compile nodes (LLM + MCPTool)
- `requires_deployment=true` → Deployment nodes (approval workflow)
- All false → Output node (conversational response)

**Generate Contract Agent** (`generate_contract_agent.py`) - Sub-agent for contract generation:
- Intent classification → generic (ERC20/ERC721 templates via MCP) or custom (LLM-generated Solidity)
- Returns `ContractGenerationResult` back to orchestration reasoning node

### Key Components

- **Backend** (`apps/backend/`): FastAPI + Graphite multi-agent system
- **Frontend** (`apps/frontend/`): Next.js 14, React 19, Wagmi, RainbowKit, Tailwind
- **MCP Server** (`services/mcp_server/`): FastMCP server with Solidity tools
- **Contract Templates** (`services/mcp_server/src/contracts/`): Jinja2 ERC20/ERC721 templates (OpenZeppelin 5.x)

### Agent Architecture (Graphite/Grafi)

The agents use `EventDrivenWorkflow` with `Node` + `Topic` pub/sub routing:
- `Assistant` subclass with `_construct_workflow()` method
- `Node.builder()` fluent API: `.subscribe()`, `.tool()`, `.publish_to()`
- `Topic` conditions receive `PublishToTopicEvent` (access messages via `event.data`)
- `OpenAITool` for LLM calls, `MCPTool` for MCP server tool execution
- `AgentCallingTool` for agent-to-agent delegation
- `SubscriptionBuilder` for combining topic subscriptions (`.or_()`, `.and_()`)
- Pydantic response models as `response_format` for structured LLM output
- Prompts loaded from markdown files in `apps/backend/prompts/`
- `MCPToolBuilder.build()` is async (use `await`), NOT `a_build()`
- `Assistant.invoke()` is the async generator method, NOT `a_invoke()`
- Topic condition content may be Pydantic objects (not just JSON strings) - use helper to parse both

### Orchestration Agent Flow

```
reasoning_node ──→ reasoning_output_topic (all flags false) ──→ output_node ──→ user
      │
      ├──→ contract_generation_topic ──→ contract_delegation_node ──→ contract_agent_execution_node ──→ back to reasoning
      ├──→ compile_topic ──→ compile_action_node ──→ compile_tool_node ──→ back to reasoning
      └──→ deployment_topic ──→ deployment_request_node ──→ prepare_deployment_node ──→ approval flow
```

### ReasoningResponse Fields

| Field | Purpose |
|-------|---------|
| `reasoning` | Step-by-step thinking |
| `confidence` | 0.0 to 1.0 |
| `requires_compile` | Route to compile nodes |
| `requires_deployment` | Route to deployment workflow |
| `requires_contract_generation` | Route to contract generation agent |
| `solidity_code` | Pass through generated code (from generation or for compilation) |
| `compilation_id` | Pass through compilation result ID |

## Tech Stack

### Backend (Python 3.13+)
- **Framework**: FastAPI + Graphite (grafi==0.0.34)
- **AI**: OpenAI API (GPT-4o), structured outputs via Pydantic
- **Blockchain**: Web3.py, py-solc-x (Solidity 0.8.27)
- **MCP**: FastMCP for tool server
- **DB**: PostgreSQL + SQLAlchemy (event sourcing)
- **Package manager**: uv
- **Linting**: ruff

### Frontend (TypeScript)
- **Framework**: Next.js 14 (App Router), React 19
- **Web3**: Wagmi + RainbowKit + viem
- **Styling**: Tailwind CSS 4
- **HTTP**: Axios

## Development

### Running with Docker
```bash
docker-compose up --build
```

Services: postgres (:5432), pgadmin (:5050), mcp_server (:8082→8081), backend (:8000), frontend (:3000), phoenix (:6006)

### Environment Variables
See `.env`. Required: `OPENAI_API_KEY`, `OPENAI_MODEL`, `METAMASK_PRIVATE_KEY`, `ETHEREUM_SEPOLIA_RPC`, Postgres credentials.
- `PHOENIX_ENDPOINT=phoenix` (hostname only, no port - `setup_tracing` appends port)
- `PHOENIX_PORT=4317`

### Code Quality
```bash
ruff check .       # lint
ruff format .      # format
mypy .             # type check
```

## Key File Paths

```
apps/backend/
├── agents/
│   ├── orchestration_agent.py     # Main orchestration agent (reasoning, compile, deploy, delegation)
│   └── generate_contract_agent.py # Contract generation sub-agent (intent → generate → output)
├── main.py                        # FastAPI app + agent initialization (lifespan)
├── deps/
│   ├── __init__.py
│   └── assistant.py               # FastAPI dependency providers (get_assistant, get_generate_contract_assistant)
├── routers/
│   ├── chat.py                    # POST /api/chat/ - main chat endpoint
│   ├── approval.py                # Approval polling + wallet signing flow
│   ├── wallet.py                  # Wallet connection management
│   ├── contracts.py               # Contract template endpoints
│   ├── transactions.py            # Transaction broadcast
│   └── tools.py                   # MCP tool listing
├── models/
│   ├── agent_responses.py         # Orchestration models (ReasoningResponse, FinalAgentResponse, etc.)
│   └── contract_agent_responses.py # Contract agent models (IntentClassificationResponse, ContractGenerationResult)
├── prompts/
│   ├── reasoning.md               # Orchestration reasoning (routes to generate/compile/deploy/output)
│   ├── compile_action.md          # Compile node - extracts code and calls compile_contract
│   ├── contract_generation_delegation.md  # Delegation to contract generation agent
│   ├── intent_classification.md   # Contract agent - classify generic/custom/conversational
│   ├── generic_action.md          # Contract agent - translate to MCP generate calls
│   ├── custom_generation.md       # Contract agent - LLM generates raw Solidity
│   ├── generate_output.md         # Contract agent - format ContractGenerationResult
│   ├── deployment_request.md      # Deployment approval formatting
│   ├── deployment_approval.md     # Approval processing
│   └── final_output.md            # Final response formatting (FinalAgentResponse)
├── memory/context.py              # Conversation context from event store
└── event_store/postgres.py        # PostgreSQL event store setup

services/mcp_server/src/
├── servers/server.py              # FastMCP server + all tools
├── contracts/
│   ├── erc20.sol                  # ERC20 Jinja2 template
│   └── erc721.sol                 # ERC721 Jinja2 template
└── models/tool_params.py          # Tool parameter validation

apps/frontend/src/
├── app/page.tsx                   # Main chat page
├── components/
│   ├── ChatContainer.tsx          # Chat UI
│   ├── TransactionModal.tsx       # Wallet signing modal
│   └── WalletButton.tsx           # RainbowKit wallet
├── hooks/useApprovalPolling.ts    # Poll for approval requests
├── services/api.ts                # Axios API client
└── config/wagmi.ts                # Wagmi config (Sepolia)
```

## MCP Server Tools

- `generate_erc20_contract` - Template-based ERC20 generation (mintable, burnable, pausable, permit, capped, ownable)
- `generate_erc721_contract` - Template-based ERC721 generation (mintable, burnable, enumerable, uri_storage, ownable)
- `compile_contract` - Compile Solidity with solcx (OpenZeppelin 5.x via node_modules)
- `get_abi` / `get_bytecode` - Retrieve compiled artifacts by compilation_id
- `prepare_deployment_transaction` - Build unsigned tx for user wallet signing
- `broadcast_signed_transaction` - Broadcast signed tx to Ethereum
- `deploy_contract` - Server-side deployment (legacy)

## Conventions

- Agent prompts are markdown files in `apps/backend/prompts/`
- Response models are Pydantic classes in `apps/backend/models/`
- Agents follow the Graphite `Assistant` → `EventDrivenWorkflow` → `Node` → `Topic` pattern
- OpenZeppelin 5.x: `Ownable(initialOwner)` is correct constructor pattern
- OpenZeppelin imports use `@openzeppelin/contracts/...` paths (remapped via node_modules)
- Solidity version: 0.8.27
- All blockchain operations go through MCP tools, not direct web3 calls from the agent
- Event sourcing via PostgreSQL for conversation history and audit trail
- In-memory dicts for approval requests and wallet sessions (not persisted)
- Sub-agents must use a fresh `InvokeContext` (new `invoke_id`) to avoid topic name collisions with parent workflow
- Topic conditions receive `PublishToTopicEvent`, iterate `event.data` for messages
