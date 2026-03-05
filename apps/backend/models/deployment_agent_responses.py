from typing import Optional, Literal
from pydantic import BaseModel, Field


class DeploymentIntentResponse(BaseModel):
    """Structured response from the deployment intent classification node."""

    intent: Literal["compile_and_deploy", "deploy_compiled"] = Field(
        description="What the deployment agent should do"
    )
    reasoning: str = Field(
        description="Explanation of the classification decision"
    )
    solidity_code: Optional[str] = Field(
        default=None,
        description="Solidity source code to compile (for compile_and_deploy or compile_only)"
    )
    compilation_id: Optional[str] = Field(
        default=None,
        description="Existing compilation ID (for deploy_compiled)"
    )
    user_address: Optional[str] = Field(
        default=None,
        description="User's wallet address for deployment"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence level in the classification"
    )


class DeploymentResult(BaseModel):
    """Final output from the deployment agent."""

    status: Literal["ready_for_signing", "compilation_failed", "failed"] = Field(
        description="Outcome of the deployment agent's work"
    )
    transaction_data: Optional[str] = Field(
        default=None,
        description="Unsigned transaction data for wallet signing as JSON string"
    )
    compilation_id: Optional[str] = Field(
        default=None,
        description="Compilation ID from compile step"
    )
    estimated_gas: Optional[int] = Field(
        default=None,
        description="Estimated gas for deployment"
    )
    gas_price_gwei: Optional[float] = Field(
        default=None,
        description="Gas price in gwei"
    )
    chain_id: Optional[int] = Field(
        default=None,
        description="Target chain ID"
    )
    user_address: Optional[str] = Field(
        default=None,
        description="Deployer wallet address"
    )
    summary: str = Field(
        description="Human-readable summary of what happened"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if status is failed or compilation_failed"
    )
