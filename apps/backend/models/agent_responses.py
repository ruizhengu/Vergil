from typing import Optional, List, Literal, Union, Dict
from pydantic import BaseModel, Field


class ReasoningResponse(BaseModel):
    reasoning: str = Field(description="The agent's reasoning process and observations")
    requires_tool_call: bool = Field(
        default=False,
        description="Whether this reasoning requires tool execution"
    )
    tool_call_reasoning: Optional[str] = Field(
        default=None,
        description="Specific reasoning for what tool to call and why"
    )
    tool_result: Optional[Dict[str, str]] = Field(
        default=None,
        description="Result from tool execution, if any"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence level in the reasoning (0-1)"
    )
    requires_deployment: bool = Field(
        default=False,
        description="Whether this reasoning requires deploying a compiled smart contract"
    )

class DeploymentApprovalRequest(BaseModel):
    """Structured response for deployment approval requests."""
    
    contract_type: str = Field(description="Type of smart contract to deploy")
    deployment_details: str = Field(description="Details of the deployment as JSON string")
    estimated_gas: Optional[int] = Field(
        default=None,
        description="Estimated gas cost for deployment"
    )
    security_considerations: List[str] = Field(
        default_factory=list,
        description="Security considerations and risks"
    )
    approval_required: bool = Field(
        default=True,
        description="Whether human approval is required"
    )
    urgency: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Urgency level of the deployment"
    )


class ApprovalResponse(BaseModel):
    """Structured response for processing human approval."""
    
    approval_status: Literal["approved", "rejected", "pending"] = Field(
        description="Status of the approval"
    )
    reasoning: str = Field(description="Reasoning for the approval decision")
    modifications_required: Optional[List[str]] = Field(
        default=None,
        description="List of modifications required if rejected"
    )
    proceed_with_deployment: bool = Field(
        description="Whether to proceed with deployment"
    )


class FinalAgentResponse(BaseModel):
    """Final structured response from the agent."""
    
    status: Literal["completed", "failed", "pending_approval"] = Field(
        description="Overall status of the task"
    )
    summary: str = Field(description="Summary of what was accomplished")
    results: Optional[str] = Field(
        default=None,
        description="Results of the task execution as JSON string"
    )
    next_actions: Optional[List[str]] = Field(
        default=None,
        description="Suggested next actions"
    )
    artifacts: Optional[List[str]] = Field(
        default=None,
        description="Generated artifacts (contracts, transactions, etc.)"
    )
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Any warnings or important notes"
    )

AgentResponse = Union[
    ReasoningResponse,
    DeploymentApprovalRequest,
    ApprovalResponse,
    FinalAgentResponse
]