import re
from typing import Optional, List, Literal, Union, Dict, Any
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError, field_validator


class ReasoningResponse(BaseModel):
    reasoning: str = Field(description="The agent's reasoning process and observations")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence level in the reasoning (0-1)"
    )
    requires_compile: bool = Field(
        default=False,
        description="Whether this request requires compiling a Solidity contract"
    )
    requires_deployment: bool = Field(
        default=False,
        description="Whether this reasoning requires deploying a compiled smart contract"
    )
    requires_contract_generation: bool = Field(
        default=False,
        description="Whether this request should be routed to the contract generation agent"
    )
    solidity_code: Optional[str] = Field(
        default=None,
        description="Solidity source code from contract generation or context, pass through as-is"
    )
    compilation_id: Optional[str] = Field(
        default=None,
        description="Compilation ID from a successful compile_contract call"
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


class FinancialAction(BaseModel):
    amount: float = Field(
        gt=0,
        le=5.0,
        description="Amount in ETH units, must be > 0 and <= 5.0"
    )
    asset: Literal["ETH", "USDC", "WETH"] = Field(
        description="Asset ticker"
    )
    target_address: str = Field(
        description="Target Ethereum address"
    )

    @field_validator("target_address")
    @classmethod
    def validate_target_address(cls, value: str) -> str:
        if not re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
            raise ValueError("target_address must be a valid Ethereum address")
        return value


class StructuredValidationError(BaseModel):
    layer: Literal["pydantic_guardrail", "smt_logic_preparation"]
    message: str
    details: List[Dict[str, Any]] = Field(default_factory=list)


class SMTState(BaseModel):
    pre_condition: Dict[str, Any]
    post_condition: Dict[str, Any]
    action: FinancialAction


def parse_financial_action(payload: Dict[str, Any]) -> FinancialAction:
    return FinancialAction.parse_obj(payload)


def build_validation_error(
    layer: Literal["pydantic_guardrail", "smt_logic_preparation"],
    message: str,
    error: Optional[Exception] = None,
) -> StructuredValidationError:
    details: List[Dict[str, Any]] = []
    if isinstance(error, PydanticValidationError):
        details = error.errors()
    elif error is not None:
        details = [{"error": str(error)}]
    return StructuredValidationError(layer=layer, message=message, details=details)

AgentResponse = Union[
    ReasoningResponse,
    DeploymentApprovalRequest,
    ApprovalResponse,
    FinalAgentResponse
]