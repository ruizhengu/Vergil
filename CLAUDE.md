# Vergil - Smart Contract Assistant

## Project Overview

AI-powered smart contract development platform. Users describe contracts in natural language, the system generates Solidity code, compiles it, and deploys to Ethereum (Sepolia testnet) with wallet signing approval.

Built on the **Graphite (grafi)** event-driven AI agent framework.

## Architecture

```
Frontend (Next.js :3000) → Backend API (FastAPI :8000) → ReAct Agent (Graphite workflow)
                                                              ↓
                                                        MCP Server (:8081)
                                                        (contract tools)
                                                              ↓
                                                        PostgreSQL (event store)
```

### Key Components

- **Backend** (`apps/backend/`): FastAPI + Graphite ReAct agent
- **Frontend** (`apps/frontend/`): Next.js 14, React 19, Wagmi, RainbowKit, Tailwind
- **MCP Server** (`services/mcp_server/`): FastMCP server with Solidity tools
- **Contract Templates** (`services/mcp_server/src/contracts/`): Jinja2 ERC20/ERC721 templates

### Agent Architecture (Graphite/Grafi)

The agent uses `EventDrivenWorkflow` with `Node` + `Topic` pub/sub routing:
- `Assistant` subclass with `_construct_workflow()` method
- `Node.builder()` fluent API: `.subscribe()`, `.tool()`, `.publish_to()`
- `Topic` with lambda conditions for message routing
- `OpenAITool` for LLM calls, `MCPTool` for MCP server tool execution
- `SubscriptionBuilder` for combining topic subscriptions (`.or_()`, `.and_()`)
- Pydantic response models as `response_format` for structured LLM output
- Prompts loaded from markdown files in `apps/backend/prompts/`

Key agent file: `apps/backend/agents/orchestration_agent.py`

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

Services: postgres (:5432), pgadmin (:5050), mcp_server (:8081), backend (:8000), frontend (:3000), phoenix (:6006)

### Environment Variables
See `.env.example`. Required: `OPENAI_API_KEY`, `OPENAI_MODEL`, `METAMASK_PRIVATE_KEY`, `ETHEREUM_SEPOLIA_RPC`, Postgres credentials.

### Code Quality
```bash
ruff check .       # lint
ruff format .      # format
mypy .             # type check
```

## Key File Paths

```
apps/backend/
├── agents/orchestration_agent.py   # Main orchestration agent (Graphite workflow)
├── main.py                        # FastAPI app + agent initialization
├── routers/
│   ├── chat.py                    # POST /api/chat/ - main chat endpoint
│   ├── approval.py                # Approval polling + wallet signing flow
│   ├── wallet.py                  # Wallet connection management
│   ├── contracts.py               # Contract template endpoints
│   ├── transactions.py            # Transaction broadcast
│   └── tools.py                   # MCP tool listing
├── models/agent_responses.py      # Pydantic response models
├── prompts/                       # Agent prompt templates (markdown)
│   ├── reasoning.md               # ReAct reasoning prompt
│   ├── action.md                  # Function call translation
│   ├── deployment_request.md      # Deployment approval formatting
│   ├── deployment_approval.md     # Approval processing
│   └── final_output.md            # Final response formatting
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
- `compile_contract` - Compile Solidity with solcx (OpenZeppelin via node_modules)
- `get_abi` / `get_bytecode` - Retrieve compiled artifacts by compilation_id
- `prepare_deployment_transaction` - Build unsigned tx for user wallet signing
- `broadcast_signed_transaction` - Broadcast signed tx to Ethereum
- `deploy_contract` - Server-side deployment (legacy)

## Conventions

- Agent prompts are markdown files in `apps/backend/prompts/`
- Response models are Pydantic classes in `apps/backend/models/`
- Agents follow the Graphite `Assistant` → `EventDrivenWorkflow` → `Node` → `Topic` pattern
- OpenZeppelin imports use `@openzeppelin/contracts/...` paths (remapped via node_modules)
- Solidity version: 0.8.27
- All blockchain operations go through MCP tools, not direct web3 calls from the agent
- Event sourcing via PostgreSQL for conversation history and audit trail
- In-memory dicts for approval requests and wallet sessions (not persisted)
