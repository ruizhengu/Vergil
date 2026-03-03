from fastapi import Request


async def get_assistant(request: Request):
    """Get the ReAct assistant from app state."""
    return getattr(request.app.state, "assistant", None)


async def get_generate_contract_assistant(request: Request):
    """Get the Generate Contract assistant from app state."""
    return getattr(request.app.state, "generate_contract_assistant", None)
