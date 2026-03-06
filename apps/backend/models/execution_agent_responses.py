from typing import Optional, Literal, List
from pydantic import BaseModel, Field


class ExecutionIntentResponse(BaseModel):
    """Structured response from the execution intent classification node."""

    function_type: Literal["read", "write"] = Field(
        description="Whether this is a read-only view function or state-changing write function"
    )
    contract_address: Optional[str] = Field(
        default=None,
        description="Contract address to call, extracted from context"
    )
    compilation_id: Optional[str] = Field(
        default=None,
        description="Compilation ID from context"
    )
    abi_json: Optional[str] = Field(
        default=None,
        description="Full contract ABI as a JSON string, extracted from context"
    )
    function_name: str = Field(
        description="Name of the contract function to call"
    )
    function_args: List[str] = Field(
        default_factory=list,
        description="Function arguments as stringified values in correct order"
    )
    user_wallet_address: Optional[str] = Field(
        default=None,
        description="User's wallet address, required for write calls"
    )
    value_wei: int = Field(
        default=0,
        description="ETH value in wei to send with the call (for payable functions)"
    )
    reasoning: str = Field(
        description="Explanation of the classification decision"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence level in the classification"
    )


class ExecutionResult(BaseModel):
    """Final output from the execution agent."""

    status: Literal["success", "pending_signature", "failed"] = Field(
        description="Outcome of the execution"
    )
    function_type: Literal["read", "write"] = Field(
        description="Whether this was a read or write call"
    )
    contract_address: Optional[str] = Field(
        default=None,
        description="Contract address that was called"
    )
    function_name: Optional[str] = Field(
        default=None,
        description="Function that was called"
    )
    return_value: Optional[str] = Field(
        default=None,
        description="Return value for read calls as a human-readable string"
    )
    transaction_data: Optional[str] = Field(
        default=None,
        description="Transaction metadata JSON for write calls (includes call_id, gas, chainId, etc.)"
    )
    compilation_id: Optional[str] = Field(
        default=None,
        description="Compilation ID used for this call"
    )
    summary: str = Field(
        description="Human-readable summary of the execution result"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if status is failed"
    )
